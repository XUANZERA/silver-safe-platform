const TRIP_LABELS = {
  created: '待出发',
  active: '出游中',
  completed: '已完成',
  cancelled: '已取消'
}

const LOCATION_PRESENTATIONS = {
  NO_DATA: { label: '暂无定位数据', tone: 'neutral' },
  FRESH: { label: '定位正常', tone: 'success' },
  STALE: { label: '定位较久未更新', tone: 'warning' },
  INACCURATE: { label: '定位精度不足', tone: 'warning' }
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

const OPEN_ALERT_STATUSES = new Set(['new', 'processing'])

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
      label: '告警状态暂时无法获取',
      detail: '请稍后刷新状态',
      tone: 'neutral'
    }
  }
  if (!alert) {
    return {
      label: '暂无告警',
      detail: '',
      tone: 'neutral'
    }
  }
  const status = ALERT_PRESENTATION[alert.status] || {
    label: ALERT_STATUS_LABELS[alert.status] || '事件状态未知',
    tone: 'neutral'
  }
  if (alert.type === 'emergency') {
    return {
      label: '老人发起紧急求助',
      detail: alert.status === 'new'
        ? '待处理'
        : ALERT_STATUS_LABELS[alert.status] || '告警状态未知',
      tone: alert.status === 'new' ? 'danger' : status.tone,
      createdAt: formatAlertCreatedAt(alert.occurred_at)
    }
  }
  return {
    label: status.label,
    detail: ALERT_TYPE_LABELS[alert.type] || alert.type,
    tone: status.tone
  }
}

export function selectFamilyAlert(safetyAlert, alertItems) {
  const openAlerts = Array.isArray(alertItems)
    ? alertItems.filter((item) => OPEN_ALERT_STATUSES.has(item?.status))
    : []
  const emergencyAlert = openAlerts.find((item) => item.type === 'emergency')
  if (emergencyAlert) return emergencyAlert
  if (safetyAlert && OPEN_ALERT_STATUSES.has(safetyAlert.status)) return safetyAlert
  return openAlerts[0] || null
}

function formatAlertCreatedAt(value) {
  if (!value) return '创建时间：时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '创建时间：时间未知'
  return `创建时间：${date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })}`
}

function formatRecordedAt(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

export function presentLocationHealth(view, available = true, formatTime = formatRecordedAt) {
  if (!available || !view) {
    return {
      label: '数据不可用',
      tone: 'neutral',
      markerLabel: '暂无定位数据',
      lastLocationLabel: '最后定位：无法获取最新状态',
      recordedAtText: '无法获取最新状态',
      recordedAt: null,
      showMarker: false,
      isStale: false
    }
  }

  const state = LOCATION_PRESENTATIONS[view.location_health] || {
    label: '定位状态未知',
    tone: 'neutral'
  }
  const recordedAt = view.latest_location?.recorded_at || null
  const recordedAtText = recordedAt ? formatTime(recordedAt) : '暂无记录'
  const showMarker = Boolean(view.latest_location)
  return {
    ...state,
    markerLabel: showMarker ? '最新记录位置' : '暂无定位数据',
    lastLocationLabel: `最后定位：${recordedAtText}`,
    recordedAtText,
    recordedAt,
    showMarker,
    isStale: view.location_health === 'STALE'
  }
}

export function presentSafety(view, available = true) {
  const risk = presentRisk(view, available)
  const location = presentLocationHealth(view, available)
  if (!available || !view) {
    return {
      trip: '数据不可用',
      location: '数据不可用',
      locationTone: 'neutral',
      risk: risk.label,
      tone: risk.tone
    }
  }
  return {
    trip: view.trip_status ? (TRIP_LABELS[view.trip_status] || view.trip_status) : '无进行中行程',
    location: location.label,
    locationTone: location.tone,
    risk: risk.label,
    tone: risk.tone
  }
}
