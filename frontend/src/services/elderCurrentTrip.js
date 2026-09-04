export const TRIP_LOAD_FAILURE = Object.freeze({
  AUTH_UNAVAILABLE: 'AUTH_UNAVAILABLE',
  TRIP_UNAVAILABLE: 'TRIP_UNAVAILABLE'
})

const AUTH_ERROR_CODES = new Set([
  'UNAUTHORIZED',
  'TOKEN_EXPIRED',
  'INVALID_TOKEN',
  'INVALID_REFRESH_TOKEN',
  'SESSION_REVOKED',
  'REFRESH_TOKEN_REUSED'
])

export function isAuthUnavailable(error) {
  return error?.status === 401 || AUTH_ERROR_CODES.has(error?.code)
}

export function createElderTripState({ realMode, demoTrip = null } = {}) {
  const trip = realMode ? null : demoTrip
  return {
    currentTrip: trip,
    currentTripId: trip?.id ?? null,
    currentTripBackendStatus: trip?.status ?? null,
    tripDataAvailable: !realMode,
    tripLoadError: null,
    tripLoadFailureKind: null,
    tripStatus: realMode ? '状态获取中' : (trip?.status === 'active' ? '出游中' : '待出发'),
    destination: trip?.destination?.trim?.() || ''
  }
}

export function applyAuthoritativeCurrentTrip(state, trip) {
  state.currentTrip = trip
  state.currentTripId = trip?.id ?? null
  state.currentTripBackendStatus = trip?.status ?? null
  state.tripDataAvailable = true
  state.tripLoadError = null
  state.tripLoadFailureKind = null
  state.destination = trip?.destination?.trim?.() || ''
  state.tripStatus = !trip
    ? '暂无进行中的真实行程'
    : trip.status === 'active' ? '出游中' : '待出发'
}

export function applyCurrentTripFailure(state, error) {
  const authUnavailable = isAuthUnavailable(error)
  state.currentTrip = null
  state.currentTripId = null
  state.currentTripBackendStatus = null
  state.tripDataAvailable = false
  state.tripLoadError = error
  state.tripLoadFailureKind = authUnavailable
    ? TRIP_LOAD_FAILURE.AUTH_UNAVAILABLE
    : TRIP_LOAD_FAILURE.TRIP_UNAVAILABLE
  state.destination = ''
  state.tripStatus = authUnavailable ? '登录状态不可用' : '行程状态不可用'
}

export async function loadAuthoritativeElderTrip({
  state,
  listElders,
  getCurrentTrip,
  onElder
}) {
  try {
    const list = await listElders()
    const elder = list?.items?.[0]
    if (!elder?.id) throw new Error('没有可用的老人资料')
    onElder?.(elder)
    const trip = await getCurrentTrip(elder.id)
    applyAuthoritativeCurrentTrip(state, trip)
    return { elder, trip }
  } catch (error) {
    applyCurrentTripFailure(state, error)
    throw error
  }
}

export async function reloadAfterAuthReady({ ensureAuthReady, reload }) {
  await ensureAuthReady()
  return reload()
}
