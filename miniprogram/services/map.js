'use strict'

const PI = Math.PI
const EARTH_SEMI_MAJOR_AXIS = 6378245
const ECCENTRICITY_SQUARED = 0.006693421622965943

const LOCATION_HEALTH_TEXT = Object.freeze({
  NO_DATA: '暂无定位信息',
  FRESH: '定位正常',
  STALE: '定位信息较久未更新',
  INACCURATE: '定位精度较低'
})

const RISK_STATUS_TEXT = Object.freeze({
  SAFE: '安全',
  PENDING: '状态确认中',
  ALERT: '请关注'
})

function outsideMainlandChina(latitude, longitude) {
  return longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271
}

function transformLatitude(x, y) {
  let result = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  result += (20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2 / 3
  result += (20 * Math.sin(y * PI) + 40 * Math.sin(y / 3 * PI)) * 2 / 3
  result += (160 * Math.sin(y / 12 * PI) + 320 * Math.sin(y * PI / 30)) * 2 / 3
  return result
}

function transformLongitude(x, y) {
  let result = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  result += (20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2 / 3
  result += (20 * Math.sin(x * PI) + 40 * Math.sin(x / 3 * PI)) * 2 / 3
  result += (150 * Math.sin(x / 12 * PI) + 300 * Math.sin(x / 30 * PI)) * 2 / 3
  return result
}

// 微信 map 使用 GCJ-02；此函数只做地图坐标适配，不改变 Backend Safety View。
function wgs84ToGcj02(latitude, longitude) {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (outsideMainlandChina(latitude, longitude)) return { latitude, longitude }

  let deltaLatitude = transformLatitude(longitude - 105, latitude - 35)
  let deltaLongitude = transformLongitude(longitude - 105, latitude - 35)
  const radianLatitude = latitude / 180 * PI
  let magic = Math.sin(radianLatitude)
  magic = 1 - ECCENTRICITY_SQUARED * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  deltaLatitude = deltaLatitude * 180 / ((EARTH_SEMI_MAJOR_AXIS * (1 - ECCENTRICITY_SQUARED)) / (magic * sqrtMagic) * PI)
  deltaLongitude = deltaLongitude * 180 / (EARTH_SEMI_MAJOR_AXIS / sqrtMagic * Math.cos(radianLatitude) * PI)
  return {
    latitude: latitude + deltaLatitude,
    longitude: longitude + deltaLongitude
  }
}

function presentSafetyView(safetyView) {
  const location = safetyView?.latest_location || null
  const locationHealth = safetyView?.location_health || null
  const riskStatus = safetyView?.risk_status || null
  const mapCoordinate = location?.source_crs === 'WGS84'
    ? wgs84ToGcj02(location.latitude, location.longitude)
    : null

  return {
    // 仅映射 Backend 已返回的状态用于展示，不在客户端重算安全或新鲜度。
    locationHealth,
    locationHealthText: LOCATION_HEALTH_TEXT[locationHealth] || '暂无定位信息',
    riskStatus,
    riskStatusText: RISK_STATUS_TEXT[riskStatus] || '暂无安全状态',
    recordedAt: location?.recorded_at || '--',
    recordedAtText: formatRecordedAt(location?.recorded_at),
    sourceCrs: location?.source_crs || '--',
    latitude: location?.latitude ?? null,
    longitude: location?.longitude ?? null,
    hasLocation: Boolean(mapCoordinate),
    mapLatitude: mapCoordinate?.latitude ?? 0,
    mapLongitude: mapCoordinate?.longitude ?? 0,
    circles: mapCoordinate ? [{
      latitude: mapCoordinate.latitude,
      longitude: mapCoordinate.longitude,
      radius: 18,
      color: '#ffffff',
      fillColor: '#1677ffcc',
      strokeWidth: 4
    }] : []
  }
}

function formatRecordedAt(value) {
  if (!value) return '暂无更新时间'
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return '暂无更新时间'
  return timestamp.toLocaleString('zh-CN', { hour12: false })
}

module.exports = {
  LOCATION_HEALTH_TEXT,
  RISK_STATUS_TEXT,
  formatRecordedAt,
  presentSafetyView,
  wgs84ToGcj02
}
