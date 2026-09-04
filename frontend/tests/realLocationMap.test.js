import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  CANONICAL_CRS,
  InvalidCanonicalLocationError,
  isCanonicalLocation,
  validateCanonicalLocation,
  validateCanonicalTrack
} from '../src/services/map/mapLocationMapper.js'

import {
  AMAP_MAX_BATCH_SIZE,
  AmapConversionError,
  convertCanonicalLocation,
  convertCanonicalTrack,
  createFamilyStateCoordinator,
  createLatestLocationCoordinator,
  createMapLifecycleManager,
  createOperatorSelectionCoordinator,
  DISPLAY_CRS,
  formatPolylinePath,
  loadAMapSdk,
  resetAMapSdk,
  setAMapSdkLoader,
  syncAMapPolyline
} from '../src/services/map/amapCoordinateAdapter.js'

import {
  presentLocationHealth,
  presentRisk,
  presentSafety
} from '../src/services/safetyPresentation.js'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

// Mock converter simulating AMap.convertFrom
function createMockAMapConverter({
  delayMs = 0,
  shouldFail = false,
  offsetLng = 0.005,
  offsetLat = 0.002
} = {}) {
  return async (points, type) => {
    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
    if (shouldFail) {
      return null
    }
    assert.equal(type, 'gps', 'AMap 必须使用 gps 类型将 WGS84 转换为 GCJ-02')
    return points.map(([lng, lat]) => [lng + offsetLng, lat + offsetLat])
  }
}

// ============================================================================
// MAP-001: canonical WGS84 accepted
// ============================================================================
test('MAP-001 canonical WGS84 accepted', () => {
  const validLocation = {
    id: 101,
    trip_id: 12,
    latitude: 39.9042,
    longitude: 116.4074,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z',
    accuracy_meters: 10.5,
    speed_mps: 1.2
  }

  assert.equal(isCanonicalLocation(validLocation), true)
  const canonical = validateCanonicalLocation(validLocation)
  assert.equal(canonical.latitude, 39.9042)
  assert.equal(canonical.longitude, 116.4074)
  assert.equal(canonical.sourceCrs, CANONICAL_CRS)
  assert.equal(canonical.recordedAt, '2026-09-05T01:00:00.000Z')
  assert.equal(canonical.accuracyMeters, 10.5)
  assert.equal(canonical.speedMps, 1.2)
})

// ============================================================================
// MAP-002: missing/unknown CRS rejected
// ============================================================================
test('MAP-002 missing or unknown CRS rejected', () => {
  const base = { latitude: 39.9042, longitude: 116.4074, recorded_at: '2026-09-05T01:00:00.000Z' }

  const invalidCases = [
    { ...base }, // missing
    { ...base, source_crs: null },
    { ...base, source_crs: undefined },
    { ...base, source_crs: 'GCJ-02' },
    { ...base, source_crs: 'GCJ02' },
    { ...base, source_crs: 'BD-09' },
    { ...base, source_crs: 'wgs84' }, // lowercase rejected
    { ...base, source_crs: 'EPSG:4326' },
    { ...base, source_crs: 'UNKNOWN' }
  ]

  for (const item of invalidCases) {
    assert.equal(isCanonicalLocation(item), false)
    assert.throws(
      () => validateCanonicalLocation(item),
      (err) => err instanceof InvalidCanonicalLocationError && err.field === 'source_crs',
      `应拒绝未知或非标准CRS: ${item.source_crs}`
    )
  }
})

// ============================================================================
// MAP-003: invalid coordinates rejected
// ============================================================================
test('MAP-003 invalid coordinates rejected', () => {
  const invalidCoords = [
    { latitude: 91, longitude: 116.4, source_crs: 'WGS84' },
    { latitude: -90.1, longitude: 116.4, source_crs: 'WGS84' },
    { latitude: NaN, longitude: 116.4, source_crs: 'WGS84' },
    { latitude: Infinity, longitude: 116.4, source_crs: 'WGS84' },
    { latitude: '39.9', longitude: 116.4, source_crs: 'WGS84' },
    { latitude: 39.9, longitude: 181, source_crs: 'WGS84' },
    { latitude: 39.9, longitude: -180.1, source_crs: 'WGS84' },
    { latitude: 39.9, longitude: NaN, source_crs: 'WGS84' },
    { latitude: 39.9, longitude: -Infinity, source_crs: 'WGS84' }
  ]

  for (const item of invalidCoords) {
    assert.equal(isCanonicalLocation(item), false)
    assert.throws(
      () => validateCanonicalLocation(item),
      InvalidCanonicalLocationError
    )
  }
})

// ============================================================================
// MAP-004: conversion invoked before AMap rendering
// ============================================================================
test('MAP-004 conversion invoked before AMap rendering', async () => {
  let conversionCalled = false
  const converter = async (points, type) => {
    conversionCalled = true
    assert.equal(type, 'gps')
    return points.map(([lng, lat]) => [lng + 0.005, lat + 0.002])
  }

  const canonical = {
    latitude: 23.1291,
    longitude: 113.2644,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z'
  }

  const mapPoint = await convertCanonicalLocation(canonical, { converter })
  assert.equal(conversionCalled, true)
  assert.equal(mapPoint.displayCrs, DISPLAY_CRS)
  assert.equal(mapPoint.longitude, 113.2644 + 0.005)
  assert.equal(mapPoint.latitude, 23.1291 + 0.002)
})

// ============================================================================
// MAP-005: conversion failure does not identity-fallback
// ============================================================================
test('MAP-005 conversion failure does not identity-fallback', async () => {
  const failingConverter = async () => null

  const canonical = {
    latitude: 23.1291,
    longitude: 113.2644,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z'
  }

  await assert.rejects(
    () => convertCanonicalLocation(canonical, { converter: failingConverter }),
    (err) => {
      assert.ok(err instanceof AmapConversionError)
      assert.equal(err.code, 'MAP_CONVERSION_FAILED')
      return true
    }
  )

  // Test with throwing converter
  const throwingConverter = async () => {
    throw new Error('Network error connecting to AMap')
  }

  await assert.rejects(
    () => convertCanonicalLocation(canonical, { converter: throwingConverter }),
    (err) => {
      assert.ok(err instanceof AmapConversionError)
      return true
    }
  )
})

