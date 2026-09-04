import assert from 'node:assert/strict'
import test from 'node:test'

import {
  InvalidLocationSampleError,
  locationSampleFromBrowserPosition,
  validateLocationSample
} from '../src/services/location/locationSample.js'

function browserPosition(overrides = {}) {
  return {
    coords: {
      latitude: 23.1291,
      longitude: 113.2644,
      accuracy: 12,
      speed: null,
      ...overrides
    },
    timestamp: Date.parse('2026-09-04T06:00:00Z')
  }
}

test('LOC-FE-006 valid browser position becomes an in-memory LocationSample', () => {
  const sample = locationSampleFromBrowserPosition(browserPosition())
  assert.deepEqual(sample, {
    latitude: 23.1291,
    longitude: 113.2644,
    accuracyMeters: 12,
    speedMps: null,
    recordedAt: '2026-09-04T06:00:00.000Z',
    source: 'h5',
    sourceCrs: 'WGS84'
  })
  assert.equal(Object.isFrozen(sample), true)
})

test('LOC-FE-007 invalid browser samples are rejected before transport', () => {
  for (const [field, value] of [
    ['latitude', 91],
    ['latitude', Number.NaN],
    ['longitude', -181],
    ['accuracy', -1],
    ['speed', 101]
  ]) {
    assert.throws(
      () => locationSampleFromBrowserPosition(browserPosition({ [field]: value })),
      InvalidLocationSampleError
    )
  }
  assert.throws(
    () => validateLocationSample({
      latitude: 1,
      longitude: 1,
      accuracyMeters: null,
      speedMps: null,
      recordedAt: 'not-a-time'
    }),
    /recordedAt/
  )
  assert.throws(
    () => validateLocationSample({
      latitude: 1,
      longitude: 1,
      accuracyMeters: null,
      speedMps: null,
      recordedAt: '2026-09-04T06:00:00.000Z',
      sourceCrs: 'GCJ02'
    }),
    /sourceCrs/
  )
})
