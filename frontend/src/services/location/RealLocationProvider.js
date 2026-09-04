import { locationSampleFromBrowserPosition } from './locationSample.js'

export const LOCATION_STATUS = Object.freeze({
  IDLE: 'IDLE',
  REQUESTING: 'REQUESTING',
  TRACKING: 'TRACKING',
  DEGRADED: 'DEGRADED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  UNSUPPORTED: 'UNSUPPORTED'
})

export const LOCATION_ERROR = Object.freeze({
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  POSITION_UNAVAILABLE: 'POSITION_UNAVAILABLE',
  TIMEOUT: 'TIMEOUT',
  UNSUPPORTED: 'UNSUPPORTED',
  INVALID_SAMPLE: 'INVALID_SAMPLE',
  UNKNOWN: 'UNKNOWN'
})

const DEFAULT_WATCH_OPTIONS = Object.freeze({
  enableHighAccuracy: true,
  maximumAge: 0,
  timeout: 20000
})

function normalizeGeolocationError(error) {
  if (error?.code === 1) return { code: LOCATION_ERROR.PERMISSION_DENIED }
  if (error?.code === 2) return { code: LOCATION_ERROR.POSITION_UNAVAILABLE }
  if (error?.code === 3) return { code: LOCATION_ERROR.TIMEOUT }
  return { code: LOCATION_ERROR.UNKNOWN }
}

export function createRealLocationProvider({
  geolocation = globalThis.navigator?.geolocation,
  watchOptions = DEFAULT_WATCH_OPTIONS
} = {}) {
  let status = LOCATION_STATUS.IDLE
  let watchId = null
  let active = false
  let generation = 0

  function clearCurrentWatch() {
    if (watchId !== null && geolocation?.clearWatch) {
      geolocation.clearWatch(watchId)
    }
    watchId = null
  }

  function stop() {
    active = false
    generation += 1
    clearCurrentWatch()
    status = LOCATION_STATUS.IDLE
    return status
  }

  function start(onLocation, onError) {
    if (active) return status
    if (!geolocation?.watchPosition || !geolocation?.clearWatch) {
      status = LOCATION_STATUS.UNSUPPORTED
      onError?.({ code: LOCATION_ERROR.UNSUPPORTED })
      return status
    }

    active = true
    status = LOCATION_STATUS.REQUESTING
    const lifecycle = ++generation

    const handlePosition = (position) => {
      if (!active || lifecycle !== generation) return
      let sample
      try {
        sample = locationSampleFromBrowserPosition(position)
      } catch {
        status = LOCATION_STATUS.DEGRADED
        onError?.({ code: LOCATION_ERROR.INVALID_SAMPLE })
        return
      }
      status = LOCATION_STATUS.TRACKING
      onLocation?.(sample)
    }

    const handleError = (error) => {
      if (!active || lifecycle !== generation) return
      const normalized = normalizeGeolocationError(error)
      if (normalized.code === LOCATION_ERROR.PERMISSION_DENIED) {
        active = false
        generation += 1
        clearCurrentWatch()
        status = LOCATION_STATUS.PERMISSION_DENIED
      } else {
        status = LOCATION_STATUS.DEGRADED
      }
      onError?.(normalized)
    }

    try {
      const nextWatchId = geolocation.watchPosition(
        handlePosition,
        handleError,
        { ...watchOptions }
      )
      if (!active || lifecycle !== generation) {
        geolocation.clearWatch(nextWatchId)
      } else {
        watchId = nextWatchId
      }
    } catch {
      active = false
      generation += 1
      clearCurrentWatch()
      status = LOCATION_STATUS.DEGRADED
      onError?.({ code: LOCATION_ERROR.UNKNOWN })
    }
    return status
  }

  function getStatus() {
    return status
  }

  return { start, stop, getStatus }
}