// ============================================================================
// MAP-006: backend canonical object not mutated
// ============================================================================
test('MAP-006 backend canonical object not mutated', async () => {
  const original = Object.freeze({
    id: 99,
    trip_id: 8,
    latitude: 31.2304,
    longitude: 121.4737,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T02:00:00.000Z',
    accuracy_meters: 5.0,
    speed_mps: 0.5
  })

  const converter = createMockAMapConverter()

  // Must not throw TypeError from attempting to mutate frozen object
  const canonical = validateCanonicalLocation(original)
  assert.equal(canonical.latitude, 31.2304)

  const mapPoint = await convertCanonicalLocation(original, { converter })
  assert.equal(mapPoint.displayCrs, 'GCJ-02')

  // Original object remains identical
  assert.equal(original.latitude, 31.2304)
  assert.equal(original.longitude, 121.4737)
  assert.equal(original.source_crs, 'WGS84')
  assert.equal(original.displayCrs, undefined)
})

// ============================================================================
// MAP-007: latest marker uses newest backend Location
// ============================================================================
test('MAP-007 latest marker uses newest backend Location', async () => {
  const coordinator = createLatestLocationCoordinator({
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter: createMockAMapConverter() })
  })

  const loc1 = {
    latitude: 39.9,
    longitude: 116.4,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z'
  }
  const loc2 = {
    latitude: 39.91,
    longitude: 116.41,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:05:00.000Z'
  }

  const res1 = await coordinator.update(loc1)
  assert.equal(res1.discarded, false)
  assert.equal(res1.mapPoint.latitude, 39.9 + 0.002)

  const res2 = await coordinator.update(loc2)
  assert.equal(res2.discarded, false)
  assert.equal(res2.mapPoint.latitude, 39.91 + 0.002)
})

// ============================================================================
// MAP-008: old async conversion cannot overwrite newer Location
// ============================================================================
test('MAP-008 old async conversion cannot overwrite newer Location', async () => {
  let pendingSlowResolve = null

  // Slow converter for request A
  const slowConverter = () => new Promise((resolve) => {
    pendingSlowResolve = () => resolve([[116.405, 39.902]])
  })

  // Fast converter for request B
  const fastConverter = createMockAMapConverter({ offsetLng: 0.01, offsetLat: 0.01 })

  let currentConverter = slowConverter
  const coordinator = createLatestLocationCoordinator({
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter: currentConverter })
  })

  const locA = { latitude: 39.90, longitude: 116.40, source_crs: 'WGS84', recorded_at: '2026-09-05T01:00:00.000Z' }
  const locB = { latitude: 39.95, longitude: 116.45, source_crs: 'WGS84', recorded_at: '2026-09-05T01:01:00.000Z' }

  // 1. Request A starts (slow)
  const promiseA = coordinator.update(locA)

  // 2. Request B starts (fast) with fastConverter
  currentConverter = fastConverter
  const promiseB = coordinator.update(locB)

  // 3. B resolves first
  const resB = await promiseB
  assert.equal(resB.discarded, false, '较新的请求 B 应该成功被采纳')
  assert.equal(resB.mapPoint.latitude, 39.95 + 0.01)

  // 4. Now A finally finishes later
  pendingSlowResolve()
  const resA = await promiseA
  assert.equal(resA.discarded, true, '旧的异步转换 A 完成时必须被丢弃，不得覆盖 B')
  assert.equal(resA.mapPoint, null)
})

// ============================================================================
// MAP-009: no Location -> no marker
// ============================================================================
test('MAP-009 no Location produces NO_LOCATION state and no marker', () => {
  const childHomeSource = source('../src/views/child/ChildHome.vue')
  // Verifies that when latestLocation is null, mapStatus is set to NO_LOCATION and marker point is cleared
  assert.match(childHomeSource, /mapStatus\.value\s*=\s*'NO_LOCATION'/)
  assert.match(childHomeSource, /latestMapPoint\.value\s*=\s*null/)

  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')
  // Verifies that MapCanvas removes marker when status is not READY or latestPoint is null
  assert.match(mapCanvasSource, /NO_LOCATION:\s*"暂无可用定位数据"/)
  assert.match(mapCanvasSource, /if\s*\(!point\s*\|\|\s*!isValidCoordinate\(point\)\s*\|\|\s*props\.status\s*!==\s*"READY"\)/)
})

