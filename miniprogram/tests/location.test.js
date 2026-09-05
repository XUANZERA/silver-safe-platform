'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const {
  LOCATION_STATUS,
  createLocationService,
  isAuthDeny,
  locationSampleFromWxResult,
  locationSampleToPayload
} = require('../services/location')

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

function noOpTimers() {
  let callback = null
  return {
    setIntervalImpl(next) { callback = next; return 1 },
    clearIntervalImpl() { callback = null },
    tick() { callback?.() }
  }
}

test('wx.getLocation result becomes the existing Backend WGS84 payload', () => {
  const sample = locationSampleFromWxResult({
    latitude: 23.1291,
    longitude: 113.2644,
    accuracy: 8,
    speed: -1
  }, '2026-09-05T01:02:03.000Z')
  const payload = locationSampleToPayload(sample, 'wx:12:test')

  assert.deepEqual(payload, {
    client_location_id: 'wx:12:test',
    latitude: 23.1291,
    longitude: 113.2644,
    speed_mps: null,
    accuracy_meters: 8,
    source: 'h5',
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:02:03.000Z'
  })
})

test('location service is IDLE and never requests location before explicit start', () => {
  let locationCalls = 0
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: { getLocation() { locationCalls += 1 } },
    uploadLocation() {},
    ...timers
  })

  assert.equal(service.getStatus(), LOCATION_STATUS.IDLE)
  assert.equal(service.isRunning(), false)
  assert.equal(locationCalls, 0)
})

test('explicit start requests WGS84 and reaches TRACKING only after upload', async () => {
  const calls = []
  const statuses = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        calls.push(options)
        options.success({ latitude: 39.9, longitude: 116.4, accuracy: 12, speed: 1 })
      }
    },
    uploadLocation(tripId, payload) {
      calls.push({ tripId, payload })
      return Promise.resolve()
    },
    now: () => Date.parse('2026-09-05T01:02:03.000Z'),
    createClientLocationId: () => 'wx:8:sample',
    onStatusChange: (status) => statuses.push(status),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()

  assert.equal(calls[0].type, 'wgs84')
  assert.equal(calls[1].tripId, 8)
  assert.equal(calls[1].payload.source_crs, 'WGS84')
  assert.deepEqual(statuses, [LOCATION_STATUS.REQUESTING, LOCATION_STATUS.TRACKING])
})

test('wx.getLocation auth deny enters PERMISSION_DENIED and stops automatic requests', async () => {
  let locationCalls = 0
  const errors = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        locationCalls += 1
        options.fail({ errMsg: 'getLocation:fail auth deny' })
      }
    },
    uploadLocation: () => Promise.resolve(),
    createClientLocationId: () => 'wx:8:sample',
    onError: (error) => errors.push(error),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()

  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.equal(service.isRunning(), false)
  assert.equal(errors.length, 1)
  assert.equal(errors[0].permissionDenied, true)
  assert.equal(locationCalls, 1)

  // 停止后续自动定位请求：即使 timer tick 触发，也不会再调用 wx.getLocation
  timers.tick()
  await flush()
  assert.equal(locationCalls, 1)
  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
})

test('isAuthDeny matches auth deny, system permission denied, and system location disabled', () => {
  // auth deny
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail auth deny' }), true)
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail:AUTH DENY' }), true)

  // system permission denied
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail system permission denied' }), true)
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail:system permission denied' }), true)
  assert.equal(isAuthDeny({ errMsg: 'SYSTEM PERMISSION DENIED' }), true)
  assert.equal(isAuthDeny({ message: 'system permission denied' }), true)

  // system location disabled
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail system location disabled' }), true)
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail:system location disabled' }), true)
  assert.equal(isAuthDeny({ errMsg: 'System Location Disabled' }), true)
  assert.equal(isAuthDeny({ message: 'system location disabled' }), true)

  // non-matching errors
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail system error' }), false)
  assert.equal(isAuthDeny({ errMsg: 'getLocation:fail timeout' }), false)
  assert.equal(isAuthDeny(null), false)
  assert.equal(isAuthDeny(undefined), false)
  assert.equal(isAuthDeny({}), false)
})

