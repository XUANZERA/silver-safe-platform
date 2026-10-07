export async function loadFamilyDashboard(elderApi, { isCurrent = () => true } = {}) {
  const elderList = await elderApi.list()
  if (!isCurrent()) return { stale: true }
  const currentElder = elderList?.items?.[0]
  if (!currentElder?.id) throw new Error('没有可查看的老人资料')

  const alertsRequest = elderApi.alerts(currentElder.id).then(
    (alertList) => ({ ok: true, alertList }),
    (error) => ({ ok: false, error })
  )
  const [safetyView, alertResult, trip, geofence] = await Promise.all([
    elderApi.safety(currentElder.id),
    alertsRequest,
    elderApi.currentTrip(currentElder.id),
    elderApi.geofence(currentElder.id)
  ])
  if (!isCurrent()) return { stale: true }

  return {
    currentElder,
    safetyView,
    alerts: alertResult.ok ? (alertResult.alertList?.items || []) : undefined,
    alertsLoadFailed: !alertResult.ok,
    alertError: alertResult.ok ? null : alertResult.error,
    trip,
    geofence
  }
}
