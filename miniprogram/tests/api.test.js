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