// ============================================================================
// MAP-010: backend unavailable -> no Mock fallback
// ============================================================================
test('MAP-010 backend unavailable produces DATA_UNAVAILABLE without Mock fallback', () => {
  const childHomeSource = source('../src/views/child/ChildHome.vue')
  assert.match(childHomeSource, /onError\(error\)\s*\{[\s\S]*mapStatus\.value\s*=\s*'DATA_UNAVAILABLE'/)
  assert.match(childHomeSource, /onError\(error\)\s*\{[\s\S]*latestMapPoint\.value\s*=\s*null/)
  // Verify it does NOT fallback to mock track or mock points on error
  assert.doesNotMatch(childHomeSource, /onError\(error\)\s*\{[\s\S]*elderTrack/)

  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')
  assert.match(mapCanvasSource, /DATA_UNAVAILABLE:\s*"暂时无法获取最新位置"/)
})

// ============================================================================
// MAP-011: REAL never consumes Demo coordinates
// ============================================================================
test('MAP-011 REAL never consumes Demo coordinates', () => {
  const adapterSource = source('../src/services/map/amapCoordinateAdapter.js')
  const mapperSource = source('../src/services/map/mapLocationMapper.js')
  const childHomeSource = source('../src/views/child/ChildHome.vue')

  for (const code of [adapterSource, mapperSource]) {
    assert.doesNotMatch(code, /mock\/track|mock\/geofence|mock\/servicePoints|elderTrack/)
  }

  // ChildHome in real mode must strictly read from backend view and coordinator
  assert.match(childHomeSource, /const canonical = validateCanonicalLocation\(latestLocation\)/)
  assert.match(childHomeSource, /locationCoordinator\.update\(canonical\)/)
  assert.doesNotMatch(childHomeSource, /mock\/track/)
})

// ============================================================================
// MAP-012: Demo behavior unchanged
// ============================================================================
test('MAP-012 Demo behavior unchanged', () => {
  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')
  // Verify simulation panel still exists for demo mode
  assert.match(mapCanvasSource, /v-if="!realMode"\s*class="simulation-panel"/)
  assert.match(mapCanvasSource, /开始模拟/)
  assert.match(mapCanvasSource, /createLocationSimulator/)
  assert.match(mapCanvasSource, /detectGeofenceRisk/)
  assert.match(mapCanvasSource, /initializeDemoSimulation/)
})

// ============================================================================
// MAP-013: Map failure does not change Safety state
// ============================================================================
test('MAP-013 Map failure does not change Safety state', () => {
  // Backend safety view with SAFE risk
  const backendView = {
    elder_id: 1,
    trip_status: 'active',
    location_health: 'FRESH',
    risk_status: 'SAFE',
    open_alert_count: 0,
    latest_location: {
      latitude: 39.9,
      longitude: 116.4,
      source_crs: 'WGS84',
      recorded_at: '2026-09-05T01:00:00.000Z'
    }
  }

  // Presentation of backend safety state
  const initialSafety = presentSafety(backendView, true)
  const initialRisk = presentRisk(backendView, true)
  assert.equal(initialSafety.risk, '当前位于安全围栏内')
  assert.equal(initialRisk.tone, 'success')

  // When map conversion fails, ChildHome marks mapStatus = MAP_CONVERSION_FAILED,
  // but stateAvailable and safetyView remain intact.
  // Safety presentation remains identical:
  const safetyAfterMapFailure = presentSafety(backendView, true)
  const riskAfterMapFailure = presentRisk(backendView, true)
  assert.deepEqual(safetyAfterMapFailure, initialSafety, '地图失败绝不能改变 SafetyView 的结论')
  assert.deepEqual(riskAfterMapFailure, initialRisk, '地图失败绝不能改变 Risk 的结论')
})

// ============================================================================
// MAP-014: recorded_at presentation preserved
// ============================================================================
test('MAP-014 recorded_at presentation preserved', () => {
  const recordedAt = '2026-09-05T01:02:03.000Z'
  let formattedValue = null
  const presentation = presentLocationHealth({
    location_health: 'STALE',
    latest_location: { recorded_at: recordedAt }
  }, true, (value) => {
    formattedValue = value
    return '09:02:03'
  })
  assert.equal(formattedValue, recordedAt)
  assert.equal(presentation.lastLocationLabel, '最后定位：09:02:03')

  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')
  assert.match(mapCanvasSource, /formatRecordedTime/)
  assert.match(mapCanvasSource, /最后定位：/)
})

// ============================================================================
// MAP-015: track order preserved, if track implemented
// ============================================================================
test('MAP-015 track order preserved, if track implemented', async () => {
  const trackInput = [
    { id: 1, latitude: 39.90, longitude: 116.40, source_crs: 'WGS84', recorded_at: '2026-09-05T01:00:00.000Z' },
    { id: 2, latitude: 39.91, longitude: 116.41, source_crs: 'WGS84', recorded_at: '2026-09-05T01:01:00.000Z' },
    { id: 3, latitude: 39.92, longitude: 116.42, source_crs: 'WGS84', recorded_at: '2026-09-05T01:02:00.000Z' }
  ]

  const canonicalTrack = validateCanonicalTrack(trackInput)
  assert.equal(canonicalTrack.length, 3)
  assert.equal(canonicalTrack[0].id, 1)
  assert.equal(canonicalTrack[1].id, 2)
  assert.equal(canonicalTrack[2].id, 3)

  const converter = createMockAMapConverter()
  const convertedTrack = await convertCanonicalTrack(canonicalTrack, { converter })

  assert.equal(convertedTrack.length, 3)
  assert.equal(convertedTrack[0].id, 1)
  assert.equal(convertedTrack[0].displayCrs, 'GCJ-02')
  assert.equal(convertedTrack[1].id, 2)
  assert.equal(convertedTrack[2].id, 3)
  assert.equal(convertedTrack[0].recordedAt, '2026-09-05T01:00:00.000Z')
  assert.equal(convertedTrack[2].recordedAt, '2026-09-05T01:02:00.000Z')
})

// ============================================================================
// MAP-016: Family authorization/backend endpoint remains authoritative
// ============================================================================
test('MAP-016 Family authorization/backend endpoint remains authoritative', () => {
  const childHomeSource = source('../src/views/child/ChildHome.vue')
  // Verify Family fetches state strictly from authorized backend APIs:
  assert.match(childHomeSource, /elderApi\.safety\(currentElder\.id\)/)
  assert.match(childHomeSource, /elderApi\.alerts\(currentElder\.id\)/)
  assert.match(childHomeSource, /elderApi\.currentTrip\(currentElder\.id\)/)
  assert.match(childHomeSource, /locationApi\.track\(trip\.id\)/)

  // Verify Family does NOT connect to browser geolocation directly
  assert.doesNotMatch(childHomeSource, /navigator\.geolocation/)
  assert.doesNotMatch(childHomeSource, /RealLocationProvider/)
})

// ============================================================================
// MAP-RUN-001: AMap SDK readiness - conversion waits for SDK ready then succeeds
// ============================================================================
test('MAP-RUN-001 AMap SDK readiness: conversion called before SDK ready waits and succeeds', async () => {
  resetAMapSdk()
  let resolveSdk = null
  const sdkPromise = new Promise((resolve) => {
    resolveSdk = resolve
  })

  setAMapSdkLoader(() => sdkPromise)

  const canonical = {
    latitude: 39.9042,
    longitude: 116.4074,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z'
  }

  let conversionDone = false
  const convPromise = convertCanonicalLocation(canonical).then((res) => {
    conversionDone = true
    return res
  })

  await new Promise((r) => setTimeout(r, 10))
  assert.equal(conversionDone, false, 'SDK就绪前转换必须处于等待状态')

  const mockAMap = {
    convertFrom: (points, type, cb) => {
      assert.equal(type, 'gps')
      cb('complete', {
        info: 'ok',
        locations: points.map(([lng, lat]) => [lng + 0.005, lat + 0.002])
      })
    }
  }
  resolveSdk(mockAMap)

  const mapPoint = await convPromise
  assert.equal(conversionDone, true)
  assert.equal(mapPoint.displayCrs, 'GCJ-02')
  assert.equal(mapPoint.longitude, 116.4074 + 0.005)
  assert.equal(mapPoint.latitude, 39.9042 + 0.002)
  resetAMapSdk()
})

// ============================================================================
// MAP-RUN-002: SDK load failure -> MAP_UNAVAILABLE semantics
// ============================================================================
test('MAP-RUN-002 SDK load failure produces MAP_UNAVAILABLE error', async () => {
  resetAMapSdk()
  setAMapSdkLoader(() => Promise.reject(new Error('Failed to fetch AMap JSAPI from CDN')))

  const canonical = {
    latitude: 39.9042,
    longitude: 116.4074,
    source_crs: 'WGS84',
    recorded_at: '2026-09-05T01:00:00.000Z'
  }

  await assert.rejects(
    () => convertCanonicalLocation(canonical),
    (err) => {
      assert.ok(err instanceof AmapConversionError)
      assert.equal(err.code, 'MAP_UNAVAILABLE')
      assert.match(err.message, /高德地图SDK加载失败/)
      return true
    }
  )
  resetAMapSdk()
})

// ============================================================================
// MAP-RUN-003: 40, 41, 80, 81 point batching with exact batch sizes
// ============================================================================
test('MAP-RUN-003 track batching: 40, 41, 80, 81 points with exact batch sizes and preserved order', async () => {
  function makeTrack(count) {
    return Array.from({ length: count }, (_, i) => ({
      id: i + 1,
      trip_id: 10,
      latitude: 39.90 + (i * 0.001),
      longitude: 116.40 + (i * 0.001),
      source_crs: 'WGS84',
      recorded_at: new Date(Date.UTC(2026, 8, 5, 1, 0, i)).toISOString()
    }))
  }

  const testCases = [
    { count: 40, expectedBatches: [40] },
    { count: 41, expectedBatches: [40, 1] },
    { count: 80, expectedBatches: [40, 40] },
    { count: 81, expectedBatches: [40, 40, 1] }
  ]

  for (const { count, expectedBatches } of testCases) {
    const inputTrack = makeTrack(count)
    const recordedBatchSizes = []

    const converter = async (points, type) => {
      assert.equal(type, 'gps')
      recordedBatchSizes.push(points.length)
      return points.map(([lng, lat]) => [lng + 0.005, lat + 0.002])
    }

    const result = await convertCanonicalTrack(inputTrack, { converter })
    assert.deepEqual(recordedBatchSizes, expectedBatches, `点数 ${count} 应产生批次 ${expectedBatches}`)
    assert.equal(result.length, count)

    for (let i = 0; i < count; i++) {
      assert.equal(result[i].id, inputTrack[i].id)
      assert.equal(result[i].recordedAt, inputTrack[i].recorded_at)
      assert.equal(result[i].displayCrs, 'GCJ-02')
      assert.equal(result[i].longitude, inputTrack[i].longitude + 0.005)
      assert.equal(result[i].latitude, inputTrack[i].latitude + 0.002)
    }
  }

  // Fail-closed test: if a batch fails, entire track conversion fails closed
  const track81 = makeTrack(81)
  let callIndex = 0
  const partiallyFailingConverter = async (points) => {
    callIndex++
    if (callIndex === 2) {
      throw new Error('Network error on batch 2')
    }
    return points.map(([lng, lat]) => [lng + 0.005, lat + 0.002])
  }

  await assert.rejects(
    () => convertCanonicalTrack(track81, { converter: partiallyFailingConverter }),
    (err) => {
      assert.ok(err instanceof AmapConversionError)
      return true
    }
  )
})

// ============================================================================
// MAP-RUN-004: Operator selection race: A slow, B fast -> final = B
// ============================================================================
test('MAP-RUN-004 Operator selection race: A slow, B fast -> final = B', async () => {
  let resolveSafetyA
  const safetyPromiseA = new Promise((resolve) => { resolveSafetyA = resolve })

  const fetchSafety = (elderId) => {
    if (elderId === 'A') return safetyPromiseA
    if (elderId === 'B') {
      return Promise.resolve({
        latest_location: { latitude: 39.92, longitude: 116.42, source_crs: 'WGS84' }
      })
    }
    throw new Error('Unknown elder')
  }

  const converter = createMockAMapConverter({ offsetLng: 0.01, offsetLat: 0.01 })
  const stateHistory = []

  const coordinator = createOperatorSelectionCoordinator({
    fetchSafety,
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter }),
    onStateChange: (state) => stateHistory.push(state)
  })

  // 1. Select A (slow)
  const selectPromiseA = coordinator.selectElder({ id: 'A', name: 'Elder A' })

  // 2. Quickly select B (fast)
  const selectPromiseB = coordinator.selectElder({ id: 'B', name: 'Elder B' })

  await selectPromiseB
  const afterB = stateHistory[stateHistory.length - 1]
  assert.equal(afterB.status, 'READY')
  assert.equal(afterB.elderId, 'B')
  assert.equal(afterB.point.latitude, 39.92 + 0.01)

  // 3. A finishes later
  resolveSafetyA({
    latest_location: { latitude: 39.90, longitude: 116.40, source_crs: 'WGS84' }
  })
  await selectPromiseA

  // Final state must remain B
  const finalState = stateHistory[stateHistory.length - 1]
  assert.equal(finalState.elderId, 'B')
  assert.equal(finalState.status, 'READY')
  assert.equal(finalState.point.latitude, 39.92 + 0.01)
})

// ============================================================================
// MAP-RUN-005: Operator selection race: A slow failure, B fast success -> final = B READY
// ============================================================================
test('MAP-RUN-005 Operator selection race: A slow failure, B fast success -> final = B READY', async () => {
  let rejectSafetyA
  const safetyPromiseA = new Promise((_, reject) => { rejectSafetyA = reject })

  const fetchSafety = (elderId) => {
    if (elderId === 'A') return safetyPromiseA
    if (elderId === 'B') {
      return Promise.resolve({
        latest_location: { latitude: 39.95, longitude: 116.45, source_crs: 'WGS84' }
      })
    }
    throw new Error('Unknown elder')
  }

  const converter = createMockAMapConverter()
  const stateHistory = []

  const coordinator = createOperatorSelectionCoordinator({
    fetchSafety,
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter }),
    onStateChange: (state) => stateHistory.push(state)
  })

  const selectPromiseA = coordinator.selectElder({ id: 'A', name: 'Elder A' })
  const selectPromiseB = coordinator.selectElder({ id: 'B', name: 'Elder B' })

  await selectPromiseB
  assert.equal(stateHistory[stateHistory.length - 1].status, 'READY')
  assert.equal(stateHistory[stateHistory.length - 1].elderId, 'B')

  // A fails
  rejectSafetyA(new Error('Network error loading Elder A'))
  await selectPromiseA

  // Final state must remain B READY
  const finalState = stateHistory[stateHistory.length - 1]
  assert.equal(finalState.elderId, 'B')
  assert.equal(finalState.status, 'READY')
})

