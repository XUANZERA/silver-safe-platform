import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  createRealLocationProvider,
  LOCATION_ERROR,
  LOCATION_STATUS
} from '../src/services/location/RealLocationProvider.js'

function fakeGeolocation() {
  const watches = []
  const cleared = []
  return {
    watches,
    cleared,
    watchPosition(onLocation, onError, options) {
      watches.push({ onLocation, onError, options })
      return watches.length
    },
    clearWatch(id) {
      cleared.push(id)
    }
  }
}

function fakePermissions(initialState) {
  const listeners = new Set()
  const queries = []
  const status = {
    state: initialState,
    onchange: null,
    addEventListener(type, listener) {
      if (type === 'change') listeners.add(listener)
    },
    removeEventListener(type, listener) {
      if (type === 'change') listeners.delete(listener)
    },
    change(nextState) {
      this.state = nextState
      for (const listener of listeners) listener()
      this.onchange?.()
    }
  }
  return {
    queries,
    status,
    query(descriptor) {
      queries.push(descriptor)
      return Promise.resolve(status)
    }
  }
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
}

function position(latitude = 23.1291) {
  return {
    coords: { latitude, longitude: 113.2644, accuracy: 8, speed: 1.2 },
    timestamp: Date.parse('2026-09-04T06:00:00Z')
  }
}

test('LOC-FE-004 unsupported browser reports UNSUPPORTED without a watch', () => {
  const errors = []
  const provider = createRealLocationProvider({ geolocation: null })
  assert.equal(provider.start(() => {}, (error) => errors.push(error)), LOCATION_STATUS.UNSUPPORTED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.UNSUPPORTED }])
})

test('GEO-PERM-003 explicit error code 1 denies permission and clears the active watch', () => {
  const geolocation = fakeGeolocation()
  const errors = []
  const diagnostics = []
  const provider = createRealLocationProvider({
    geolocation,
    onDiagnostic: (diagnostic) => diagnostics.push(diagnostic)
  })
  provider.start(() => {}, (error) => errors.push(error))
  geolocation.watches[0].onError({ code: 1 })

  assert.equal(provider.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.PERMISSION_DENIED }])
  assert.deepEqual(geolocation.cleared, [1])
  assert.deepEqual(diagnostics, [{
    errorCode: 1,
    internalErrorCategory: LOCATION_ERROR.PERMISSION_DENIED,
    permissionState: 'denied'
  }])
})

test('LOC-FE-006/007 valid samples track and invalid samples degrade', () => {
  const geolocation = fakeGeolocation()
  const samples = []
  const errors = []
  const provider = createRealLocationProvider({ geolocation })
  provider.start((sample) => samples.push(sample), (error) => errors.push(error))

  geolocation.watches[0].onLocation(position(100))
  assert.equal(provider.getStatus(), LOCATION_STATUS.DEGRADED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.INVALID_SAMPLE }])

  geolocation.watches[0].onLocation(position())
  assert.equal(provider.getStatus(), LOCATION_STATUS.TRACKING)
  assert.equal(samples.length, 1)
})

test('LOC-FE-008 duplicate start creates only one geolocation watch', () => {
  const geolocation = fakeGeolocation()
  const provider = createRealLocationProvider({ geolocation })
  provider.start(() => {}, () => {})
  provider.start(() => {}, () => {})
  assert.equal(geolocation.watches.length, 1)
})

test('LOC-FE-011 stop clears the watch and invalidates stale callbacks', () => {
  const geolocation = fakeGeolocation()
  const samples = []
  const provider = createRealLocationProvider({ geolocation })
  provider.start((sample) => samples.push(sample), () => {})
  const staleCallback = geolocation.watches[0].onLocation

  provider.stop()
  provider.stop()
  staleCallback(position())

  assert.equal(provider.getStatus(), LOCATION_STATUS.IDLE)
  assert.deepEqual(geolocation.cleared, [1])
  assert.deepEqual(samples, [])
})

test('LOC-FE-015 REAL provider has no Mock or simulator fallback', () => {
  const source = readFileSync(
    new URL('../src/services/location/RealLocationProvider.js', import.meta.url),
    'utf8'
  )
  assert.doesNotMatch(source, /MockLocationProvider|locationSimulator|simulationLocation/)
})

test('GEO-PERM-001 permission prompt after Enable remains REQUESTING', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('prompt')
  const provider = createRealLocationProvider({ geolocation, permissions })

  assert.equal(provider.start(() => {}, () => {}), LOCATION_STATUS.REQUESTING)
  await flush()

  assert.deepEqual(permissions.queries, [{ name: 'geolocation' }])
  assert.equal(provider.getPermissionState(), 'prompt')
  assert.equal(provider.getStatus(), LOCATION_STATUS.REQUESTING)
  assert.equal(geolocation.watches.length, 1)
})

