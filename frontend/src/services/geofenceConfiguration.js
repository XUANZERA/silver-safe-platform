export function createSingleFlightAction() {
  let pending = false

  return async function runSingleFlight(action) {
    if (pending) return { status: 'IGNORED_DUPLICATE' }
    pending = true
    try {
      return await action()
    } finally {
      pending = false
    }
  }
}

export async function saveGeofenceForMode({
  realMode,
  update,
  refresh,
  onSaved,
  isCurrent = () => true
}) {
  if (!realMode) return { skipped: true }

  const savedGeofence = await update()
  if (!isCurrent()) {
    return { status: 'SAVED_REFRESH_UNCONFIRMED', geofence: savedGeofence }
  }
  onSaved?.(savedGeofence)

  try {
    if (!isCurrent()) {
      return { status: 'SAVED_REFRESH_UNCONFIRMED', geofence: savedGeofence }
    }
    const authoritativeState = await refresh()
    if (!isCurrent() || authoritativeState === false || authoritativeState?.superseded) {
      return { status: 'SAVED_REFRESH_UNCONFIRMED', geofence: savedGeofence }
    }
    return { status: 'CONFIRMED', geofence: savedGeofence, authoritativeState }
  } catch (error) {
    return { status: 'SAVED_REFRESH_FAILED', geofence: savedGeofence, error }
  }
}
