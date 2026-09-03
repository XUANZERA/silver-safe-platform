import assert from 'node:assert/strict'
import test from 'node:test'

import { createPollingController, normalizePollingInterval } from '../src/services/polling.js'

test('polling prevents overlapping requests and stops scheduled work', async () => {
  let finishRequest
  let calls = 0
  const timers = []
  const controller = createPollingController({
    task: () => {
      calls += 1
      return new Promise((resolve) => { finishRequest = resolve })
    },
    intervalMs: 1000,
    scheduleTimer: (callback, delay) => {
      timers.push({ callback, delay, cancelled: false })
      return timers.length - 1
    },
    cancelTimer: (id) => { timers[id].cancelled = true }
  })

  const first = controller.start()
  const overlapping = controller.refresh()
  await Promise.resolve()
  assert.equal(calls, 1)
  assert.equal(first, overlapping)

  finishRequest('done')
  assert.deepEqual(await first, { ok: true, value: 'done' })
  assert.equal(timers.at(-1).delay, 1000)

  controller.stop()
  assert.equal(timers.at(-1).cancelled, true)
  assert.equal(controller.isRunning(), false)
})

test('polling backs off after failures and resets after success', async () => {
  const timers = []
  let shouldFail = true
  const controller = createPollingController({
    task: async () => {
      if (shouldFail) throw new Error('offline')
      return 'ok'
    },
    intervalMs: 2000,
    scheduleTimer: (callback, delay) => {
      timers.push({ callback, delay })
      return timers.length
    },
    cancelTimer: () => {}
  })

  assert.equal((await controller.start()).ok, false)
  assert.equal(timers.at(-1).delay, 4000)
  shouldFail = false
  assert.equal((await controller.refresh()).ok, true)
  assert.equal(timers.at(-1).delay, 2000)
  controller.stop()
})

test('polling interval is configurable with a safe lower bound', () => {
  assert.equal(normalizePollingInterval('8000'), 8000)
  assert.equal(normalizePollingInterval('20', 15000), 15000)
  assert.equal(normalizePollingInterval('invalid', 15000), 15000)
})

test('post-write refresh waits for an old poll and always starts a new request', async () => {
  const resolvers = []
  let calls = 0
  const controller = createPollingController({
    task: () => {
      calls += 1
      return new Promise((resolve) => { resolvers.push(resolve) })
    },
    intervalMs: 1000,
    scheduleTimer: () => 1,
    cancelTimer: () => {}
  })

  const oldPoll = controller.start()
  await Promise.resolve()
  const postWriteRefresh = controller.refreshAfterCurrent()
  assert.equal(calls, 1)
  resolvers[0]()
  await oldPoll
  await Promise.resolve()
  assert.equal(calls, 2)
  resolvers[1]()
  assert.equal((await postWriteRefresh).ok, true)
  controller.stop()
})
