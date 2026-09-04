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

const PERMISSION_STATE = Object.freeze({
  PROMPT: 'prompt',
  GRANTED: 'granted',
  DENIED: 'denied',
  UNKNOWN: 'unknown',
  UNAVAILABLE: 'unavailable'
})

function normalizeGeolocationError(error) {
  if (error?.code === 1) return { code: LOCATION_ERROR.PERMISSION_DENIED }
  if (error?.code === 2) return { code: LOCATION_ERROR.POSITION_UNAVAILABLE }
  if (error?.code === 3) return { code: LOCATION_ERROR.TIMEOUT }
  return { code: LOCATION_ERROR.UNKNOWN }
}

export function createRealLocationProvider({
  geolocation = globalThis.navigator?.geolocation,
  permissions = globalThis.navigator?.permissions,
  watchOptions = DEFAULT_WATCH_OPTIONS,
  onDiagnostic
} = {}) {
  let status = LOCATION_STATUS.IDLE
  let watchId = null
  let active = false
  let generation = 0
  let permissionState = permissions?.query
    ? PERMISSION_STATE.UNKNOWN
    : PERMISSION_STATE.UNAVAILABLE
  let permissionStatus = null
  let permissionChangeHandler = null
  let pendingAcquisitionError = null
  let hasValidPosition = false

  function emitDiagnostic(errorCode, category) {
    try {
      onDiagnostic?.(Object.freeze({
        errorCode: errorCode ?? null,
        internalErrorCategory: category,
        permissionState
      }))
    } catch {
      // Diagnostics must never affect the geolocation lifecycle.
    }
  }

  function notifyError(errorCode, normalized, onError) {
    emitDiagnostic(errorCode, normalized.code)
    onError?.(normalized)
  }

  function detachPermissionListener() {
    if (permissionStatus && permissionChangeHandler) {
      if (typeof permissionStatus.removeEventListener === 'function') {
        permissionStatus.removeEventListener('change', permissionChangeHandler)
      } else if (permissionStatus.onchange === permissionChangeHandler) {
        permissionStatus.onchange = null
      }
    }
    permissionStatus = null
    permissionChangeHandler = null
  }

  function clearCurrentWatch() {
    if (watchId !== null && geolocation?.clearWatch) {
      geolocation.clearWatch(watchId)
    }
    watchId = null
  }

  function stop() {
    active = false
    generation += 1
    pendingAcquisitionError = null
    hasValidPosition = false
    detachPermissionListener()
    clearCurrentWatch()
    status = LOCATION_STATUS.IDLE
    return status
  }

  function denyPermission(errorCode, lifecycle, onError) {
    if (!active || lifecycle !== generation) return
    permissionState = PERMISSION_STATE.DENIED
    active = false
    generation += 1
    pendingAcquisitionError = null
    detachPermissionListener()
    clearCurrentWatch()
    status = LOCATION_STATUS.PERMISSION_DENIED
    notifyError(errorCode, { code: LOCATION_ERROR.PERMISSION_DENIED }, onError)
  }

  function processAcquisitionError(errorCode, normalized, lifecycle, onError) {
    if (!active || lifecycle !== generation) return

    if (
      !hasValidPosition &&
      permissionState === PERMISSION_STATE.UNKNOWN
    ) {
      pendingAcquisitionError = { errorCode, normalized }
      return
    }

    if (
      !hasValidPosition &&
      permissionState === PERMISSION_STATE.PROMPT
    ) {
      status = LOCATION_STATUS.REQUESTING
    } else {
      status = LOCATION_STATUS.DEGRADED
    }
    notifyError(errorCode, normalized, onError)
  }

  function applyPermissionState(nextState, lifecycle, onError) {
    if (!active || lifecycle !== generation) return
    permissionState = Object.values(PERMISSION_STATE).includes(nextState)
      ? nextState
      : PERMISSION_STATE.UNAVAILABLE

    if (permissionState === PERMISSION_STATE.DENIED) {
      denyPermission(null, lifecycle, onError)
      return
    }

    if (pendingAcquisitionError) {
      const pending = pendingAcquisitionError
      pendingAcquisitionError = null
      processAcquisitionError(
        pending.errorCode,
        pending.normalized,
        lifecycle,
        onError
      )
    }
  }

  function observePermission(lifecycle, onError) {
    if (!permissions?.query) return

    let queryResult
    try {
      queryResult = permissions.query({ name: 'geolocation' })
    } catch {
      applyPermissionState(PERMISSION_STATE.UNAVAILABLE, lifecycle, onError)
      return
    }

    Promise.resolve(queryResult).then((result) => {
      if (!active || lifecycle !== generation) return
      permissionStatus = result
      permissionChangeHandler = () => {
        applyPermissionState(permissionStatus?.state, lifecycle, onError)
      }
      if (typeof permissionStatus?.addEventListener === 'function') {
        permissionStatus.addEventListener('change', permissionChangeHandler)
      } else if (permissionStatus) {
        permissionStatus.onchange = permissionChangeHandler
      }
      applyPermissionState(permissionStatus?.state, lifecycle, onError)
    }).catch(() => {
      applyPermissionState(PERMISSION_STATE.UNAVAILABLE, lifecycle, onError)
    })
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
    permissionState = permissions?.query
      ? PERMISSION_STATE.UNKNOWN
      : PERMISSION_STATE.UNAVAILABLE
    pendingAcquisitionError = null
    hasValidPosition = false
    observePermission(lifecycle, onError)

    const handlePosition = (position) => {
      if (!active || lifecycle !== generation) return
      let sample
      try {
        sample = locationSampleFromBrowserPosition(position)
      } catch {
        status = LOCATION_STATUS.DEGRADED
        notifyError(null, { code: LOCATION_ERROR.INVALID_SAMPLE }, onError)
        return
      }
      hasValidPosition = true
      pendingAcquisitionError = null
      status = LOCATION_STATUS.TRACKING
      onLocation?.(sample)
    }

    const handleError = (error) => {
      if (!active || lifecycle !== generation) return
      const normalized = normalizeGeolocationError(error)
      if (normalized.code === LOCATION_ERROR.PERMISSION_DENIED) {
        denyPermission(error?.code, lifecycle, onError)
        return
      }
      if (
        normalized.code === LOCATION_ERROR.POSITION_UNAVAILABLE ||
        normalized.code === LOCATION_ERROR.TIMEOUT
      ) {
        processAcquisitionError(error?.code, normalized, lifecycle, onError)
      } else {
        status = LOCATION_STATUS.DEGRADED
        notifyError(error?.code, normalized, onError)
      }
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
      pendingAcquisitionError = null
      detachPermissionListener()
      clearCurrentWatch()
      status = LOCATION_STATUS.DEGRADED
      notifyError(null, { code: LOCATION_ERROR.UNKNOWN }, onError)
    }
    return status
  }

  function getStatus() {
    return status
  }

  function getPermissionState() {
    return permissionState
  }

  return { start, stop, getStatus, getPermissionState }
}
