import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveApiBaseUrl } from '../src/services/api.js'
import { loadDemoItinerary } from '../src/services/modeBoundary.js'
import {
  TRIP_LOAD_FAILURE,
  createElderTripState,
  loadAuthoritativeElderTrip,
  reloadAfterAuthReady
} from '../src/services/elderCurrentTrip.js'
import { createLocationUploadCoordinator } from '../src/services/location/LocationUploadCoordinator.js'
import { createRealLocationProvider, LOCATION_STATUS } from '../src/services/location/RealLocationProvider.js'

const activeTrip = Object.freeze({
  id: 73,
  elder_id: 8,
  destination: '永庆坊',
  status: 'active'
})

function activeReload(overrides = {}) {
  const state = overrides.state || createElderTripState({ realMode: true })
  const calls = []
  const reload = () => loadAuthoritativeElderTrip({
    state,
    listElders: overrides.listElders || (async () => {
      calls.push('GET /elders')
      return { items: [{ id: 8, name: '陈伯', age: 72 }] }
    }),
    getCurrentTrip: overrides.getCurrentTrip || (async (elderId) => {
      calls.push(`GET /elders/${elderId}/current-trip`)
      return activeTrip
    }),
    onElder: overrides.onElder
  })
  return { calls, reload, state }
}

test('REFRESH-TRIP-001 auth restored then authoritative backend active Trip is shown after reload', async () => {
  const fixture = activeReload()
  let authReady = false

  await reloadAfterAuthReady({
    ensureAuthReady: async () => { authReady = true },
    reload: fixture.reload
  })

  assert.equal(authReady, true)
  assert.deepEqual(fixture.calls, [
    'GET /elders',
    'GET /elders/8/current-trip'
  ])
  assert.equal(fixture.state.currentTrip, activeTrip)
  assert.equal(fixture.state.currentTripBackendStatus, 'active')
  assert.equal(fixture.state.tripStatus, '出游中')
  assert.equal(fixture.state.tripDataAvailable, true)
})

test('REFRESH-TRIP-002 temporary auth failure can reload after auth becomes ready', async () => {
  const state = createElderTripState({ realMode: true })
  let currentTripAttempts = 0
  let authReady = false
  const fixture = activeReload({
    state,
    getCurrentTrip: async () => {
      currentTripAttempts += 1
      if (currentTripAttempts === 1) {
        throw Object.assign(new Error('access token not restored yet'), {
          status: 401,
          code: 'UNAUTHORIZED'
        })
      }
      assert.equal(authReady, true)
      return activeTrip
    }
  })

  await assert.rejects(fixture.reload, /access token not restored yet/)
  assert.equal(state.tripLoadFailureKind, TRIP_LOAD_FAILURE.AUTH_UNAVAILABLE)
  assert.equal(state.tripDataAvailable, false)

  await reloadAfterAuthReady({
    ensureAuthReady: async () => { authReady = true },
    reload: fixture.reload
  })

  assert.equal(currentTripAttempts, 2)
  assert.equal(state.currentTripBackendStatus, 'active')
  assert.equal(state.tripStatus, '出游中')
  assert.equal(state.tripDataAvailable, true)
})

test('REFRESH-TRIP-003 a 200 active Trip cannot leave UI state unavailable', async () => {
  const fixture = activeReload()
  await fixture.reload()

  assert.notEqual(fixture.state.tripStatus, '行程状态不可用')
  assert.equal(fixture.state.tripLoadFailureKind, null)
  assert.equal(fixture.state.tripLoadError, null)
})

test('GEO-PERM-010 active Trip reload keeps location IDLE and never starts geolocation', async () => {
  const fixture = activeReload()
  let watchPositionCalls = 0
  const provider = createRealLocationProvider({
    geolocation: {
      watchPosition() { watchPositionCalls += 1; return 1 },
      clearWatch() {}
    }
  })

  await fixture.reload()

  assert.equal(fixture.state.currentTripBackendStatus, 'active')
  assert.equal(provider.getStatus(), LOCATION_STATUS.IDLE)
  assert.equal(watchPositionCalls, 0)
})

test('REFRESH-TRIP-005 active Trip reload never POSTs a location', async () => {
  const fixture = activeReload()
  let locationPostCalls = 0
  const coordinator = createLocationUploadCoordinator({
    upload: async () => { locationPostCalls += 1 },
    mapSample: (sample) => sample
  })

  await fixture.reload()

  assert.equal(fixture.state.currentTripBackendStatus, 'active')
  assert.equal(coordinator.getStatus(), LOCATION_STATUS.IDLE)
  assert.equal(locationPostCalls, 0)
})

test('REFRESH-TRIP-006 REAL refresh failure never reads Demo/sessionStorage fallback', async () => {
  const state = createElderTripState({ realMode: true })
  let storageReads = 0
  const demoStorage = { getItem() { storageReads += 1; return JSON.stringify([{ title: 'Demo 公园' }]) } }

  assert.equal(loadDemoItinerary(true, demoStorage), null)

  await assert.rejects(
    loadAuthoritativeElderTrip({
      state,
      listElders: async () => { throw Object.assign(new Error('backend down'), { status: 503 }) },
      getCurrentTrip: async () => activeTrip
    }),
    /backend down/
  )

  assert.equal(storageReads, 0)
  assert.equal(state.currentTrip, null)
  assert.equal(state.destination, '')
  assert.equal(state.tripLoadFailureKind, TRIP_LOAD_FAILURE.TRIP_UNAVAILABLE)
})

test('REFRESH-TRIP-007 later authoritative success clears the previous trip load error', async () => {
  const state = createElderTripState({ realMode: true })
  let fail = true
  const fixture = activeReload({
    state,
    getCurrentTrip: async () => {
      if (fail) throw Object.assign(new Error('temporary outage'), { status: 503 })
      return activeTrip
    }
  })

  await assert.rejects(fixture.reload, /temporary outage/)
  assert.equal(state.tripLoadError.message, 'temporary outage')
  assert.equal(state.tripDataAvailable, false)

  fail = false
  await fixture.reload()

  assert.equal(state.tripLoadError, null)
  assert.equal(state.tripLoadFailureKind, null)
  assert.equal(state.tripDataAvailable, true)
  assert.equal(state.currentTripBackendStatus, 'active')
})

test('local REAL API uses the browser loopback hostname so Strict refresh cookie survives reload', () => {
  assert.equal(
    resolveApiBaseUrl('http://127.0.0.1:8000/api/v1', {
      origin: 'http://localhost:5173',
      hostname: 'localhost'
    }),
    'http://localhost:8000/api/v1'
  )
  assert.equal(
    resolveApiBaseUrl('https://api.example.net/api/v1', {
      origin: 'https://app.example.com',
      hostname: 'app.example.com'
    }),
    'https://api.example.net/api/v1'
  )
})
