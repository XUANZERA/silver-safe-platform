import assert from 'node:assert/strict'
import test from 'node:test'

import { createOperatorSelectionCoordinator } from '../src/services/map/amapCoordinateAdapter.js'
import { presentLocationHealth, presentRisk } from '../src/services/safetyPresentation.js'

function view(locationHealth, recordedAt = '2026-09-05T01:02:03.000Z') {
  return {
    trip_status: 'active',
    location_health: locationHealth,
    risk_status: null,
    latest_location: recordedAt
      ? {
          id: 9,
          latitude: 23.1291,
          longitude: 113.2644,
          source_crs: 'WGS84',
          recorded_at: recordedAt
        }
      : null
  }
}

test('FRESH-FE-001 STALE uses the authoritative stale warning', () => {
  const staleView = { ...view('STALE'), risk_status: 'SAFE' }
  const result = presentLocationHealth(staleView, true, () => '09:02:03')

  assert.equal(result.label, '定位较久未更新')
  assert.equal(result.tone, 'warning')
  assert.equal(result.isStale, true)
  assert.equal(presentRisk(staleView).tone, 'neutral')
})

test('FRESH-FE-002 NO_DATA uses the no-location message', () => {
  const result = presentLocationHealth(view('NO_DATA', null))

  assert.equal(result.label, '暂无定位数据')
  assert.equal(result.markerLabel, '暂无定位数据')
  assert.equal(result.showMarker, false)
})

test('FRESH-FE-003 FRESH uses normal-location wording', () => {
  const result = presentLocationHealth(view('FRESH'))

  assert.equal(result.label, '定位正常')
  assert.equal(result.tone, 'success')
})

test('FRESH-FE-004 INACCURATE preserves the existing accuracy warning', () => {
  const result = presentLocationHealth(view('INACCURATE'))

  assert.equal(result.label, '定位精度不足')
  assert.equal(result.tone, 'warning')
})

test('FRESH-FE-005 STALE preserves the latest recorded marker context', () => {
  const result = presentLocationHealth(view('STALE'))

  assert.equal(result.showMarker, true)
  assert.equal(result.markerLabel, '最新记录位置')
})

test('FRESH-FE-006 STALE reports recordedAt truthfully', () => {
  const recordedAt = '2026-09-05T01:02:03.000Z'
  let formattedValue = null
  const result = presentLocationHealth(view('STALE', recordedAt), true, (value) => {
    formattedValue = value
    return '09:02:03'
  })

  assert.equal(formattedValue, recordedAt)
  assert.equal(result.lastLocationLabel, '最后定位：09:02:03')
  assert.equal(result.recordedAtText, '09:02:03')
  assert.equal(result.markerLabel, '最新记录位置')
  assert.doesNotMatch(`${result.markerLabel}${result.lastLocationLabel}`, /当前位置|实时位置/)
})

test('FRESH-FE-007 operator map failure keeps backend STALE state', async () => {
  const backendView = view('STALE')
  const states = []
  const coordinator = createOperatorSelectionCoordinator({
    fetchSafety: async () => backendView,
    validateLocation: (location) => location,
    convertLocation: async () => {
      throw Object.assign(new Error('map unavailable'), { code: 'MAP_UNAVAILABLE' })
    },
    onStateChange: (state) => states.push(state)
  })

  await coordinator.selectElder({ id: 1, name: '测试老人' })

  const finalState = states.at(-1)
  assert.equal(finalState.status, 'MAP_UNAVAILABLE')
  assert.equal(finalState.safetyView, backendView)
  assert.equal(presentLocationHealth(finalState.safetyView).label, '定位较久未更新')
})

test('FRESH-FE-008 presentation never derives freshness from local time', () => {
  const originalDateNow = Date.now
  Date.now = () => {
    throw new Error('frontend freshness calculation is forbidden')
  }
  try {
    const ancientButBackendFresh = presentLocationHealth(view('FRESH', '2000-01-01T00:00:00Z'))
    const futureButBackendStale = presentLocationHealth(view('STALE', '2099-01-01T00:00:00Z'))

    assert.equal(ancientButBackendFresh.label, '定位正常')
    assert.equal(futureButBackendStale.label, '定位较久未更新')
  } finally {
    Date.now = originalDateNow
  }
})
