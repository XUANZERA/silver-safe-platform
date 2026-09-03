import assert from 'node:assert/strict'
import test from 'node:test'

import {
  nextFamilyAttentionState,
  presentElderTripActionHint
} from '../src/services/modePresentation.js'

test('FAMILY-REAL-001 real mode cannot change local attention state', () => {
  assert.equal(nextFamilyAttentionState(true, false), false)
  assert.equal(nextFamilyAttentionState(true, true), true)
})

test('FAMILY-DEMO-001 demo mode keeps the local attention interaction', () => {
  assert.equal(nextFamilyAttentionState(false, false), true)
  assert.equal(nextFamilyAttentionState(false, true), false)
})

test('real trip copy does not claim that location sharing has started', () => {
  const hint = presentElderTripActionHint(true, false)

  assert.equal(hint, '开始后等待定位数据上报')
  assert.doesNotMatch(hint, /家人可以看到您的位置|已开始定位|正在上传/)
})

test('demo trip copy explicitly identifies simulated location behavior', () => {
  assert.equal(presentElderTripActionHint(false, false), '演示：开始后显示模拟定位')
})