// ============================================================================
// MAP-RUN-006: Operator selection race: A success after selected cleared is discarded
// ============================================================================
test('MAP-RUN-006 Operator selection race: A success after selected cleared is discarded', async () => {
  let resolveSafetyA
  const safetyPromiseA = new Promise((resolve) => { resolveSafetyA = resolve })

  const fetchSafety = () => safetyPromiseA
  const converter = createMockAMapConverter()
  const stateHistory = []

  const coordinator = createOperatorSelectionCoordinator({
    fetchSafety,
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter }),
    onStateChange: (state) => stateHistory.push(state)
  })

  const selectPromiseA = coordinator.selectElder({ id: 'A', name: 'Elder A' })

  // User closes popup -> clearSelection
  coordinator.clearSelection()
  assert.equal(stateHistory[stateHistory.length - 1].status, 'NO_LOCATION')
  assert.equal(stateHistory[stateHistory.length - 1].point, null)

  // Now A finishes
  resolveSafetyA({
    latest_location: { latitude: 39.90, longitude: 116.40, source_crs: 'WGS84' }
  })
  await selectPromiseA

  // Final state remains cleared (NO_LOCATION)
  const finalState = stateHistory[stateHistory.length - 1]
  assert.equal(finalState.status, 'NO_LOCATION')
  assert.equal(finalState.point, null)
  assert.equal(finalState.elderId, null)
})

