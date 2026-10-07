'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { ApiError, createApiClient, TOKEN_STORAGE_KEY } = require('../services/api')

function createStorage() {
  const values = new Map()
  return {
    getStorageSync(key) { return values.get(key) || '' },
    setStorageSync(key, value) { values.set(key, value) },
    removeStorageSync(key) { values.delete(key) },
    value(key) { return values.get(key) }
  }
}

test('API client uses existing login endpoint and Bearer token', async () => {
  const calls = []
  const storage = createStorage()
  const wxApi = {
    request(options) {
      calls.push(options)
      if (options.url.endsWith('/auth/login')) {
        options.success({
          statusCode: 200,
          data: { data: { access_token: 'backend-token', user: { id: 1, role: 'elder' } } }
        })
        return
      }
      options.success({ statusCode: 200, data: { data: { items: [] } } })
    }
  }
  const client = createApiClient({
    baseUrl: 'https://api.example.com/api/v1/',
    wxApi,
    storage
  })

  const user = await client.login('elder01', 'demo123')
  await client.listElders()

  assert.equal(user.role, 'elder')
  assert.equal(calls[0].url, 'https://api.example.com/api/v1/auth/login')
  assert.equal(calls[0].header.Authorization, undefined)
  assert.equal(calls[1].header.Authorization, 'Bearer backend-token')
  assert.equal(storage.value(TOKEN_STORAGE_KEY), 'backend-token')
})

test('API client calls the existing trip, location and safety routes', async () => {
  const calls = []
  const wxApi = {
    request(options) {
      calls.push(options)
      options.success({ statusCode: 200, data: { data: null } })
    }
  }
  const client = createApiClient({ baseUrl: 'https://api.example.com/api/v1', wxApi })

  await client.getCurrentTrip(7)
  await client.uploadLocation(9, { source_crs: 'WGS84' })
  await client.getSafetyView(7)

  assert.deepEqual(calls.map(({ url, method }) => [url, method]), [
    ['https://api.example.com/api/v1/elders/7/current-trip', 'GET'],
    ['https://api.example.com/api/v1/trips/9/locations', 'POST'],
    ['https://api.example.com/api/v1/elders/7/safety', 'GET']
  ])
})

test('API client sends SOS to the backend with only trip_id and the existing Bearer token', async () => {
  const calls = []
  const storage = createStorage()
  storage.setStorageSync(TOKEN_STORAGE_KEY, 'saved-elder-token')
  const client = createApiClient({
    baseUrl: 'https://api.example.com/api/v1/',
    storage,
    wxApi: {
      request(options) {
        calls.push(options)
        options.success({
          statusCode: 201,
          data: { success: true, data: { id: 18, trip_id: 42, type: 'emergency' } }
        })
      }
    }
  })

  const result = await client.requestSos(42)

  assert.deepEqual(result, { id: 18, trip_id: 42, type: 'emergency' })
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'https://api.example.com/api/v1/alerts/sos')
  assert.equal(calls[0].method, 'POST')
  assert.deepEqual(calls[0].data, { trip_id: 42 })
  assert.deepEqual(Object.keys(calls[0].data), ['trip_id'])
  assert.equal(calls[0].header.Authorization, 'Bearer saved-elder-token')
})

test('SOS API helper rejects responses that cannot confirm an Alert was created or returned', async () => {
  const malformedResponses = [
    { statusCode: 201, data: { data: { id: 18, trip_id: 42, type: 'emergency' } } },
    { statusCode: 201, data: { success: true, data: { id: 18, trip_id: 42, type: 'geofence_exit' } } },
    { statusCode: 200, data: { success: true, data: { id: 18, trip_id: 99, type: 'emergency' } } }
  ]

  for (const response of malformedResponses) {
    const client = createApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      wxApi: { request(options) { options.success(response) } }
    })
    await assert.rejects(client.requestSos(42), (error) => {
      assert.equal(error instanceof ApiError, true)
      assert.match(error.code, /^INVALID_/)
      return true
    })
  }
})

test('API errors preserve Backend status and error code', async () => {
  const client = createApiClient({
    baseUrl: 'https://api.example.com/api/v1',
    wxApi: {
      request(options) {
        options.success({
          statusCode: 403,
          data: { error: { code: 'TRIP_ACCESS_DENIED', message: '无权访问' } }
        })
      }
    }
  })

  await assert.rejects(client.getCurrentTrip(1), (error) => {
    assert.equal(error instanceof ApiError, true)
    assert.equal(error.status, 403)
    assert.equal(error.code, 'TRIP_ACCESS_DENIED')
    return true
  })
})
