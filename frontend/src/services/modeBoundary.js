const DEMO_ACCOUNTS = {
  operator01: { id: 9001, username: 'operator01', displayName: '林晓岚', role: 'operator', phone: '188****2608' },
  elder01: { id: 1001, username: 'elder01', displayName: '张建国', role: 'elder', phone: '138****4031' },
  child01: { id: 2001, username: 'child01', displayName: '张小明', role: 'family', phone: '138****2256' },
  family01: { id: 2001, username: 'family01', displayName: '张小明', role: 'family', phone: '138****2256' }
}

const DEMO_ITINERARY = [
  { time: '08:30', title: '集合出发', transport: '🚗 专车直达（约30分钟）', description: '服务人员到家接送，确认随身物品后前往天坛公园。', tips: [{ text: '🛋️ 专人陪同', type: 'safe' }, { text: '📞 家人可查看位置', type: 'safe' }] },
  { time: '09:00', title: '天坛公园慢游', transport: '🚶 平缓步道', description: '沿平整步道游览祈年殿，园区路况平缓，空气极佳。', tips: [{ text: '🛋️ 沿途有休息区', type: 'safe' }, { text: '🚶‍♂️ 全程平缓步道', type: 'safe' }, { text: '⚠️ 每小时休息15分钟', type: 'warning' }] },
  { time: '15:30', title: '返程回家', transport: '🚗 专车送回', description: '结束游览后由原车送回家，抵达后通知家人。', tips: [{ text: '✅ 已安排返程', type: 'safe' }, { text: '📞 抵达自动提醒', type: 'safe' }] }
]

const SESSION_MODES = Object.freeze({ REAL: 'real', DEMO: 'demo' })

export function modeName(realMode) {
  return realMode ? SESSION_MODES.REAL : SESSION_MODES.DEMO
}

export function sessionMatchesMode(session, realMode) {
  return Boolean(session) && session.mode === modeName(realMode)
}

export function homePathForRole(role) {
  return role === 'operator' ? '/operator' : role === 'family' ? '/child' : '/elder'
}

export function demoOnlyRedirect(realMode, session) {
  if (!realMode) return null
  return session?.role ? homePathForRole(session.role) : '/login'
}

export async function loginForMode({ realMode, username, password, login, saveSession }) {
  let user
  if (realMode) {
    user = await login(username, password)
  } else {
    const account = DEMO_ACCOUNTS[username]
    if (!account || password !== 'demo123') throw new Error('演示账号或密码不正确')
    user = account
  }

  const session = {
    ...user,
    displayName: user.displayName || user.username,
    path: homePathForRole(user.role),
    mode: modeName(realMode)
  }
  saveSession(session)
  return session
}

export function createDemoItinerary() {
  return structuredClone(DEMO_ITINERARY)
}

export function loadDemoItinerary(realMode, storage) {
  if (realMode) return null
  const saved = storage.getItem('helpingold-itinerary')
  if (!saved) return null
  try {
    const items = JSON.parse(saved)
    return Array.isArray(items) && items.length ? items : null
  } catch {
    storage.removeItem('helpingold-itinerary')
    return null
  }
}

export function presentRealSchedule({ loading = false, error = '', trip = null } = {}) {
  if (loading) return { kind: 'loading', title: '正在获取真实行程', detail: '请稍候' }
  if (error) return { kind: 'error', title: '数据不可用 / 无法获取真实行程', detail: error }
  if (!trip) return { kind: 'empty', title: '暂无真实行程', detail: '后端当前没有未完成的行程' }
  if (!hasValidRealDestination(trip)) return { kind: 'error', title: '真实行程目的地无效', detail: '请先设置真实目的地' }
  return {
    kind: 'ready',
    title: trip.destination,
    detail: trip.status === 'active' ? '进行中' : '待出发'
  }
}

export function presentElderPlan({ realMode, dataAvailable, trip }) {
  if (!realMode) return { kind: 'demo', title: '天坛公园慢游' }
  if (!dataAvailable) return { kind: 'error', title: '数据不可用 / 无法获取真实行程' }
  if (!trip) return { kind: 'empty', title: '暂无进行中的真实行程' }
  if (!hasValidRealDestination(trip)) return { kind: 'error', title: '真实行程目的地无效' }
  return { kind: 'ready', title: trip.destination }
}

export function hasValidRealDestination(trip) {
  const destination = trip?.destination?.trim()
  return Boolean(trip?.id && destination && destination !== '暂无行程' && destination !== '暂无真实行程')
}

export function realDestinationOrPlaceholder(trip, placeholder = '暂无真实行程') {
  return hasValidRealDestination(trip) ? trip.destination.trim() : placeholder
}

export async function startTripForMode({ realMode, trip, startExisting, startDemo }) {
  if (!realMode) return startDemo()
  if (!hasValidRealDestination(trip)) throw new Error('请先设置真实目的地')
  return startExisting(trip.id)
}

export async function logoutForMode({ realMode, logoutRemote, clearLocal }) {
  try {
    if (realMode) await logoutRemote()
  } catch {
    // Remote revocation can fail while offline; logoutRequest still clears its in-memory token.
  } finally {
    clearLocal()
  }
}

export function emergencyContactPresentation(realMode, demoMessage = '') {
  if (realMode) {
    return {
      label: '查看紧急联系信息',
      title: '紧急联系信息',
      message: '当前后端接口未提供有权限使用的紧急联系人电话号码，本页面不会发起拨号。'
    }
  }
  return {
    label: '查看紧急联系信息',
    title: '紧急联系信息（演示）',
    message: demoMessage || '联系人：张小明（138****2256）\n附近医院：北京同仁医院\n\n以上均为虚构演示信息，本页面不会发起拨号。'
  }
}
