const STATUS_LABELS = {
  new: '待接单',
  processing: '处理中',
  resolved: '已解决'
}

export function presentSosSuccess(alert) {
  if (!alert?.id || !alert?.status) throw new Error('后端未返回有效求助事件')
  return `后端已记录求助事件 #${alert.id}，当前告警状态：${STATUS_LABELS[alert.status] || alert.status}`
}

export function presentSosFailure(error) {
  const detail = error instanceof Error ? error.message : '网络请求失败'
  return `求助发送失败或状态未知：${detail}`
}

export async function runSosSubmission({ isPending, setPending, submit }) {
  if (isPending()) return { submitted: false }
  setPending(true)
  try {
    return { submitted: true, value: await submit() }
  } finally {
    setPending(false)
  }
}
