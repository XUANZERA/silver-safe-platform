'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const api = require('../services/api')

const FAMILY_USER = { id: 2, role: 'family' }
const ELDER = { id: 1, name: 'elder_test_01' }
const SAFETY_VIEW = {
  location_health: 'FRESH',
  risk_status: 'SAFE',
  latest_location: null
}

async function createFamilyHarness({ alertsResponse = [], failAlerts = false, failSafety = false } = {}) {
  const originalWx = global.wx
  const originalPage = global.Page
  const calls = []
  const storage = new Map()
  let pageDefinition

  global.wx = {
    getStorageSync(key) { return storage.get(key) || '' },
    setStorageSync(key, value) { storage.set(key, value) },
    removeStorageSync(key) { storage.delete(key) },
    request(options) {
      calls.push(options)
      const requestPath = new URL(options.url).pathname.replace('/api/v1', '')
      if (requestPath === '/auth/login') {
        options.success({
          statusCode: 200,
          data: { data: { access_token: 'family-test-token', user: FAMILY_USER } }
        })
      } else if (requestPath === '/auth/me') {
        options.success({ statusCode: 200, data: { data: FAMILY_USER } })
      } else if (requestPath === '/elders') {
        options.success({ statusCode: 200, data: { data: { items: [ELDER] } } })
      } else if (requestPath === '/elders/1/safety' && failSafety) {
        options.success({ statusCode: 503, data: { message: 'safety unavailable' } })
      } else if (requestPath === '/elders/1/safety') {
        options.success({ statusCode: 200, data: { data: SAFETY_VIEW } })
      } else if (requestPath === '/elders/1/alerts' && failAlerts) {
        options.success({ statusCode: 503, data: { message: 'alerts unavailable' } })
      } else if (requestPath === '/elders/1/alerts') {
        options.success({ statusCode: 200, data: { data: alertsResponse } })
      } else {
        options.success({ statusCode: 404, data: { message: `unexpected ${requestPath}` } })
      }
    }
  }

  api.clearAccessToken()
  api.configureApi({ baseUrl: 'https://api.example.test/api/v1' })
  await api.login('family_test_01', 'test-password')
  calls.length = 0

  global.Page = (definition) => { pageDefinition = definition }
  const pageModule = require.resolve('../pages/family/map')
  delete require.cache[pageModule]
  require(pageModule)
  const page = {
    ...pageDefinition,
    data: { ...pageDefinition.data },
    setData(update) { Object.assign(this.data, update) }
  }

  return {
    calls,
    page,
    restore() {
      api.clearAccessToken()
      api.configureApi({ baseUrl: '' })
      delete require.cache[pageModule]
      if (originalWx === undefined) delete global.wx
      else global.wx = originalWx
      if (originalPage === undefined) delete global.Page
      else global.Page = originalPage
    }
  }
}

function requestPaths(calls) {
  return calls.map((call) => new URL(call.url).pathname.replace('/api/v1', ''))
}

test('Family initial load uses the production API client for elders, safety, and alerts; onShow refreshes alerts', async () => {
  const harness = await createFamilyHarness()
  try {
    await harness.page.onLoad()

    assert.deepEqual(requestPaths(harness.calls), [
      '/auth/me',
      '/elders',
      '/elders/1/safety',
      '/elders/1/alerts'
    ])
    for (const call of harness.calls) {
      assert.equal(call.header.Authorization, 'Bearer family-test-token')
    }

    harness.calls.length = 0
    await harness.page.onShow()
    assert.deepEqual(requestPaths(harness.calls), [
      '/elders',
      '/elders/1/safety',
      '/elders/1/alerts'
    ])
  } finally {
    harness.restore()
  }
})

