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

test('LOC-FE-005 permission denial is stable and clears the active watch', () => {
  const geolocation = fakeGeolocation()
  const errors = []
  const provider = createRealLocationProvider({ geolocation })
  provider.start(() => {}, (error) => errors.push(error))
  geolocation.watches[0].onError({ code: 1 })

  assert.equal(provider.getStatus(), LOCATION_STATUS.PERMISSION_DENIED)
  assert.deepEqual(errors, [{ code: LOCATION_ERROR.PERMISSION_DENIED }])
  assert.deepEqual(geolocation.cleared, [1])
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