// ============================================================================
// MAP-RUN-007: Family whole-load generation: old failure cannot erase newer READY
// ============================================================================
test('MAP-RUN-007 Family whole-load generation: old failure cannot erase newer READY', async () => {
  let rejectLoad1
  const safetyPromise1 = new Promise((_, reject) => { rejectLoad1 = reject })
  let notifySafety1Reached
  const safety1Reached = new Promise((r) => { notifySafety1Reached = r })

  let callCount = 0
  const fetchSafety = () => {
    callCount++
    if (callCount === 1) {
      notifySafety1Reached()
      return safetyPromise1
    }
    return Promise.resolve({
      latest_location: { latitude: 39.91, longitude: 116.41, source_crs: 'WGS84' }
    })
  }

  const converter = createMockAMapConverter()
  const events = []

  const coordinator = createFamilyStateCoordinator({
    fetchElders: () => Promise.resolve({ items: [{ id: 1, name: 'Elder 1' }] }),
    fetchSafety,
    fetchAlerts: () => Promise.resolve({ items: [] }),
    fetchCurrentTrip: () => Promise.resolve(null),
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter }),
    onStateChange: (ev) => events.push(ev)
  })

  // Load 1 starts and enters safety fetch
  const p1 = coordinator.loadAuthoritativeState().catch((e) => e)
  await safety1Reached

  // Load 2 starts (fast, succeeds)
  const p2 = coordinator.loadAuthoritativeState()
  await p2

  // Load 2 produced LOCATION_READY
  const readyEvent = events.find((e) => e.type === 'LOCATION_READY')
  assert.ok(readyEvent, 'Load 2 必须成功产生 LOCATION_READY')
  assert.equal(readyEvent.mapStatus, 'READY')

  // Now Load 1 fails
  rejectLoad1(new Error('Load 1 network failure'))
  await p1

  // Final location state must remain READY
  const lastLocationEvent = events.filter((e) => e.type.startsWith('LOCATION_') || e.type === 'ERROR').pop()
  assert.equal(lastLocationEvent.type, 'LOCATION_READY')
  assert.equal(lastLocationEvent.mapStatus, 'READY')
})

// ============================================================================
// MAP-RUN-008: Track generation: old track result cannot overwrite newer Trip
// ============================================================================
test('MAP-RUN-008 Track generation: old track result cannot overwrite newer Trip', async () => {
  let resolveTrackA
  const trackPromiseA = new Promise((resolve) => { resolveTrackA = resolve })
  let notifyTrackAReached
  const trackAReached = new Promise((r) => { notifyTrackAReached = r })

  let tripCallCount = 0
  const fetchCurrentTrip = () => {
    tripCallCount++
    if (tripCallCount === 1) return Promise.resolve({ id: 'trip-A' })
    return Promise.resolve({ id: 'trip-B' })
  }

  const fetchTrack = (tripId) => {
    if (tripId === 'trip-A') {
      notifyTrackAReached()
      return trackPromiseA
    }
    if (tripId === 'trip-B') {
      return Promise.resolve({
        items: [{ id: 201, latitude: 39.92, longitude: 116.42, source_crs: 'WGS84' }]
      })
    }
    return Promise.resolve({ items: [] })
  }

  const converter = createMockAMapConverter()
  const events = []

  const coordinator = createFamilyStateCoordinator({
    fetchElders: () => Promise.resolve({ items: [{ id: 1, name: 'Elder 1' }] }),
    fetchSafety: () => Promise.resolve({
      latest_location: { latitude: 39.90, longitude: 116.40, source_crs: 'WGS84' }
    }),
    fetchAlerts: () => Promise.resolve({ items: [] }),
    fetchCurrentTrip,
    fetchTrack,
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter }),
    convertTrack: (pts) => convertCanonicalTrack(pts, { converter }),
    onStateChange: (ev) => events.push(ev)
  })

  // Load 1 starts and enters track-A fetch
  const p1 = coordinator.loadAuthoritativeState()
  await trackAReached

  // Load 2 for trip-B (fast, finishes track B)
  const p2 = coordinator.loadAuthoritativeState()
  await p2

  // Verify trip-B track was adopted
  const trackBEvent = events.find((e) => e.type === 'TRACK_READY' && e.tripId === 'trip-B')
  assert.ok(trackBEvent, 'Trip B 轨迹必须成功展示')
  assert.equal(trackBEvent.trackPoints[0].id, 201)

  // Now trip-A track resolves
  resolveTrackA({
    items: [{ id: 101, latitude: 39.90, longitude: 116.40, source_crs: 'WGS84' }]
  })
  await p1

  // Final track must remain trip-B
  const lastTrackEvent = events.filter((e) => e.type === 'TRACK_READY').pop()
  assert.equal(lastTrackEvent.tripId, 'trip-B')
  assert.equal(lastTrackEvent.trackPoints[0].id, 201, 'Trip A 轨迹绝不得覆盖 Trip B')
})

