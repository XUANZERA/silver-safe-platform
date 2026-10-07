import assert from 'node:assert/strict'
import test from 'node:test'

import {
  presentAlertWorkflow,
  presentRisk,
  presentSafety,
  selectFamilyAlert
} from '../src/services/safetyPresentation.js'

test('unavailable backend state never renders as safe', () => {
  const result = presentSafety(null, false)

  assert.equal(result.trip, '数据不可用')
  assert.equal(result.location, '数据不可用')
  assert.equal(result.risk, '数据不可用 / 无法获取最新状态')
  assert.equal(result.tone, 'neutral')
})

test('PRESENTATION-001 SAFE and PROCESSING produce independent models', () => {
  const view = {
    trip_status: 'active',
    location_health: 'FRESH',
    risk_status: 'SAFE'
  }
  const risk = presentRisk(view)
  const workflow = presentAlertWorkflow({ type: 'geofence_exit', status: 'processing' })

  assert.deepEqual(risk, { label: '当前位于安全围栏内', tone: 'success' })
  assert.deepEqual(workflow, {
    label: '工作人员处理中',
    detail: '围栏越界',
    tone: 'processing'
  })
})

test('unknown or stale location cannot be displayed as safe', () => {
  const stale = presentSafety({
    trip_status: 'active',
    location_health: 'STALE',
    risk_status: null
  })

  assert.equal(stale.location, '定位较久未更新')
  assert.equal(stale.risk, '风险状态无法判定')
  assert.equal(stale.tone, 'neutral')
})

test('PRESENTATION-002 unknown location health cannot produce a success tone', () => {
  const view = {
    trip_status: 'active',
    location_health: 'UNRECOGNIZED',
    risk_status: 'SAFE'
  }

  assert.deepEqual(presentRisk(view), {
    label: '风险状态无法判定',
    tone: 'neutral'
  })
  assert.equal(presentSafety(view).location, '定位状态未知')
})

test('SOS emergency/new presentation includes a clear title, pending status, and creation time', () => {
  const workflow = presentAlertWorkflow({
    id: 42,
    type: 'emergency',
    status: 'new',
    occurred_at: '2026-10-07T08:30:00Z'
  })

  assert.equal(workflow.label, '老人发起紧急求助')
  assert.equal(workflow.detail, '待处理')
  assert.equal(workflow.tone, 'danger')
  assert.match(workflow.createdAt, /^创建时间：.+/)
})

test('SOS alert is prioritized over a later open geofence event', () => {
  const emergency = { id: 42, type: 'emergency', status: 'new' }
  const geofence = { id: 43, type: 'geofence_exit', status: 'new' }

  assert.equal(selectFamilyAlert(geofence, [geofence, emergency]), emergency)
})

test('REAL empty and unavailable alert states remain distinct', () => {
  assert.equal(presentAlertWorkflow(selectFamilyAlert(null, []), true).label, '暂无告警')
  const unavailable = presentAlertWorkflow(null, false)
  assert.equal(unavailable.label, '告警状态暂时无法获取')
  assert.notEqual(unavailable.label, '暂无告警')
})

test('PRESENTATION-003 unavailable risk and alert use neutral tones', () => {
  assert.equal(presentRisk(null, false).tone, 'neutral')
  assert.deepEqual(presentAlertWorkflow(null, false), {
    label: '告警状态暂时无法获取',
    detail: '请稍后刷新状态',
    tone: 'neutral'
  })
})
