import assert from 'node:assert/strict'
import test from 'node:test'

import {
  presentSosFailure,
  presentSosSuccess,
  runSosSubmission
} from '../src/services/sosPresentation.js'

test('SOS success text is based on the authoritative Alert response', () => {
  assert.equal(
    presentSosSuccess({ id: 42, status: 'new' }),
    '后端已记录求助事件 #42，当前告警状态：待接单'
  )
})

test('SOS network failure never claims that anyone was notified', () => {
  const message = presentSosFailure(new Error('网络中断'))

  assert.match(message, /发送失败或状态未知/)
  assert.doesNotMatch(message, /已通知|成功/)
})

test('SOS-DOUBLE-001 synchronous duplicate submission calls backend once', async () => {
  let pending = false
  let apiCalls = 0
  let finishRequest
  const submit = () => {
    apiCalls += 1
    return new Promise((resolve) => { finishRequest = resolve })
  }
  const options = {
    isPending: () => pending,
    setPending: (value) => { pending = value },
    submit
  }

  const first = runSosSubmission(options)
  const second = runSosSubmission(options)

  assert.equal(apiCalls, 1)
  assert.deepEqual(await second, { submitted: false })
  finishRequest({ id: 42, status: 'new' })
  assert.deepEqual(await first, {
    submitted: true,
    value: { id: 42, status: 'new' }
  })
  assert.equal(pending, false)
})

test('EMERGENCY-001 SOS remains a backend submission, not a phone action', async () => {
  let pending = false
  let backendSosCalls = 0
  const result = await runSosSubmission({
    isPending: () => pending,
    setPending: (value) => { pending = value },
    submit: async () => {
      backendSosCalls += 1
      return { id: 73, status: 'new' }
    }
  })

  assert.equal(backendSosCalls, 1)
  assert.deepEqual(result.value, { id: 73, status: 'new' })
  assert.doesNotMatch(presentSosSuccess(result.value), /tel:|拨号|电话/)
})
