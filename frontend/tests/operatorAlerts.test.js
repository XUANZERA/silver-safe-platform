import assert from 'node:assert/strict'
import test from 'node:test'

import {
  mapOperatorAlerts,
  replaceAuthoritativeOperatorSnapshot,
  runOperatorAlertAction,
  selectOperatorTrips,
  syncDemoElderState
} from '../src/services/operatorAlerts.js'

test('backend alert status is mapped without inventing workflow success', () => {
  const [alert] = mapOperatorAlerts([{
    id: 7,
    elder_id: 3,
    type: 'geofence_exit',
    status: 'new',
    latitude: 23.1,
    longitude: 113.2,
    occurred_at: '2026-09-03T10:00:00Z',
    resolution: null,
    handler: null
  }], [{ id: 3, name: '王奶奶' }])

  assert.equal(alert.backendStatus, 'new')
  assert.equal(alert.status, '待处理')
  assert.equal(alert.elderName, '王奶奶')
})

test('empty backend queue remains an empty real queue', () => {
  const state = {
    alerts: [{ id: 301, status: '待处理', source: 'mock' }],
    elders: [{ id: 101, name: 'Mock elder' }]
  }

  replaceAuthoritativeOperatorSnapshot(state, { items: [] }, { items: [] })

  assert.deepEqual(state.alerts, [])
  assert.deepEqual(state.elders, [])
})

test('OP-REAL-001 real mode never selects mock trips', () => {
  const mockTrips = [{ id: 501, status: '进行中' }]

  assert.deepEqual(selectOperatorTrips(true, mockTrips), [])
  assert.deepEqual(selectOperatorTrips(false, mockTrips), mockTrips)
  assert.notEqual(selectOperatorTrips(false, mockTrips)[0], mockTrips[0])
})

test('OP-REAL-002 real mode cannot locally derive elder state from mock trips', () => {
  const elder = { name: '王奶奶', status: '后端状态待查看', risk: '未在告警队列推断' }

  const changed = syncDemoElderState({
    realMode: true,
    elders: [elder],
    alerts: [],
    trips: [{ elderName: '王奶奶', status: '进行中' }],
    elderName: '王奶奶'
  })

  assert.equal(changed, false)
  assert.deepEqual(elder, {
    name: '王奶奶',
    status: '后端状态待查看',
    risk: '未在告警队列推断'
  })
})

test('OP-DEMO-001 demo mode preserves local mock trip behavior', () => {
  const elder = { name: '王奶奶', status: '在家', risk: '低风险' }

  const changed = syncDemoElderState({
    realMode: false,
    elders: [elder],
    alerts: [],
    trips: [{ elderName: '王奶奶', status: '进行中' }],
    elderName: '王奶奶'
  })

  assert.equal(changed, true)
  assert.equal(elder.status, '出游中')
  assert.equal(elder.risk, '低风险')
})

test('TC-OP-003 real 409 cannot run demo mutation or optimistic success', async () => {
  const displayed = { id: 7, status: '待处理' }
  let demoMutations = 0
  let refreshCalls = 0

  await assert.rejects(
    runOperatorAlertAction({
      realMode: true,
      action: async () => { throw new Error('请先接单再完成处置') },
      refresh: async () => { refreshCalls += 1; return { ok: true } },
      applyDemo: () => { demoMutations += 1; displayed.status = '已解决' }
    }),
    /请先接单/
  )
  assert.equal(displayed.status, '待处理')
  assert.equal(demoMutations, 0)
  assert.equal(refreshCalls, 0)
})

test('successful real write schedules authoritative refresh without local mutation', async () => {
  const displayed = { id: 7, status: '待处理' }
  const calls = []

  const result = await runOperatorAlertAction({
    realMode: true,
    action: async () => { calls.push('write'); return { id: 7, status: 'processing' } },
    refresh: async () => { calls.push('refresh'); return { ok: true } },
    applyDemo: () => { displayed.status = '处理中' }
  })

  assert.deepEqual(calls, ['write', 'refresh'])
  assert.equal(displayed.status, '待处理')
  assert.equal(result.authoritative, true)
})

test('real network failure cannot produce local success state', async () => {
  const displayed = { id: 7, status: '待处理' }

  await assert.rejects(
    runOperatorAlertAction({
      realMode: true,
      action: async () => { throw new Error('network unavailable') },
      refresh: async () => ({ ok: true }),
      applyDemo: () => { displayed.status = '处理中' }
    }),
    /network unavailable/
  )

  assert.equal(displayed.status, '待处理')
})
