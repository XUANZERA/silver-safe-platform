export const REAL_LOCATION_SOURCE = 'h5'
export const WGS84_CRS = 'WGS84'

export class InvalidLocationSampleError extends TypeError {
  constructor(field) {
    super(`定位样本字段不合法：${field}`)
    this.name = 'InvalidLocationSampleError'
    this.code = 'INVALID_LOCATION_SAMPLE'
    this.field = field
  }
}

function optionalNumber(value) {
  return value === null || value === undefined ? null : value
}

export function validateLocationSample(sample) {
  if (!sample || typeof sample !== 'object') {
    throw new InvalidLocationSampleError('sample')
  }
  if (!Number.isFinite(sample.latitude) || sample.latitude < -90 || sample.latitude > 90) {
    throw new InvalidLocationSampleError('latitude')
  }
  if (!Number.isFinite(sample.longitude) || sample.longitude < -180 || sample.longitude > 180) {
    throw new InvalidLocationSampleError('longitude')
  }
  if (
    sample.accuracyMeters !== null &&
    (!Number.isFinite(sample.accuracyMeters) || sample.accuracyMeters < 0 || sample.accuracyMeters > 10000)
  ) {
    throw new InvalidLocationSampleError('accuracyMeters')
  }
  if (
    sample.speedMps !== null &&
    (!Number.isFinite(sample.speedMps) || sample.speedMps < 0 || sample.speedMps > 100)
  ) {
    throw new InvalidLocationSampleError('speedMps')
  }
  if (typeof sample.recordedAt !== 'string' || Number.isNaN(Date.parse(sample.recordedAt))) {
    throw new InvalidLocationSampleError('recordedAt')
  }
  if (sample.sourceCrs !== WGS84_CRS) {
    throw new InvalidLocationSampleError('sourceCrs')
  }
  return sample
}

export function locationSampleFromBrowserPosition(position) {
  const timestamp = position?.timestamp
  if (!Number.isFinite(timestamp)) {
    throw new InvalidLocationSampleError('recordedAt')
  }

  const sample = {
    latitude: position?.coords?.latitude,
    longitude: position?.coords?.longitude,
    accuracyMeters: optionalNumber(position?.coords?.accuracy),
    speedMps: optionalNumber(position?.coords?.speed),
    recordedAt: new Date(timestamp).toISOString(),
    source: REAL_LOCATION_SOURCE,
    sourceCrs: WGS84_CRS
  }

  return Object.freeze(validateLocationSample(sample))
}
