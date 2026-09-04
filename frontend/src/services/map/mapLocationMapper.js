export const CANONICAL_CRS = 'WGS84'

export class InvalidCanonicalLocationError extends TypeError {
  constructor(reason, field = null) {
    super(`非法的权威定位数据: ${reason}${field ? ` (${field})` : ''}`)
    this.name = 'InvalidCanonicalLocationError'
    this.code = 'INVALID_CANONICAL_LOCATION'
    this.field = field
  }
}

function extractCrs(location) {
  return location.source_crs ?? location.sourceCrs
}

function extractRecordedAt(location) {
  return location.recorded_at ?? location.recordedAt
}

export function isCanonicalLocation(location) {
  if (!location || typeof location !== 'object') return false

  const lat = location.latitude
  const lng = location.longitude
  if (typeof lat !== 'number' || !Number.isFinite(lat) || lat < -90 || lat > 90) {
    return false
  }
  if (typeof lng !== 'number' || !Number.isFinite(lng) || lng < -180 || lng > 180) {
    return false
  }

  const crs = extractCrs(location)
  if (crs !== CANONICAL_CRS) {
    return false
  }

  const recordedAt = extractRecordedAt(location)
  if (recordedAt !== undefined && recordedAt !== null) {
    if (typeof recordedAt !== 'string' && !(recordedAt instanceof Date)) {
      return false
    }
    const parsed = typeof recordedAt === 'string' ? Date.parse(recordedAt) : recordedAt.getTime()
    if (Number.isNaN(parsed)) {
      return false
    }
  }

  return true
}

export function validateCanonicalLocation(location) {
  if (!location || typeof location !== 'object') {
    throw new InvalidCanonicalLocationError('定位对象不可为空', 'location')
  }

  const lat = location.latitude
  if (typeof lat !== 'number' || !Number.isFinite(lat)) {
    throw new InvalidCanonicalLocationError('纬度必须为有限数值', 'latitude')
  }
  if (lat < -90 || lat > 90) {
    throw new InvalidCanonicalLocationError('纬度超出有效范围 [-90, 90]', 'latitude')
  }

  const lng = location.longitude
  if (typeof lng !== 'number' || !Number.isFinite(lng)) {
    throw new InvalidCanonicalLocationError('经度必须为有限数值', 'longitude')
  }
  if (lng < -180 || lng > 180) {
    throw new InvalidCanonicalLocationError('经度超出有效范围 [-180, 180]', 'longitude')
  }

  const crs = extractCrs(location)
  if (crs === undefined || crs === null) {
    throw new InvalidCanonicalLocationError('缺失坐标参考系', 'source_crs')
  }
  if (crs !== CANONICAL_CRS) {
    throw new InvalidCanonicalLocationError(`不支持的坐标参考系: ${crs}，仅接受 ${CANONICAL_CRS}`, 'source_crs')
  }

  const recordedAt = extractRecordedAt(location)
  let normalizedRecordedAt = null
  if (recordedAt !== undefined && recordedAt !== null) {
    if (typeof recordedAt === 'string') {
      if (Number.isNaN(Date.parse(recordedAt))) {
        throw new InvalidCanonicalLocationError('时间戳格式不合法', 'recorded_at')
      }
      normalizedRecordedAt = recordedAt
    } else if (recordedAt instanceof Date) {
      if (Number.isNaN(recordedAt.getTime())) {
        throw new InvalidCanonicalLocationError('时间戳不合法', 'recorded_at')
      }
      normalizedRecordedAt = recordedAt.toISOString()
    } else {
      throw new InvalidCanonicalLocationError('时间戳类型不合法', 'recorded_at')
    }
  }

  const accuracy = location.accuracy_meters ?? location.accuracyMeters ?? null
  if (accuracy !== null && (typeof accuracy !== 'number' || !Number.isFinite(accuracy) || accuracy < 0)) {
    throw new InvalidCanonicalLocationError('精度必须为非负有限数值', 'accuracy_meters')
  }

  const speed = location.speed_mps ?? location.speedMps ?? null
  if (speed !== null && (typeof speed !== 'number' || !Number.isFinite(speed) || speed < 0)) {
    throw new InvalidCanonicalLocationError('速度必须为非负有限数值', 'speed_mps')
  }

  // Pure function: create a presentation canonical copy, never mutate original
  return {
    id: location.id ?? null,
    tripId: location.trip_id ?? location.tripId ?? null,
    latitude: lat,
    longitude: lng,
    sourceCrs: CANONICAL_CRS,
    recordedAt: normalizedRecordedAt,
    accuracyMeters: accuracy,
    speedMps: speed
  }
}

export function validateCanonicalTrack(points) {
  if (!Array.isArray(points)) {
    return []
  }
  return points
    .filter((point) => isCanonicalLocation(point))
    .map((point) => validateCanonicalLocation(point))
}

