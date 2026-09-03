export function mapOperatorAlerts(items, elders) {
  const elderNames = new Map(elders.map((elder) => [elder.id, elder.name]))
  return items.map((item) => ({
    id: item.id,
    elderId: item.elder_id,
    elderName: elderNames.get(item.elder_id) || `老人 ${item.elder_id}`,
    type: item.type === 'emergency' ? 'SOS 紧急求助' : '电子围栏越界',
    level: item.type === 'emergency' ? 'urgent' : 'warning',
    backendStatus: item.status,
    status: item.status === 'resolved' ? '已解决' : item.status === 'processing' ? '处理中' : '待处理',
    location: item.latitude !== null && item.longitude !== null
      ? `${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}`
      : '位置待更新',
    time: new Date(item.occurred_at).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    familyContact: '请通过老人资料核实家属联系方式',
    resolution: item.resolution || '',
    handler: item.handler || null
  }))
}

export function selectOperatorTrips(realMode, demoTrips) {
  return realMode ? [] : demoTrips.map((trip) => ({ ...trip }))
}

export function replaceAuthoritativeOperatorSnapshot({ alerts, elders }, elderData, alertData) {
  const backendElders = elderData?.items || []
  const backendAlerts = alertData?.items || []
  elders.splice(0, elders.length, ...backendElders.map((item) => ({
    id: item.id,
    name: item.name,
    age: item.age,
    status: '后端状态待查看',
    risk: '未在告警队列推断',
    family: '家属信息未在此接口返回',
    familyPhone: '请查看老人资料核实'
  })))
  alerts.splice(0, alerts.length, ...mapOperatorAlerts(backendAlerts, backendElders))
}

export function syncDemoElderState({ realMode, elders, alerts, trips, elderName }) {
  if (realMode) return false
  const elder = elders.find((item) => item.name === elderName)
  if (!elder) return false
  const elderAlerts = alerts.filter((alert) => alert.elderName === elderName && alert.status !== '已解决')
  const activeTrip = trips.find((trip) => trip.elderName === elderName && trip.status === '进行中')
  if (elderAlerts.some((alert) => alert.level === 'urgent')) {
    elder.status = '告警中'
    elder.risk = '高风险'
  } else if (elderAlerts.length) {
    elder.status = '需关注'
    elder.risk = '中风险'
  } else if (activeTrip) {
    elder.status = '出游中'
    elder.risk = '低风险'
  } else {
    elder.status = '在家'
    elder.risk = '低风险'
  }
  return true
}

export async function runAuthoritativeAlertAction(action, refresh) {
  const response = await action()
  const refreshed = await refresh()
  if (!refreshed?.ok) throw refreshed?.error || new Error('无法刷新后端告警状态')
  return response
}

export async function runOperatorAlertAction({ realMode, action, refresh, applyDemo }) {
  if (!realMode) {
    applyDemo()
    return { authoritative: false }
  }
  const response = await runAuthoritativeAlertAction(action, refresh)
  return { authoritative: true, response }
}