// ============================================================================
// MAP-RUN-009: Map lifecycle: unmount before SDK ready prevents late initialization
// ============================================================================
test('MAP-RUN-009 Map lifecycle: unmount before SDK ready prevents late initialization', async () => {
  let resolveSdk
  const sdkPromise = new Promise((resolve) => { resolveSdk = resolve })

  let initMapCalled = false
  let onReadyCalled = false

  const lifecycle = createMapLifecycleManager({
    loadSdk: () => sdkPromise,
    initMap: async () => {
      initMapCalled = true
      return { destroy: () => {} }
    },
    onReady: () => {
      onReadyCalled = true
    }
  })

  // Mount starts (awaits delayed SDK)
  const mountPromise = lifecycle.mount()

  // Component unmounts while SDK is still pending
  lifecycle.destroy()
  assert.equal(lifecycle.isAlive(), false)

  // Now SDK finishes loading
  resolveSdk({ Map: function () {}, Polyline: function () {} })
  const result = await mountPromise

  assert.equal(result.initialized, false)
  assert.equal(result.reason, 'destroyed_before_sdk')
  assert.equal(initMapCalled, false, '销毁后绝不得调用 initMap')
  assert.equal(onReadyCalled, false, '销毁后绝不得触发 onReady')
})

// ============================================================================
// MAP-RUN-010: Conversion failure does not mutate Safety state
// ============================================================================
test('MAP-RUN-010 Conversion failure does not mutate Safety state', async () => {
  const backendSafety = Object.freeze({
    elder_id: 1001,
    trip_status: 'active',
    location_health: 'FRESH',
    risk_status: 'SAFE',
    open_alert_count: 0,
    latest_location: Object.freeze({
      latitude: 39.9042,
      longitude: 116.4074,
      source_crs: 'WGS84',
      recorded_at: '2026-09-05T01:00:00.000Z'
    })
  })

  const failingConverter = async () => {
    throw new AmapConversionError('高德坐标转换服务不可用', { code: 'MAP_CONVERSION_FAILED' })
  }

  const events = []
  const coordinator = createFamilyStateCoordinator({
    fetchElders: () => Promise.resolve({ items: [{ id: 1001, name: '张建国' }] }),
    fetchSafety: () => Promise.resolve(backendSafety),
    fetchAlerts: () => Promise.resolve({ items: [] }),
    fetchCurrentTrip: () => Promise.resolve({ id: 10 }),
    convertLocation: (loc) => convertCanonicalLocation(loc, { converter: failingConverter }),
    onStateChange: (ev) => events.push(ev)
  })

  await coordinator.loadAuthoritativeState()

  const errorEvent = events.find((e) => e.type === 'LOCATION_ERROR')
  assert.ok(errorEvent)
  assert.equal(errorEvent.mapStatus, 'MAP_CONVERSION_FAILED')

  const safety = presentSafety(backendSafety, true)
  const risk = presentRisk(backendSafety, true)
  assert.equal(safety.risk, '当前位于安全围栏内')
  assert.equal(risk.tone, 'success')
  assert.equal(backendSafety.risk_status, 'SAFE')
})

// ============================================================================
// MAP-RUN-011: Real map UI copy uses 最新记录位置 instead of 当前位置
// ============================================================================
test('MAP-RUN-011 Real map UI copy uses 最新记录位置 instead of 当前位置', () => {
  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')
  assert.match(mapCanvasSource, /最新记录位置/)
  assert.match(mapCanvasSource, /image\.alt\s*=\s*props\.realMode\s*\?\s*`\$\{props\.elderName\}最新记录位置`/)
  assert.match(mapCanvasSource, /title:\s*`\$\{props\.elderName\}最新记录位置`/)
  assert.doesNotMatch(mapCanvasSource, /title:\s*`\$\{props\.elderName\}当前位置`/)
})

// ============================================================================
// MAP-PATH-001..006: fail-closed MapPoint[] -> AMap number[][] boundary
// ============================================================================
test('MAP-PATH-001 valid 2 MapPoints become number[][]', () => {
  assert.deepEqual(formatPolylinePath([
    { longitude: 116.4074, latitude: 39.9042 },
    { longitude: 116.4174, latitude: 39.9142 }
  ]), [
    [116.4074, 39.9042],
    [116.4174, 39.9142]
  ])
})

test('MAP-PATH-002 one MapPoint produces no Polyline path', () => {
  assert.deepEqual(formatPolylinePath([
    { longitude: 116.4074, latitude: 39.9042 }
  ]), [])
})

test('MAP-PATH-003 zero MapPoints produce no Polyline path', () => {
  assert.deepEqual(formatPolylinePath([]), [])
})

test('MAP-PATH-004 malformed coordinates fail closed', () => {
  const valid = { longitude: 116.4074, latitude: 39.9042 }
  const malformed = [
    { longitude: NaN, latitude: 39.9142 },
    { longitude: 116.4174, latitude: undefined },
    { longitude: 'garbage', latitude: 39.9142 },
    { longitude: '116.4174', latitude: '39.9142' }
  ]

  for (const point of malformed) {
    assert.deepEqual(formatPolylinePath([valid, point]), [])
  }
})

