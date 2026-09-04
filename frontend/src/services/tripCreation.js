const RESERVED_DESTINATIONS = new Set(['暂无行程', '暂无真实行程'])
const MAX_DESTINATION_LENGTH = 200

export const CREATE_STATE = Object.freeze({
  READY: 'CREATE_READY',
  UNKNOWN: 'CREATE_UNKNOWN'
})

export const CREATE_RESULT = Object.freeze({
  INVALID: 'CREATE_INVALID',
  PENDING: 'CREATE_PENDING',
  CREATED: 'CREATE_CONFIRMED',
  RECONCILED: 'CREATE_RECONCILED',
  REJECTED: 'CREATE_REJECTED',
  UNKNOWN: CREATE_STATE.UNKNOWN,
  READY: CREATE_STATE.READY
})

export const START_RESULT = Object.freeze({
  INVALID: 'START_INVALID',
  PENDING: 'START_PENDING',
  CONFIRMED: 'START_CONFIRMED',
  RECONCILED: 'START_RECONCILED',
  REJECTED: 'START_REJECTED',
  UNKNOWN: 'START_UNKNOWN'
})

export function normalizeDestination(value) {
  return String(value ?? '').trim()
}

export function isValidDestination(value) {
  const destination = normalizeDestination(value)
  return Boolean(
    destination &&
    destination.length <= MAX_DESTINATION_LENGTH &&
    !RESERVED_DESTINATIONS.has(destination)
  )
}

export function isStartableTrip(trip) {
  return Boolean(
    trip?.id &&
    trip.status === 'created' &&
    isValidDestination(trip.destination)
  )
}

export function canCreateRealTrip({ realMode, tripDataAvailable, currentTrip, createState }) {
  return Boolean(
    realMode &&
    tripDataAvailable &&
    currentTrip === null &&
    createState !== CREATE_STATE.UNKNOWN
  )
}

function shouldReconcile(error) {
  return error?.status === 409 || error?.status >= 500 || error?.hasResponse !== true
}

async function refreshAuthoritativeTrip(refreshTrip) {
  try {
    return { succeeded: true, trip: await refreshTrip(), error: null }
  } catch (error) {
    return { succeeded: false, trip: null, error }
  }
}

export async function createTripAndRefresh({
  destination,
  isPending,
  setPending,
  createTrip,
  refreshTrip
}) {
  if (isPending()) return { type: CREATE_RESULT.PENDING }

  const normalizedDestination = normalizeDestination(destination)
  if (!isValidDestination(normalizedDestination)) {
    return { type: CREATE_RESULT.INVALID }
  }

  setPending(true)
  try {
    try {
      await createTrip(normalizedDestination)
    } catch (error) {
      if (!shouldReconcile(error)) return { type: CREATE_RESULT.REJECTED, error }

      const refreshed = await refreshAuthoritativeTrip(refreshTrip)
      if (refreshed.succeeded && refreshed.trip) {
        return { type: CREATE_RESULT.RECONCILED, trip: refreshed.trip, error }
      }
      return {
        type: CREATE_RESULT.UNKNOWN,
        error,
        refreshError: refreshed.error
      }
    }

    const refreshed = await refreshAuthoritativeTrip(refreshTrip)
    if (refreshed.succeeded && refreshed.trip) {
      return { type: CREATE_RESULT.CREATED, trip: refreshed.trip }
    }
    return {
      type: CREATE_RESULT.UNKNOWN,
      error: refreshed.error
    }
  } finally {
    setPending(false)
  }
}

export async function refreshUnknownCreation({ isPending, setPending, refreshTrip }) {
  if (isPending()) return { type: CREATE_RESULT.PENDING }

  setPending(true)
  try {
    const refreshed = await refreshAuthoritativeTrip(refreshTrip)
    if (!refreshed.succeeded) {
      return { type: CREATE_RESULT.UNKNOWN, error: refreshed.error }
    }
    if (refreshed.trip) {
      return { type: CREATE_RESULT.RECONCILED, trip: refreshed.trip }
    }
    return { type: CREATE_RESULT.READY, trip: null }
  } finally {
    setPending(false)
  }
}

export async function startTripAndRefresh({
  trip,
  isPending,
  setPending,
  startTrip,
  refreshTrip
}) {
  if (isPending()) return { type: START_RESULT.PENDING }
  if (!isStartableTrip(trip)) return { type: START_RESULT.INVALID }

  setPending(true)
  try {
    try {
      await startTrip(trip.id)
    } catch (error) {
      if (!shouldReconcile(error)) return { type: START_RESULT.REJECTED, error }

      const refreshed = await refreshAuthoritativeTrip(refreshTrip)
      if (refreshed.succeeded && refreshed.trip) {
        return { type: START_RESULT.RECONCILED, trip: refreshed.trip, error }
      }
      return { type: START_RESULT.UNKNOWN, error, refreshError: refreshed.error }
    }

    const refreshed = await refreshAuthoritativeTrip(refreshTrip)
    if (refreshed.succeeded && refreshed.trip) {
      return { type: START_RESULT.CONFIRMED, trip: refreshed.trip }
    }
    return { type: START_RESULT.UNKNOWN, error: refreshed.error }
  } finally {
    setPending(false)
  }
}
