'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { presentSafetyView, wgs84ToGcj02 } = require('../services/map')

test('family presentation displays Backend statuses and recorded_at without recalculation', () => {
  const oldRecordedAt = '2020-01-01T00:00:00Z'
  const presented = presentSafetyView({
    location_health: 'FRESH',
    risk_status: 'SAFE',
    latest_location: {
      latitude: 39.9,
      longitude: 116.4,
      source_crs: 'WGS84',
      recorded_at: oldRecordedAt
    }
  })

  // 即使时间很早，客户端也不重算 freshness，Backend 的 FRESH 保持不变。
  assert.equal(presented.locationHealth, 'FRESH')
  assert.equal(presented.locationHealthText, '定位正常')
  assert.equal(presented.riskStatus, 'SAFE')
  assert.equal(presented.riskStatusText, '安全')
  assert.equal(presented.recordedAt, oldRecordedAt)
  assert.equal(presented.latitude, 39.9)
  assert.equal(presented.longitude, 116.4)
  assert.equal(presented.hasLocation, true)
})

test('map coordinate adapter leaves locations outside mainland China unchanged', () => {
  assert.deepEqual(wgs84ToGcj02(51.5074, -0.1278), {
    latitude: 51.5074,
    longitude: -0.1278
  })
})

test('non-WGS84 Safety locations are not guessed or displayed on the map', () => {
  const presented = presentSafetyView({
    location_health: 'STALE',
    latest_location: {
      latitude: 39.9,
      longitude: 116.4,
      source_crs: 'GCJ02',
      recorded_at: '2026-09-05T01:02:03Z'
    }
  })

  assert.equal(presented.locationHealth, 'STALE')
  assert.equal(presented.locationHealthText, '定位信息较久未更新')
  assert.equal(presented.hasLocation, false)
  assert.deepEqual(presented.circles, [])
})