test('GEO-PERM-002 prompt without a modal stays REQUESTING after a temporary acquisition error', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('prompt')
  const errors = []
  const diagnostics = []
  const provider = createRealLocationProvider({
    geolocation,
    permissions,
    onDiagnostic: (diagnostic) => diagnostics.push(diagnostic)
  })
  provider.start(() => {}, (error) => errors.push(error))
  await flush()

  geolocation.watches[0].onError({ code: 2 })

  assert.equal(provider.getStatus(), LOCATION_STATUS.REQUESTING)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.POSITION_UNAVAILABLE }])
  assert.deepEqual(diagnostics, [{
    errorCode: 2,
    internalErrorCategory: LOCATION_ERROR.POSITION_UNAVAILABLE,
    permissionState: 'prompt'
  }])
  assert.deepEqual(geolocation.cleared, [])
})

test('GEO-PERM-003 Permissions API denied state also stops the watch lifecycle', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('denied')
  const errors = []
  const provider = createRealLocationProvider({ geolocation, permissions })
  provider.start(() => {}, (error) => errors.push(error))

  await flush()

  assert.equal(provider.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.PERMISSION_DENIED }])
  assert.deepEqual(geolocation.cleared, [1])
})

test('GEO-PERM-004 granted permission plus error code 2 enters DEGRADED', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('granted')
  const diagnostics = []
  const provider = createRealLocationProvider({
    geolocation,
    permissions,
    onDiagnostic: (diagnostic) => diagnostics.push(diagnostic)
  })
  provider.start(() => {}, () => {})
  await flush()

  geolocation.watches[0].onError({ code: 2 })

  assert.equal(provider.getStatus(), LOCATION_STATUS.DEGRADED)
  assert.deepEqual(diagnostics, [{
    errorCode: 2,
    internalErrorCategory: LOCATION_ERROR.POSITION_UNAVAILABLE,
    permissionState: 'granted'
  }])
})

test('GEO-PERM-005 granted permission plus error code 3 enters DEGRADED', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('granted')
  const errors = []
  const provider = createRealLocationProvider({ geolocation, permissions })
  provider.start(() => {}, (error) => errors.push(error))
  await flush()

  geolocation.watches[0].onError({ code: 3 })

  assert.equal(provider.getStatus(), LOCATION_STATUS.DEGRADED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.TIMEOUT }])
})

test('GEO-PERM-006 REQUESTING becomes TRACKING only after a valid position', () => {
  const geolocation = fakeGeolocation()
  const samples = []
  const provider = createRealLocationProvider({ geolocation, permissions: null })
  provider.start((sample) => samples.push(sample), () => {})

  assert.equal(provider.getStatus(), LOCATION_STATUS.REQUESTING)
  geolocation.watches[0].onLocation(position())

  assert.equal(provider.getStatus(), LOCATION_STATUS.TRACKING)
  assert.equal(samples.length, 1)
})

test('GEO-PERM-007 DEGRADED recovers to TRACKING after a later valid position', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('granted')
  const provider = createRealLocationProvider({ geolocation, permissions })
  provider.start(() => {}, () => {})
  await flush()
  geolocation.watches[0].onError({ code: 2 })
  assert.equal(provider.getStatus(), LOCATION_STATUS.DEGRADED)

  geolocation.watches[0].onLocation(position())

  assert.equal(provider.getStatus(), LOCATION_STATUS.TRACKING)
})

test('GEO-PERM-008 unavailable Permissions API does not block watchPosition', () => {
  const geolocation = fakeGeolocation()
  const samples = []
  const provider = createRealLocationProvider({ geolocation, permissions: null })

  provider.start((sample) => samples.push(sample), () => {})
  geolocation.watches[0].onLocation(position())

  assert.equal(geolocation.watches.length, 1)
  assert.equal(provider.getPermissionState(), 'unavailable')
  assert.equal(provider.getStatus(), LOCATION_STATUS.TRACKING)
  assert.equal(samples.length, 1)
})

test('GEO-PERM-008 rejected geolocation permission query still uses watchPosition', async () => {
  const geolocation = fakeGeolocation()
  const provider = createRealLocationProvider({
    geolocation,
    permissions: {
      query() { return Promise.reject(new TypeError('unsupported permission name')) }
    }
  })

  provider.start(() => {}, () => {})
  await flush()

  assert.equal(provider.getPermissionState(), 'unavailable')
  assert.equal(provider.getStatus(), LOCATION_STATUS.REQUESTING)
  geolocation.watches[0].onLocation(position())
  assert.equal(provider.getStatus(), LOCATION_STATUS.TRACKING)
})

test('GEO-PERM-009 Disable while permission is pending clears watch and discards late callbacks', async () => {
  const geolocation = fakeGeolocation()
  const permissions = fakePermissions('prompt')
  const samples = []
  const errors = []
  const provider = createRealLocationProvider({ geolocation, permissions })
  provider.start((sample) => samples.push(sample), (error) => errors.push(error))
  await flush()
  const latePosition = geolocation.watches[0].onLocation
  const lateError = geolocation.watches[0].onError

  provider.stop()
  lateError({ code: 1 })
  latePosition(position())
  permissions.status.change('denied')

  assert.equal(provider.getStatus(), LOCATION_STATUS.IDLE)
  assert.deepEqual(geolocation.cleared, [1])
  assert.deepEqual(samples, [])
  assert.deepEqual(errors, [])
})