test('Family page presents an open SOS ahead of a geofence alert', async () => {
  const harness = await createFamilyHarness({
    alertsResponse: [
      {
        id: 20,
        elder_id: 1,
        trip_id: 1,
        type: 'emergency',
        status: 'new',
        occurred_at: '2026-10-07T08:15:00Z'
      },
      {
        id: 21,
        elder_id: 1,
        trip_id: 1,
        type: 'geofence_exit',
        status: 'new',
        occurred_at: '2026-10-07T08:16:00Z'
      }
    ]
  })
  try {
    await harness.page.onLoad()
    assert.equal(harness.page.data.primaryAlert.id, 20)
    assert.equal(harness.page.data.primaryAlert.title, '老人发起紧急求助')
    assert.equal(harness.page.data.primaryAlert.statusText, '待处理')
    assert.equal(harness.page.data.primaryAlert.occurred_at, '2026-10-07T08:15:00Z')

    const markup = fs.readFileSync(path.join(__dirname, '../pages/family/map.wxml'), 'utf8')
    assert.match(markup, /\{\{primaryAlert\.title\}\}/)
    assert.match(markup, /\{\{primaryAlert\.statusText\}\}/)
    assert.match(markup, /发生时间/)
  } finally {
    harness.restore()
  }
})

test('Family page selects the newest open SOS and uses the larger id for equal timestamps', async () => {
  const occurredAt = '2026-10-07T08:15:00Z'
  const harness = await createFamilyHarness({
    alertsResponse: [
      { id: 40, type: 'emergency', status: 'new', occurred_at: '2026-10-07T08:14:00Z' },
      { id: 51, type: 'emergency', status: 'processing', occurred_at: occurredAt },
      { id: 52, type: 'emergency', status: 'new', occurred_at: occurredAt },
      { id: 99, type: 'geofence_exit', status: 'new', occurred_at: '2026-10-07T08:17:00Z' }
    ]
  })
  try {
    await harness.page.onLoad()
    assert.equal(harness.page.data.primaryAlert.id, 52)
    assert.equal(harness.page.data.primaryAlert.statusText, '待处理')
  } finally {
    harness.restore()
  }
})

test('an empty alerts response is shown as 暂无告警', async () => {
  const harness = await createFamilyHarness({ alertsResponse: [] })
  try {
    await harness.page.onLoad()
    assert.deepEqual(harness.page.data.alerts, [])
    assert.equal(harness.page.data.alertsEmpty, true)
    assert.equal(harness.page.data.alertLoadFailed, false)
    const markup = fs.readFileSync(path.join(__dirname, '../pages/family/map.wxml'), 'utf8')
    assert.match(markup, /暂无告警/)
  } finally {
    harness.restore()
  }
})

test('an alerts request failure is shown as unavailable and does not fall back to mock alerts', async () => {
  const harness = await createFamilyHarness({ failAlerts: true })
  try {
    await harness.page.onLoad()
    assert.deepEqual(harness.page.data.alerts, [])
    assert.equal(harness.page.data.alertsEmpty, false)
    assert.equal(harness.page.data.alertLoadFailed, true)
    assert.equal(harness.page.data.primaryAlert, null)
    assert.equal(requestPaths(harness.calls).includes('/elders/1/alerts'), true)
    const markup = fs.readFileSync(path.join(__dirname, '../pages/family/map.wxml'), 'utf8')
    assert.match(markup, /告警状态暂时无法获取/)
  } finally {
    harness.restore()
  }
})

test('alerts are still requested and rendered when the safety request fails', async () => {
  const harness = await createFamilyHarness({
    failSafety: true,
    alertsResponse: [{ id: 20, type: 'emergency', status: 'new', occurred_at: '2026-10-07T08:15:00Z' }]
  })
  try {
    await harness.page.onLoad()
    assert.deepEqual(requestPaths(harness.calls).slice(-2), [
      '/elders/1/safety',
      '/elders/1/alerts'
    ])
    assert.equal(harness.page.data.safetyView, null)
    assert.equal(harness.page.data.primaryAlert.title, '老人发起紧急求助')
    assert.equal(harness.page.data.alertLoadFailed, false)
  } finally {
    harness.restore()
  }
})