test('wx.getLocation system permission denied enters PERMISSION_DENIED and stops automatic requests', async () => {
  let locationCalls = 0
  const errors = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        locationCalls += 1
        options.fail({ errMsg: 'getLocation:fail:system permission denied' })
      }
    },
    uploadLocation: () => Promise.resolve(),
    createClientLocationId: () => 'wx:8:sample',
    onError: (error) => errors.push(error),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()

  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.equal(service.isRunning(), false)
  assert.equal(errors.length, 1)
  assert.equal(errors[0].permissionDenied, true)
  assert.equal(locationCalls, 1)

  timers.tick()
  await flush()
  assert.equal(locationCalls, 1)
  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
})

test('wx.getLocation system location disabled enters PERMISSION_DENIED and stops automatic requests', async () => {
  let locationCalls = 0
  const errors = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        locationCalls += 1
        options.fail({ errMsg: 'getLocation:fail:system location disabled' })
      }
    },
    uploadLocation: () => Promise.resolve(),
    createClientLocationId: () => 'wx:8:sample',
    onError: (error) => errors.push(error),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()

  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.equal(service.isRunning(), false)
  assert.equal(errors.length, 1)
  assert.equal(errors[0].permissionDenied, true)
  assert.equal(locationCalls, 1)

  timers.tick()
  await flush()
  assert.equal(locationCalls, 1)
  assert.equal(service.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
})

test('non-auth failure or upload failure uses DEGRADED and later success recovers', async () => {
  let attempt = 0
  const errors = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        attempt += 1
        if (attempt === 1) options.fail({ errMsg: 'getLocation:fail system error' })
        else options.success({ latitude: 39.9, longitude: 116.4, accuracy: 12, speed: 0 })
      }
    },
    uploadLocation: () => Promise.resolve(),
    createClientLocationId: () => 'wx:8:sample',
    onError: (error) => errors.push(error),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()
  assert.equal(service.getStatus(), LOCATION_STATUS.DEGRADED)
  assert.equal(errors[0].permissionDenied, false)
  assert.equal(service.isRunning(), true)

  timers.tick()
  await flush()
  assert.equal(service.getStatus(), LOCATION_STATUS.TRACKING)
})

test('upload failure enters DEGRADED and later success recovers', async () => {
  let uploadAttempt = 0
  const errors = []
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: {
      getLocation(options) {
        options.success({ latitude: 39.9, longitude: 116.4, accuracy: 12, speed: 0 })
      }
    },
    uploadLocation() {
      uploadAttempt += 1
      if (uploadAttempt === 1) return Promise.reject(new Error('upload failure'))
      return Promise.resolve()
    },
    createClientLocationId: () => 'wx:8:sample',
    onError: (error) => errors.push(error),
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  await flush()
  assert.equal(service.getStatus(), LOCATION_STATUS.DEGRADED)
  assert.equal(errors[0].phase, 'upload')
  assert.equal(errors[0].permissionDenied, false)
  assert.equal(service.isRunning(), true)

  timers.tick()
  await flush()
  assert.equal(service.getStatus(), LOCATION_STATUS.TRACKING)
})

test('stop returns IDLE and ignores a late wx.getLocation callback', async () => {
  let locationSuccess
  let uploadCalls = 0
  const timers = noOpTimers()
  const service = createLocationService({
    wxApi: { getLocation(options) { locationSuccess = options.success } },
    uploadLocation() { uploadCalls += 1 },
    ...timers
  })

  service.start({ id: 8, status: 'active' })
  service.stop()
  locationSuccess({ latitude: 39.9, longitude: 116.4, accuracy: 12, speed: 0 })
  await flush()

  assert.equal(service.getStatus(), LOCATION_STATUS.IDLE)
  assert.equal(service.isRunning(), false)
  assert.equal(uploadCalls, 0)
})
