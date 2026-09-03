const TRIP_LABELS = {
  created: '待出发',
  active: '出游中',
  completed: '已完成',
  cancelled: '已取消'
}

const LOCATION_LABELS = {
  NO_DATA: '暂无定位数据',
  FRESH: '定位数据新鲜',
  STALE: '定位数据已过期',
  INACCURATE: '定位精度不足',
  FRESHNESS_TBD: '定位新鲜度待确认'
}

const RISK_LABELS = {
  SAFE: '当前位于安全围栏内',
  PENDING: '检测到越界，等待连续定位确认',
  ALERT: '已确认越出安全围栏'
}

const ALERT_TYPE_LABELS = {
  emergency: '紧急求助',
  geofence_exit: '围栏越界'
}

const ALERT_STATUS_LABELS = {
  new: '待接单',
  processing: '处理中',
  resolved: '已解决'
}

const ALERT_PRESENTATION = {
  new: { label: '等待工作人员接单', tone: 'warning' },
  processing: { label: '工作人员处理中', tone: 'processing' },
  resolved: { label: '事件已解决', tone: 'success' }
}

export function presentRisk(view, available = true) {
  if (!available || !view) {
    return {
      label: '数据不可用 / 无法获取最新状态',
      tone: 'neutral'
    }
  }
  if (view.risk_status === 'ALERT') return { label: RISK_LABELS.ALERT, tone: 'danger' }
  if (view.risk_status === 'PENDING') return { label: RISK_LABELS.PENDING, tone: 'warning' }
  if (view.risk_status === 'SAFE' && view.location_health === 'FRESH') {
    return { label: RISK_LABELS.SAFE, tone: 'success' }
  }
  return { label: '风险状态无法判定', tone: 'neutral' }
}

export function presentAlertWorkflow(alert, available = true) {
  if (!available) {
    return {
      label: '事件处置状态不可用',
      detail: '无法获取最新事件状态',
      tone: 'neutral'
    }
  }
  if (!alert) {
    return {
      label: '当前没有待处理事件',
      detail: '',
      tone: 'neutral'
    }
  }
  const status = ALERT_PRESENTATION[alert.status] || {
    label: ALERT_STATUS_LABELS[alert.status] || '事件状态未知',
    tone: 'neutral'
  }
  return {
    label: status.label,
    detail: ALERT_TYPE_LABELS[alert.type] || alert.type,
    tone: status.tone
  }
}

export function presentSafety(view, available = true) {
  const risk = presentRisk(view, available)
  if (!available || !view) {
    return {
      trip: '数据不可用',
      location: '数据不可用',
      risk: risk.label,
      tone: risk.tone
    }
  }
  return {
    trip: view.trip_status ? (TRIP_LABELS[view.trip_status] || view.trip_status) : '无进行中行程',
    location: LOCATION_LABELS[view.location_health] || '定位状态未知',
    risk: risk.label,
    tone: risk.tone
  }
}
