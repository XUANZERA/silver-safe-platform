import { LOCATION_STATUS } from './RealLocationProvider.js'
import { validateLocationSample } from './locationSample.js'

const DEFAULT_MIN_UPLOAD_INTERVAL_MS = 10000

function configuredMinUploadInterval() {
  const configured = Number(import.meta.env?.VITE_LOCATION_UPLOAD_MIN_INTERVAL_MS)
  return Number.isFinite(configured) && configured >= 0
    ? configured
    : DEFAULT_MIN_UPLOAD_INTERVAL_MS
}

function defaultClientLocationId(tripId) {
  const cryptoApi = globalThis.crypto
  let suffix = cryptoApi?.randomUUID?.()
  if (!suffix && cryptoApi?.getRandomValues) {
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16))
    suffix = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  }
  if (!suffix) throw new Error('当前浏览器无法生成定位请求标识')
  return `h5:${tripId}:${suffix}`
}

export function isActiveTrip(trip) {
  return Boolean(
    trip &&
    Number.isInteger(trip.id) &&
    trip.id > 0 &&
    trip.status === 'active'
  )
}

export function createLocationUploadCoordinator({
  upload,
  mapSample,
  minIntervalMs = configuredMinUploadInterval(),
  now = () => Date.now(),
  setTimer = (callback, delay) => globalThis.setTimeout(callback, delay),
  clearTimer = (timerId) => globalThis.clearTimeout(timerId),
  createClientLocationId = defaultClientLocationId,
  onStatusChange
} = {}) {
  if (typeof upload !== 'function') throw new TypeError('upload 必须是函数')
  if (typeof mapSample !== 'function') throw new TypeError('mapSample 必须是函数')
  if (!Number.isFinite(minIntervalMs) || minIntervalMs < 0) {
    throw new TypeError('minIntervalMs 必须是非负有限数值')
  }

  let running = false
  let tripId = null
  let generation = 0
  let inFlight = false
  let pendingLatest = null
  let lastUploadStartedAt = null
  let timerId = null
  let status = LOCATION_STATUS.IDLE

  function changeStatus(nextStatus) {
    status = nextStatus
    onStatusChange?.(nextStatus)
  }

  function clearScheduledUpload() {
    if (timerId !== null) clearTimer(timerId)
    timerId = null
  }

  function stop() {
    running = false
    tripId = null
    generation += 1
    pendingLatest = null
    lastUploadStartedAt = null
    clearScheduledUpload()
    changeStatus(LOCATION_STATUS.IDLE)
  }

  function start(trip) {
    if (!isActiveTrip(trip)) throw new TypeError('定位上传仅允许绑定 active Trip')
    if (running && tripId === trip.id) return false

    running = true
    tripId = trip.id
    generation += 1
    pendingLatest = null
    lastUploadStartedAt = null
    clearScheduledUpload()
    return true
  }

  function schedulePending(lifecycle) {
    if (!running || lifecycle !== generation || pendingLatest === null || inFlight) return
    const elapsed = lastUploadStartedAt === null ? minIntervalMs : now() - lastUploadStartedAt
    const remaining = lastUploadStartedAt === null ? 0 : Math.max(0, minIntervalMs - elapsed)
    if (remaining === 0) {
      const next = pendingLatest
      pendingLatest = null
      void beginUpload(next, lifecycle)
      return
    }
    if (timerId !== null) return
    timerId = setTimer(() => {
      timerId = null
      schedulePending(lifecycle)
    }, remaining)
  }

  async function beginUpload(envelope, lifecycle) {
    if (!running || lifecycle !== generation || inFlight) return

    let payload
    try {
      payload = mapSample({
        tripId,
        clientLocationId: envelope.clientLocationId,
        sample: envelope.sample
      })
    } catch {
      if (running && lifecycle === generation) changeStatus(LOCATION_STATUS.DEGRADED)
      schedulePending(lifecycle)
      return
    }

    inFlight = true
    lastUploadStartedAt = now()
    try {
      await upload(tripId, payload)
      if (running && lifecycle === generation) changeStatus(LOCATION_STATUS.TRACKING)
    } catch {
      if (running && lifecycle === generation) changeStatus(LOCATION_STATUS.DEGRADED)
    } finally {
      inFlight = false
      if (running) schedulePending(generation)
    }
  }

  function handleSample(sample) {
    if (!running) return false
    validateLocationSample(sample)
    const envelope = {
      sample,
      clientLocationId: createClientLocationId(tripId)
    }
    pendingLatest = envelope
    schedulePending(generation)
    return true
  }

  function getStatus() {
    return status
  }

  return { start, handleSample, stop, getStatus }
}
