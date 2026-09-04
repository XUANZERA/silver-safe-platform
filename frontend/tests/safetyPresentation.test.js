import assert from 'node:assert/strict'
import test from 'node:test'

import {
  presentAlertWorkflow,
  presentRisk,
  presentSafety
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

test('PRESENTATION-003 unavailable risk and alert use neutral tones', () => {
  assert.equal(presentRisk(null, false).tone, 'neutral')
  assert.deepEqual(presentAlertWorkflow(null, false), {
    label: '事件处置状态不可用',
    detail: '无法获取最新事件状态',
    tone: 'neutral'
  })
})
