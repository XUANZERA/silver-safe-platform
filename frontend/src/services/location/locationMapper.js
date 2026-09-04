import {
  REAL_LOCATION_SOURCE,
  validateLocationSample,
  WGS84_CRS
} from './locationSample.js'

export function mapRealLocationSampleToPayload({ tripId, clientLocationId, sample }) {
  if (!Number.isInteger(tripId) || tripId <= 0) {
    throw new TypeError('tripId 必须是正整数')
  }
  if (
    typeof clientLocationId !== 'string' ||
    !/^[A-Za-z0-9._:-]{1,100}$/.test(clientLocationId)
  ) {
    throw new TypeError('clientLocationId 格式不合法')
  }

  validateLocationSample(sample)
  if (sample.source !== REAL_LOCATION_SOURCE || sample.sourceCrs !== WGS84_CRS) {
    throw new TypeError('REAL 定位样本必须来自 WGS84 Browser/H5 provider')
  }

  return {
    client_location_id: clientLocationId,
    latitude: sample.latitude,
    longitude: sample.longitude,
    speed_mps: sample.speedMps,
    accuracy_meters: sample.accuracyMeters,
    source: sample.source,
    source_crs: sample.sourceCrs,
    recorded_at: sample.recordedAt
  }
}