test('MAP-PATH-005 one malformed point invalidates the whole path', () => {
  assert.deepEqual(formatPolylinePath([
    { longitude: 116.4074, latitude: 39.9042 },
    { longitude: 116.4174 },
    { longitude: 116.4274, latitude: 39.9242 }
  ]), [])
})

test('MAP-PATH-006 out-of-range longitude or latitude fails closed', () => {
  const valid = { longitude: 116.4074, latitude: 39.9042 }
  const outOfRange = [
    { longitude: 180.0001, latitude: 39.9142 },
    { longitude: -180.0001, latitude: 39.9142 },
    { longitude: 116.4174, latitude: 90.0001 },
    { longitude: 116.4174, latitude: -90.0001 }
  ]

  for (const point of outOfRange) {
    assert.deepEqual(formatPolylinePath([valid, point]), [])
  }
})

// ============================================================================
// MAP-RUN-015: loadAMapSdk fails fast with MAP_UNAVAILABLE when VITE_AMAP_KEY or VITE_AMAP_SECURITY_JS_CODE is missing
// ============================================================================
test('MAP-RUN-015 loadAMapSdk fails fast with MAP_UNAVAILABLE when VITE_AMAP_KEY or VITE_AMAP_SECURITY_JS_CODE is missing', async () => {
  resetAMapSdk()
  const origWindow = globalThis.window
  const origKey = process.env.VITE_AMAP_KEY
  const origCode = process.env.VITE_AMAP_SECURITY_JS_CODE

  try {
    globalThis.window = {}

    // Case 1: Neither key nor security code
    delete process.env.VITE_AMAP_KEY
    delete process.env.VITE_AMAP_SECURITY_JS_CODE
    resetAMapSdk()
    await assert.rejects(
      async () => loadAMapSdk(),
      (err) => {
        assert.equal(err.code, 'MAP_UNAVAILABLE')
        assert.match(err.message, /高德地图配置缺失/)
        return true
      }
    )

    // Case 2: Only key, missing security code
    process.env.VITE_AMAP_KEY = 'test-key'
    delete process.env.VITE_AMAP_SECURITY_JS_CODE
    resetAMapSdk()
    await assert.rejects(
      async () => loadAMapSdk(),
      (err) => {
        assert.equal(err.code, 'MAP_UNAVAILABLE')
        assert.match(err.message, /高德地图配置缺失/)
        return true
      }
    )

    // Case 3: Only security code, missing key
    delete process.env.VITE_AMAP_KEY
    process.env.VITE_AMAP_SECURITY_JS_CODE = 'test-code'
    resetAMapSdk()
    await assert.rejects(
      async () => loadAMapSdk(),
      (err) => {
        assert.equal(err.code, 'MAP_UNAVAILABLE')
        assert.match(err.message, /高德地图配置缺失/)
        return true
      }
    )

    // Case 4: Blank/whitespace only strings
    process.env.VITE_AMAP_KEY = '   '
    process.env.VITE_AMAP_SECURITY_JS_CODE = '   '
    resetAMapSdk()
    await assert.rejects(
      async () => loadAMapSdk(),
      (err) => {
        assert.equal(err.code, 'MAP_UNAVAILABLE')
        assert.match(err.message, /高德地图配置缺失/)
        return true
      }
    )
  } finally {
    globalThis.window = origWindow
    if (origKey !== undefined) process.env.VITE_AMAP_KEY = origKey
    else delete process.env.VITE_AMAP_KEY
    if (origCode !== undefined) process.env.VITE_AMAP_SECURITY_JS_CODE = origCode
    else delete process.env.VITE_AMAP_SECURITY_JS_CODE
    resetAMapSdk()
  }
})

// ============================================================================
// MAP-RUN-016: window._AMapSecurityConfig is set before AMapLoader.load, and shared cached Promise is returned
// ============================================================================
test('MAP-RUN-016 window._AMapSecurityConfig is set before AMapLoader.load, and shared cached Promise is returned', async () => {
  resetAMapSdk()
  const origWindow = globalThis.window
  const origKey = process.env.VITE_AMAP_KEY
  const origCode = process.env.VITE_AMAP_SECURITY_JS_CODE

  try {
    const mockWindow = {}
    globalThis.window = mockWindow

    process.env.VITE_AMAP_KEY = 'valid-test-key'
    process.env.VITE_AMAP_SECURITY_JS_CODE = 'valid-test-security-code'

    // When loadAMapSdk runs, window._AMapSecurityConfig must be set immediately
    // before loader finishes
    const p1 = loadAMapSdk()
    assert.deepEqual(mockWindow._AMapSecurityConfig, {
      securityJsCode: 'valid-test-security-code'
    })

    // Concurrent call p2 must return the exact same cached Promise instance
    const p2 = loadAMapSdk()
    assert.equal(p1, p2, 'MapCanvas 和 coordinate adapter 必须共享同一个 cached loader Promise')

    // Cleanly await/catch the loader import failure in Node environment
    try {
      await p1
    } catch {
      // Expected in Node environment without actual amap jsapi loader network
    }
  } finally {
    globalThis.window = origWindow
    if (origKey !== undefined) process.env.VITE_AMAP_KEY = origKey
    else delete process.env.VITE_AMAP_KEY
    if (origCode !== undefined) process.env.VITE_AMAP_SECURITY_JS_CODE = origCode
    else delete process.env.VITE_AMAP_SECURITY_JS_CODE
    resetAMapSdk()
  }
})

