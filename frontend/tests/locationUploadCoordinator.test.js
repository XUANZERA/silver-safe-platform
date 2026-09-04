import assert from 'node:assert/strict'
import test from 'node:test'

import { LOCATION_STATUS } from '../src/services/location/RealLocationProvider.js'
import {
  createLocationUploadCoordinator,
  isActiveTrip
} from '../src/services/location/LocationUploadCoordinator.js'
import { mapRealLocationSampleToPayload } from '../src/services/location/locationMapper.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function fakeClock() {
  let current = 0
  let nextId = 1
  const timers = new Map()
  return {
    now: () => current,
    setTimer(callback, delay) {
      const id = nextId++
      timers.set(id, { callback, due: current + delay })
      return id
    },
    clearTimer(id) {
      timers.delete(id)
    },
    advance(milliseconds) {
      current += milliseconds
      const due = [...timers.entries()]
        .filter(([, timer]) => timer.due <= current)
        .sort((left, right) => left[1].due - right[1].due)
      for (const [id, timer] of due) {
        if (!timers.delete(id)) continue
        timer.callback()
      }
    },
    timerCount: () => timers.size
  }
}

function sample(latitude) {
  return {
    latitude,
    longitude: 113.2644,
    accuracyMeters: 8,
    speedMps: 1.2,
    recordedAt: '2026-09-04T06:00:00.000Z',
    source: 'h5',
    sourceCrs: 'WGS84'
  }
}

function mapper({ tripId, clientLocationId, sample: value }) {
  return { tripId, clientLocationId, marker: value.latitude }
}

function idFactory() {
  let next = 0
  return () => `location-${++next}`
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
}

test('LOC-FE-001/002 coordinator binds active Trip only', () => {
  assert.equal(isActiveTrip({ id: 1, status: 'active' }), true)
  for (const trip of [null, { id: 1, status: 'created' }, { id: 1, status: 'completed' }]) {
    const coordinator = createLocationUploadCoordinator({ upload() {}, mapSample: mapper })
    assert.throws(() => coordinator.start(trip), /active Trip/)
    assert.equal(coordinator.handleSample(sample(1)), false)
  }
})

test('LOC-FE-008 duplicate coordinator start is idempotent', () => {
  const coordinator = createLocationUploadCoordinator({ upload() {}, mapSample: mapper })
  const trip = { id: 7, status: 'active' }
  assert.equal(coordinator.start(trip), true)
  assert.equal(coordinator.start(trip), false)
})

test('LOC-FE-009 single in-flight upload retains only the latest sample', async () => {
  const firstRequest = deferred()
  const uploads = []
  const coordinator = createLocationUploadCoordinator({
    upload(_tripId, payload) {
      uploads.push(payload)
      return uploads.length === 1 ? firstRequest.promise : Promise.resolve()
    },
    mapSample: mapper,
    minIntervalMs: 0,
    createClientLocationId: idFactory()
  })
  coordinator.start({ id: 7, status: 'active' })
  coordinator.handleSample(sample(1))
  coordinator.handleSample(sample(2))
  coordinator.handleSample(sample(3))

  assert.deepEqual(uploads.map((item) => item.marker), [1])
  firstRequest.resolve()
  await flush()
  assert.deepEqual(uploads.map((item) => item.marker), [1, 3])
})

test('LOC-FE-010 throttle uses one timer and remains latest-wins', async () => {
  const clock = fakeClock()
  const uploads = []
  const coordinator = createLocationUploadCoordinator({
    upload(_tripId, payload) { uploads.push(payload) },
    mapSample: mapper,
    minIntervalMs: 100,
    now: clock.now,
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    createClientLocationId: idFactory()
  })
  coordinator.start({ id: 7, status: 'active' })
  coordinator.handleSample(sample(1))
  await flush()
  clock.advance(25)
  coordinator.handleSample(sample(2))
  coordinator.handleSample(sample(3))

  assert.equal(clock.timerCount(), 1)
  clock.advance(74)
  assert.deepEqual(uploads.map((item) => item.marker), [1])
  clock.advance(1)
  await flush()
  assert.deepEqual(uploads.map((item) => item.marker), [1, 3])
})

test('LOC-FE-011 stop clears timers and rejects later samples', async () => {
  const clock = fakeClock()
  const uploads = []
  const coordinator = createLocationUploadCoordinator({
    upload(_tripId, payload) { uploads.push(payload) },
    mapSample: mapper,
    minIntervalMs: 100,
    now: clock.now,
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    createClientLocationId: idFactory()
  })
  coordinator.start({ id: 7, status: 'active' })
  coordinator.handleSample(sample(1))
  await flush()
  coordinator.handleSample(sample(2))
  assert.equal(clock.timerCount(), 1)

  coordinator.stop()
  assert.equal(clock.timerCount(), 0)
  assert.equal(coordinator.handleSample(sample(3)), false)
  clock.advance(100)
  assert.deepEqual(uploads.map((item) => item.marker), [1])
})

test('LOC-FE-012 Trip-end stop prevents an in-flight request follow-up', async () => {
  const request = deferred()
  const uploads = []
  const coordinator = createLocationUploadCoordinator({
    upload(_tripId, payload) { uploads.push(payload); return request.promise },
    mapSample: mapper,
    minIntervalMs: 0,
    createClientLocationId: idFactory()
  })
  coordinator.start({ id: 7, status: 'active' })
  coordinator.handleSample(sample(1))
  coordinator.handleSample(sample(2))
  coordinator.stop()
  request.resolve()
  await flush()
  assert.deepEqual(uploads.map((item) => item.marker), [1])
})

test('LOC-FE-017/018 failed upload degrades and a later success recovers tracking', async () => {
  const statuses = []
  let attempts = 0
  const coordinator = createLocationUploadCoordinator({
    upload() {
      attempts += 1
      if (attempts === 1) return Promise.reject(new Error('offline'))
      return Promise.resolve()
    },
    mapSample: mapper,
    minIntervalMs: 0,
    createClientLocationId: idFactory(),
    onStatusChange: (status) => statuses.push(status)
  })
  coordinator.start({ id: 7, status: 'active' })
  coordinator.handleSample(sample(1))
  await flush()
  assert.equal(coordinator.getStatus(), LOCATION_STATUS.DEGRADED)
  coordinator.handleSample(sample(2))
  await flush()
  assert.equal(coordinator.getStatus(), LOCATION_STATUS.TRACKING)
  assert.deepEqual(statuses, [LOCATION_STATUS.DEGRADED, LOCATION_STATUS.TRACKING])
})

test('ADR-010 rejects non-WGS84 REAL samples before the uploader', async () => {
  let uploadCalls = 0
  const coordinator = createLocationUploadCoordinator({
    upload() { uploadCalls += 1 },
    mapSample: mapRealLocationSampleToPayload,
    minIntervalMs: 0,
    createClientLocationId: idFactory()
  })
  coordinator.start({ id: 7, status: 'active' })
  assert.throws(
    () => coordinator.handleSample({ ...sample(1), sourceCrs: 'GCJ02' }),
    /sourceCrs/
  )
  assert.equal(uploadCalls, 0)
})
