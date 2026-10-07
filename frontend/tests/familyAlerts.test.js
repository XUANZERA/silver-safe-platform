import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { createElderApi } from '../src/services/api.js'
import { loadFamilyDashboard } from '../src/services/familyDashboard.js'
import { createPollingController } from '../src/services/polling.js'
import {
  presentAlertWorkflow,
  selectFamilyAlert
} from '../src/services/safetyPresentation.js'

const childHomeSource = readFileSync(
  new URL('../src/views/child/ChildHome.vue', import.meta.url),
  'utf8'
)

function createFamilyApi(alertResults, { failAlerts = false } = {}) {
  const requests = []
  const elderApi = createElderApi(async (path) => {
    requests.push(path)
    if (path === '/elders') return { items: [{ id: 1, name: '测试老人' }], total: 1 }
    if (path === '/elders/1/safety') {
      return { elder_id: 1, risk_status: 'SAFE', latest_open_alert: null }
    }
    if (path === '/elders/1/alerts') {
      if (failAlerts) throw new Error('backend traceback must not reach the UI')
      return alertResults.shift()
    }
    if (path === '/elders/1/current-trip') return { id: 1, status: 'active' }
    if (path === '/elders/1/geofence') return { radius_meters: 500, enabled: true }
    throw new Error(`Unexpected Family API path: ${path}`)
  })
  return { elderApi, requests }
}

test('Family refresh orchestration calls the real Elder API helper with the bound elder id', async () => {
  const { elderApi, requests } = createFamilyApi([{ items: [], total: 0 }])
  const snapshot = await loadFamilyDashboard(elderApi)

  assert.equal(snapshot.currentElder.id, 1)
  assert.deepEqual(snapshot.alerts, [])
  assert.equal(snapshot.alertsLoadFailed, false)
  assert.equal(requests.filter((path) => path === '/elders/1/alerts').length, 1)
  assert.ok(requests.includes('/elders/1/safety'))
  assert.ok(requests.includes('/elders/1/current-trip'))
  assert.ok(requests.includes('/elders/1/geofence'))
})

test('Family initial refresh and 15s polling update the alert card from empty to SOS', async () => {
  const emergency = {
    id: 16,
    elder_id: 1,
    trip_id: 1,
    type: 'emergency',
    status: 'new',
    occurred_at: '2026-10-07T14:50:28.708510Z'
  }
  const { elderApi, requests } = createFamilyApi([
    { items: [], total: 0 },
    { items: [emergency], total: 1 }
  ])
  const timers = []
  let alerts = []
  let alertsLoadFailed = false
  let card = presentAlertWorkflow(null, true)
  const refreshFamilyState = async () => {
    const snapshot = await loadFamilyDashboard(elderApi)
    alertsLoadFailed = snapshot.alertsLoadFailed
    if (!alertsLoadFailed) alerts = snapshot.alerts
    card = presentAlertWorkflow(
      selectFamilyAlert(snapshot.safetyView.latest_open_alert, alerts),
      !alertsLoadFailed
    )
    return snapshot
  }
  const polling = createPollingController({
    task: refreshFamilyState,
    intervalMs: 15000,
    scheduleTimer: (callback, delay) => {
      timers.push({ callback, delay })
      return timers.length
    },
    cancelTimer: () => {}
  })

  await polling.start()
  assert.equal(requests.filter((path) => path === '/elders/1/alerts').length, 1)
  assert.equal(timers.at(-1).delay, 15000)
  assert.equal(card.label, '暂无告警')

  await polling.refresh()
  assert.equal(requests.filter((path) => path === '/elders/1/alerts').length, 2)
  assert.equal(card.label, '老人发起紧急求助')
  assert.equal(card.detail, '待处理')
  assert.match(card.createdAt, /^创建时间：/)
  assert.equal(alerts[0].id, 16)
  polling.stop()
})

test('Family main alert prioritizes the newest open SOS over geofence events', () => {
  const alerts = [
    { id: 18, type: 'emergency', status: 'new', occurred_at: '2026-10-07T14:51:00Z' },
    { id: 20, type: 'geofence_exit', status: 'new', occurred_at: '2026-10-07T14:52:00Z' },
    { id: 16, type: 'emergency', status: 'processing', occurred_at: '2026-10-07T14:50:00Z' }
  ]

  assert.equal(selectFamilyAlert(null, alerts), alerts[0])
})

test('REAL alert failure is distinct from an empty list and never adds a mock alert', async () => {
  const { elderApi } = createFamilyApi([], { failAlerts: true })
  const snapshot = await loadFamilyDashboard(elderApi)
  const card = presentAlertWorkflow(null, !snapshot.alertsLoadFailed)

  assert.equal(snapshot.alertsLoadFailed, true)
  assert.equal(snapshot.alerts, undefined)
  assert.equal(card.label, '告警状态暂时无法获取')
  assert.doesNotMatch(card.label + card.detail, /暂无告警|Mock|演示/)
})

test('elder change prevents an older SOS response from replacing the new elder alerts', async () => {
  let currentGeneration = 1
  let resolveAlerts
  const oldRequests = []
  const oldElderApi = createElderApi(async (path) => {
    oldRequests.push(path)
    if (path === '/elders') return { items: [{ id: 1, name: '老人甲' }], total: 1 }
    if (path === '/elders/1/alerts') {
      return new Promise((resolve) => { resolveAlerts = resolve })
    }
    if (path === '/elders/1/safety') return { elder_id: 1, latest_open_alert: null }
    if (path === '/elders/1/current-trip') return null
    if (path === '/elders/1/geofence') return null
    throw new Error(`Unexpected Family API path: ${path}`)
  })
  const oldRefresh = loadFamilyDashboard(oldElderApi, {
    isCurrent: () => currentGeneration === 1
  })
  await new Promise((resolve) => setImmediate(resolve))
  currentGeneration = 2

  const newElderApi = {
    list: async () => ({ items: [{ id: 2, name: '老人乙' }], total: 1 }),
    safety: async () => ({ elder_id: 2, latest_open_alert: null }),
    alerts: async () => ({ items: [{
      id: 26,
      elder_id: 2,
      trip_id: 2,
      type: 'emergency',
      status: 'new',
      occurred_at: '2026-10-07T15:00:00Z'
    }], total: 1 }),
    currentTrip: async () => ({ id: 2, status: 'active' }),
    geofence: async () => null
  }
  const newSnapshot = await loadFamilyDashboard(newElderApi)
  let visibleAlerts = newSnapshot.alerts

  resolveAlerts({ items: [{ id: 16, elder_id: 1, type: 'emergency', status: 'new' }], total: 1 })
  const oldSnapshot = await oldRefresh
  if (!oldSnapshot.stale) visibleAlerts = oldSnapshot.alerts

  assert.equal(newSnapshot.currentElder.id, 2)
  assert.equal(oldSnapshot.stale, true)
  assert.equal(visibleAlerts[0].id, 26)
  assert.ok(oldRequests.includes('/elders/1/alerts'))
})

test('Family route uses the ChildHome component and cleans up polling on unmount', () => {
  const routes = readFileSync(new URL('../src/router/routes.js', import.meta.url), 'utf8')

  assert.match(routes, /path: '\/child'.*ChildHome\.vue.*allowedRoles: \['family'\]/)
  assert.match(childHomeSource, /task: loadAuthoritativeState/)
  assert.match(childHomeSource, /void polling\.start\(\)/)
  assert.match(childHomeSource, /polling\.stop\(\)/)
  assert.match(childHomeSource, /currentLoadGeneration\+\+/)
})