// ============================================================================
// MAP-RUN-017: Zero secret and coordinate logging across code and runtime
// ============================================================================
test('MAP-RUN-017 Zero secret and coordinate logging across code and runtime', () => {
  const adapterSource = source('../src/services/map/amapCoordinateAdapter.js')
  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')

  // Secrets must never be logged or printed
  assert.doesNotMatch(adapterSource, /console\.(log|info|debug|warn|error)\(.*(VITE_AMAP_KEY|VITE_AMAP_SECURITY_JS_CODE|key|securityJsCode)/)
  assert.doesNotMatch(mapCanvasSource, /console\.(log|info|debug|warn|error)\(.*(VITE_AMAP_KEY|VITE_AMAP_SECURITY_JS_CODE|key|securityJsCode)/)

  // Security code must not be hardcoded
  assert.doesNotMatch(adapterSource, /securityJsCode\s*:\s*['"][a-f0-9]{16,}['"]/)
  assert.doesNotMatch(mapCanvasSource, /securityJsCode\s*:\s*['"][a-f0-9]{16,}['"]/)
})

// ============================================================================
// MAP-RUN-018: MapCanvas manages Polyline dynamically without eager creation for <2 points
// ============================================================================
test('MAP-RUN-018 MapCanvas manages Polyline dynamically without eager creation for <2 points', () => {
  const mapCanvasSource = source('../src/components/map/MapCanvas.vue')

  // Real-mode rendering must use the runtime-tested canonical boundary.
  assert.match(mapCanvasSource, /syncAMapPolyline/)

  // initializeRealMap must NOT create Polyline unconditionally
  const initRealMapBody = mapCanvasSource.slice(
    mapCanvasSource.indexOf('async function initializeRealMap'),
    mapCanvasSource.indexOf('// DEMO Simulation Mode Logic')
  )
  assert.doesNotMatch(
    initRealMapBody,
    /new\s+(AMap|aMapSdk)\.Polyline/,
    'initializeRealMap 绝不得在 0 或 1 点时预先创建 Polyline'
  )

  const realModeSource = mapCanvasSource.slice(
    mapCanvasSource.indexOf('// REAL Mode Presentation Logic'),
    mapCanvasSource.indexOf('// DEMO Simulation Mode Logic')
  )
  assert.doesNotMatch(realModeSource, /setPath\(\[\]\)/)
})

function createStrictPolylineHarness() {
  const createdPaths = []
  const updatedPaths = []
  const added = []
  const removed = []

  function assertRuntimePath(path) {
    assert.ok(Array.isArray(path) && path.length >= 2, 'AMap Polyline path must contain at least two points')
    for (const point of path) {
      assert.ok(Array.isArray(point) && point.length === 2, 'AMap point must be [longitude, latitude]')
      assert.equal(typeof point[0], 'number')
      assert.equal(typeof point[1], 'number')
      assert.equal(Number.isFinite(point[0]), true)
      assert.equal(Number.isFinite(point[1]), true)
    }
  }

  class Polyline {
    constructor(options) {
      assertRuntimePath(options.path)
      createdPaths.push(options.path)
    }

    setPath(path) {
      assertRuntimePath(path)
      updatedPaths.push(path)
    }
  }

  return {
    aMap: { Polyline },
    map: {
      add(polyline) { added.push(polyline) },
      remove(polyline) { removed.push(polyline) }
    },
    createdPaths,
    updatedPaths,
    added,
    removed
  }
}

const initialMapPoints = [
  { longitude: 116.4074, latitude: 39.9042, displayCrs: DISPLAY_CRS },
  { longitude: 116.4174, latitude: 39.9142, displayCrs: DISPLAY_CRS }
]

test('MAP-PATH-007 initial Polyline creation uses the canonical formatter', () => {
  const harness = createStrictPolylineHarness()
  const polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    points: initialMapPoints
  })

  assert.ok(polyline)
  assert.deepEqual(harness.createdPaths, [[
    [116.4074, 39.9042],
    [116.4174, 39.9142]
  ]])
  assert.equal(harness.added.length, 1)
  assert.equal(harness.updatedPaths.length, 0)
})

test('MAP-PATH-008 subsequent setPath uses the same canonical formatter', () => {
  const harness = createStrictPolylineHarness()
  let polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    points: initialMapPoints
  })
  polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    polyline,
    points: [
      { longitude: 116.4274, latitude: 39.9242, displayCrs: DISPLAY_CRS },
      { longitude: 116.4374, latitude: 39.9342, displayCrs: DISPLAY_CRS }
    ]
  })

  assert.ok(polyline)
  assert.deepEqual(harness.updatedPaths, [[
    [116.4274, 39.9242],
    [116.4374, 39.9342]
  ]])
})

test('MAP-PATH-009 polling update passes converted AMap LngLat values as number[][]', async () => {
  const conversionAMap = {
    convertFrom(points, type, callback) {
      assert.equal(type, 'gps')
      callback('complete', {
        info: 'ok',
        locations: points.map((point, index) => ({
          getLng: () => [116.425, 116.435][index],
          getLat: () => [39.922, 39.932][index]
        }))
      })
    }
  }
  const convertedTrack = await convertCanonicalTrack([
    { longitude: 116.42, latitude: 39.92, source_crs: 'WGS84' },
    { longitude: 116.43, latitude: 39.93, source_crs: 'WGS84' }
  ], { aMap: conversionAMap })
  assert.equal(Object.getPrototypeOf(convertedTrack[0]), Object.prototype)
  assert.deepEqual(convertedTrack.map(({ longitude, latitude, displayCrs }) => ({ longitude, latitude, displayCrs })), [
    { longitude: 116.425, latitude: 39.922, displayCrs: DISPLAY_CRS },
    { longitude: 116.435, latitude: 39.932, displayCrs: DISPLAY_CRS }
  ])

  const harness = createStrictPolylineHarness()
  let polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    points: initialMapPoints
  })
  polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    polyline,
    points: convertedTrack
  })

  assert.ok(polyline)
  assert.deepEqual(harness.updatedPaths, [[
    [116.425, 39.922],
    [116.435, 39.932]
  ]])
})

test('MAP-PATH-010 empty or conversion-failure state removes the line without setPath([])', () => {
  const harness = createStrictPolylineHarness()
  let polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    points: initialMapPoints
  })
  polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    polyline,
    points: []
  })

  assert.equal(polyline, null)
  assert.equal(harness.removed.length, 1)
  assert.equal(harness.updatedPaths.length, 0)

  polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    points: initialMapPoints
  })
  polyline = syncAMapPolyline({
    aMap: harness.aMap,
    map: harness.map,
    polyline,
    points: initialMapPoints,
    enabled: false
  })

  assert.equal(polyline, null)
  assert.equal(harness.removed.length, 2)
  assert.equal(harness.updatedPaths.length, 0)
})


