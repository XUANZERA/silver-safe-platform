'use strict'

const LOCATION_STATUS = Object.freeze({
  IDLE: 'IDLE',
  REQUESTING: 'REQUESTING',
  TRACKING: 'TRACKING',
  DEGRADED: 'DEGRADED',
  PERMISSION_DENIED: 'PERMISSION_DENIED'
})

const WGS84_CRS = 'WGS84'
const BACKEND_REAL_SOURCE = 'h5'
const DEFAULT_INTERVAL_MS = 10000

class InvalidLocationError extends TypeError {
  constructor(field) {
    super(`定位样本字段不合法：${field}`)
    this.name = 'InvalidLocationError'
    this.code = 'INVALID_LOCATION_SAMPLE'
    this.field = field
  }
}

function optionalMeasurement(value, { min, max, field }) {
  if (value === null || value === undefined || value === -1) return null
  if (!Number.isFinite(value) || value < min || value > max) {
    throw new InvalidLocationError(field)
  }
  return value
}

function locationSampleFromWxResult(result, recordedAt = new Date().toISOString()) {
  if (!Number.isFinite(result?.latitude) || result.latitude < -90 || result.latitude > 90) {
    throw new InvalidLocationError('latitude')
  }
  if (!Number.isFinite(result?.longitude) || result.longitude < -180 || result.longitude > 180) {
    throw new InvalidLocationError('longitude')
  }
  if (typeof recordedAt !== 'string' || Number.isNaN(Date.parse(recordedAt))) {
    throw new InvalidLocationError('recordedAt')
  }

  return Object.freeze({
    latitude: result.latitude,
    longitude: result.longitude,
    accuracyMeters: optionalMeasurement(result.accuracy, {
      min: 0,
      max: 10000,
      field: 'accuracy'
    }),
    speedMps: optionalMeasurement(result.speed, {
      min: 0,
      max: 100,
      field: 'speed'
    }),
    recordedAt,
    source: BACKEND_REAL_SOURCE,
    sourceCrs: WGS84_CRS
  })
}

function locationSampleToPayload(sample, clientLocationId) {
  if (typeof clientLocationId !== 'string' || !/^[A-Za-z0-9._:-]{1,100}$/.test(clientLocationId)) {
    throw new InvalidLocationError('clientLocationId')
  }
  if (sample?.sourceCrs !== WGS84_CRS) throw new InvalidLocationError('sourceCrs')
  if (sample?.source !== BACKEND_REAL_SOURCE) throw new InvalidLocationError('source')

  return Object.freeze({
    client_location_id: clientLocationId,
    latitude: sample.latitude,
    longitude: sample.longitude,
    speed_mps: sample.speedMps,
    accuracy_meters: sample.accuracyMeters,
    source: sample.source,
    source_crs: sample.sourceCrs,
    recorded_at: sample.recordedAt
  })
}

function defaultClientLocationId(tripId) {
  const random = Math.random().toString(36).slice(2, 10)
  return `wx:${tripId}:${Date.now()}:${random}`
}

function getWgs84Location(wxApi) {
  return new Promise((resolve, reject) => {
    wxApi.getLocation({
      type: 'wgs84',
      isHighAccuracy: true,
      highAccuracyExpireTime: 5000,
      success: resolve,
      fail: reject
    })
  })
}

function isAuthDeny(error) {
  const message = String(error?.errMsg || error?.message || (typeof error === 'string' ? error : ''))
  return /auth deny|system permission denied|system location disabled/i.test(message)
}

function createLocationService({
  wxApi,
  uploadLocation,
  intervalMs = DEFAULT_INTERVAL_MS,
  now = () => Date.now(),
  setIntervalImpl = (callback, delay) => setInterval(callback, delay),
  clearIntervalImpl = (timerId) => clearInterval(timerId),
  createClientLocationId = defaultClientLocationId,
  onStatusChange,
  onError
} = {}) {
  if (!wxApi || typeof wxApi.getLocation !== 'function') {
    throw new TypeError('wxApi.getLocation 必须可用')
  }
  if (typeof uploadLocation !== 'function') throw new TypeError('uploadLocation 必须是函数')
  if (!Number.isFinite(intervalMs) || intervalMs <= 0) {
    throw new TypeError('intervalMs 必须是正数')
  }

  let status = LOCATION_STATUS.IDLE
  let running = false
  let tripId = null
  let generation = 0
  let timerId = null
  let inFlight = false

  function changeStatus(nextStatus) {
    status = nextStatus
    onStatusChange?.(nextStatus)
  }

  async function collect(lifecycle) {
    if (!running || lifecycle !== generation || inFlight) return
    inFlight = true
    let phase = 'location'
    try {
      const result = await getWgs84Location(wxApi)
      if (!running || lifecycle !== generation) return

      const sample = locationSampleFromWxResult(result, new Date(now()).toISOString())
      const payload = locationSampleToPayload(sample, createClientLocationId(tripId))
      phase = 'upload'
      await uploadLocation(tripId, payload)
      if (running && lifecycle === generation) changeStatus(LOCATION_STATUS.TRACKING)
    } catch (error) {
      if (running && lifecycle === generation) {
        const authDenied = phase === 'location' && isAuthDeny(error)
        if (authDenied) {
          if (timerId !== null) {
            clearIntervalImpl(timerId)
            timerId = null
          }
          running = false
          changeStatus(LOCATION_STATUS.PERMISSION_DENIED)
        } else {
          changeStatus(LOCATION_STATUS.DEGRADED)
        }
        onError?.(Object.freeze({
          phase,
          permissionDenied: authDenied,
          cause: error
        }))
      }
    } finally {
      inFlight = false
    }
  }

  function start(trip) {
    if (!trip || !Number.isInteger(trip.id) || trip.id <= 0 || trip.status !== 'active') {
      throw new TypeError('定位守护只能绑定 Backend 返回的 active trip')
    }
    if (running && tripId === trip.id) return false
    if (running) stop()

    running = true
    tripId = trip.id
    generation += 1
    const lifecycle = generation
    changeStatus(LOCATION_STATUS.REQUESTING)
    timerId = setIntervalImpl(() => {
      void collect(lifecycle)
    }, intervalMs)
    void collect(lifecycle)
    return true
  }

  function stop() {
    running = false
    tripId = null
    generation += 1
    if (timerId !== null) clearIntervalImpl(timerId)
    timerId = null
    changeStatus(LOCATION_STATUS.IDLE)
  }

  return {
    start,
    stop,
    getStatus: () => status,
    isRunning: () => running
  }
}

module.exports = {
  BACKEND_REAL_SOURCE,
  DEFAULT_INTERVAL_MS,
  InvalidLocationError,
  LOCATION_STATUS,
  WGS84_CRS,
  createLocationService,
  getWgs84Location,
  isAuthDeny,
  locationSampleFromWxResult,
  locationSampleToPayload
}
