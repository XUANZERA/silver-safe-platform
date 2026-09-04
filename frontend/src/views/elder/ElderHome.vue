<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
// FIX START: API 失败时向用户展示后端返回的真实错误。
import { showConfirmDialog, showDialog, showFailToast, showSuccessToast } from 'vant'
// FIX END: API 失败时向用户展示后端返回的真实错误。
import { aiApi, alertApi, elderApi, isApiConfigured, tripApi } from '../../services/api'
import { hasValidRealDestination, loadDemoItinerary, presentElderPlan, realDestinationOrPlaceholder, startTripForMode } from '../../services/modeBoundary'
import { presentElderTripActionHint } from '../../services/modePresentation'
import { presentSosFailure, presentSosSuccess, runSosSubmission } from '../../services/sosPresentation'
import {
  CREATE_RESULT,
  CREATE_STATE,
  START_RESULT,
  canCreateRealTrip,
  createTripAndRefresh,
  isStartableTrip,
  isValidDestination,
  refreshUnknownCreation,
  startTripAndRefresh
} from '../../services/tripCreation'
import logo from '../../assets/logo.png'

const router = useRouter()
const realMode = isApiConfigured()
const tripStatus = ref(realMode ? '状态获取中' : '出游中')
const locationStatus = ref(realMode ? '定位状态待同步' : '模拟定位正常')
const showMore = ref(false)
const showAiPlan = ref(false)
// FIX START: 单独保存行程 ID，不能把老人 ID 当成行程 ID。
const currentTripId = ref(null)
const currentTripBackendStatus = ref(realMode ? null : 'active')
const currentTrip = ref(realMode ? null : { id: 5001, destination: '天坛公园慢游', status: 'active' })
const tripDataAvailable = ref(!realMode)
const createTripVisible = ref(false)
const destinationInput = ref('')
const creatingTrip = ref(false)
const refreshingUnknownTrip = ref(false)
const startingTrip = ref(false)
const createState = ref(CREATE_STATE.READY)
const sosSending = ref(false)
const sosResult = ref('')
// FIX END: 单独保存行程 ID。
const showAiChat = ref(false)
const aiInput = ref('')
const aiLoading = ref(false)
const aiMessages = ref([{ role: 'assistant', text: '您好，我是您的行程小助手。想去哪里，直接告诉我就好。' }])
const elder = reactive({ id: realMode ? null : 1001, name: realMode ? '老人' : '张建国', age: realMode ? '--' : 72, family: realMode ? '当前接口未提供' : '张小明', familyPhone: realMode ? '当前接口未提供' : '138****2256', destination: realMode ? '' : '天坛公园慢游', lastUpdate: realMode ? '尚未同步' : '刚刚' })
const isTripActive = computed(() => currentTripBackendStatus.value === 'active')
const isCreateUnknown = computed(() => createState.value === CREATE_STATE.UNKNOWN)
const showCreateTrip = computed(() => canCreateRealTrip({
  realMode,
  tripDataAvailable: tripDataAvailable.value,
  currentTrip: currentTrip.value,
  createState: createState.value
}))
const hasUsableDestination = computed(() => !realMode || hasValidRealDestination(currentTrip.value))
const tripActionHint = computed(() => {
  if (realMode && !tripDataAvailable.value) return '真实行程数据不可用'
  if (realMode && !isTripActive.value && !hasValidRealDestination(currentTrip.value)) return '请先设置真实目的地'
  return presentElderTripActionHint(realMode, isTripActive.value)
})
const tripActionDisabled = computed(() => realMode && (
  !tripDataAvailable.value ||
  (!isTripActive.value && (!isStartableTrip(currentTrip.value) || startingTrip.value))
))
const planPresentation = computed(() => presentElderPlan({ realMode, dataAvailable: tripDataAvailable.value, trip: currentTrip.value }))

function applySavedItinerary() {
  const items = loadDemoItinerary(realMode, sessionStorage)
  const destinationItem = items?.[1] || items?.[0]
  if (destinationItem?.title) elder.destination = destinationItem.title
}

function applyCurrentTrip(trip) {
  currentTrip.value = trip
  currentTripId.value = trip?.id ?? null
  currentTripBackendStatus.value = trip?.status ?? null
  elder.destination = realDestinationOrPlaceholder(trip, '')
  tripDataAvailable.value = true

  if (!trip) {
    tripStatus.value = '暂无进行中的真实行程'
    locationStatus.value = '当前没有进行中的行程'
  } else {
    tripStatus.value = trip.status === 'active' ? '出游中' : '待出发'
    locationStatus.value = trip.status === 'active' ? '等待定位上报' : '定位已暂停'
  }
}

function applyCurrentTripFailure() {
  currentTrip.value = null
  currentTripId.value = null
  currentTripBackendStatus.value = null
  elder.destination = ''
  tripDataAvailable.value = false
  tripStatus.value = '行程状态不可用'
  locationStatus.value = '无法获取最新状态'
}

async function loadCurrentTrip() {
  if (!realMode || !elder.id) throw new Error('没有可用的老人资料')
  try {
    const trip = await elderApi.currentTrip(elder.id)
    applyCurrentTrip(trip)
    return trip
  } catch (error) {
    applyCurrentTripFailure()
    throw error
  }
}

onMounted(async () => {
  if (!realMode) {
    applySavedItinerary()
    return
  }
  try {
    const list = await elderApi.list()
    const current = list?.items?.[0]
    if (!current) throw new Error('没有可用的老人资料')
    Object.assign(elder, { id: current.id, name: current.name, age: current.age ?? '--' })
    await loadCurrentTrip()
  } catch (error) {
    applyCurrentTripFailure()
    console.warn('老人端后端数据加载失败', error)
  }
})

async function createRealTrip() {
  if (!realMode || creatingTrip.value) return

  const result = await createTripAndRefresh({
    destination: destinationInput.value,
    isPending: () => creatingTrip.value,
    setPending: (pending) => { creatingTrip.value = pending },
    createTrip: (destination) => tripApi.create(destination),
    refreshTrip: loadCurrentTrip
  })

  if (result.type === CREATE_RESULT.INVALID) {
    showFailToast('请输入有效目的地（最多 200 个字符）')
    return
  }
  if (result.type === CREATE_RESULT.REJECTED) {
    showFailToast(result.error?.message || '行程创建请求被拒绝')
    return
  }
  if (result.type === CREATE_RESULT.UNKNOWN) {
    createState.value = CREATE_STATE.UNKNOWN
    return
  }
  if (result.type === CREATE_RESULT.CREATED || result.type === CREATE_RESULT.RECONCILED) {
    createState.value = CREATE_STATE.READY
    createTripVisible.value = false
    destinationInput.value = ''
    if (result.type === CREATE_RESULT.CREATED) showSuccessToast('安心行程创建成功')
  }
}

async function refreshUnknownTripState() {
  if (!realMode || refreshingUnknownTrip.value) return

  const result = await refreshUnknownCreation({
    isPending: () => refreshingUnknownTrip.value,
    setPending: (pending) => { refreshingUnknownTrip.value = pending },
    refreshTrip: loadCurrentTrip
  })

  if (result.type === CREATE_RESULT.READY) {
    createState.value = CREATE_STATE.READY
    return
  }
  if (result.type === CREATE_RESULT.RECONCILED) {
    createState.value = CREATE_STATE.READY
    createTripVisible.value = false
    destinationInput.value = ''
  }
}

// FIX START: 开始/结束行程时调用真实 API，并始终传递 trip.id。
async function toggleTrip() {
  if (isTripActive.value) {
    try {
      await showConfirmDialog({ title: '结束本次出游？', message: '确认已经安全回到家了吗？' })
    } catch {
      return
    }

    try {
      if (realMode) {
        if (!currentTripId.value) throw new Error('没有可结束的行程')
        await tripApi.end(currentTripId.value)
        await loadCurrentTrip()
      } else {
        currentTripBackendStatus.value = null
        tripDataAvailable.value = true
        tripStatus.value = '已返程'
        locationStatus.value = '已停止定位'
      }
      showSuccessToast('出游已结束，辛苦了')
    } catch (error) {
      showFailToast(error instanceof Error ? error.message : '结束行程失败')
    }
    return
  }

  if (!realMode) {
    try {
      await startTripForMode({
        realMode,
        trip: currentTrip.value,
        startExisting: (tripId) => tripApi.start(tripId),
        startDemo: async () => ({ id: currentTripId.value, destination: elder.destination, status: 'active' })
      })
      currentTripBackendStatus.value = 'active'
      tripDataAvailable.value = true
      tripStatus.value = '出游中'
      locationStatus.value = '模拟定位正常'
      showSuccessToast('演示行程已开始，正在显示模拟位置')
    } catch (error) {
      showFailToast(error instanceof Error ? error.message : '开始行程失败')
    }
    return
  }

  if (startingTrip.value) return
  const result = await startTripAndRefresh({
    trip: currentTrip.value,
    isPending: () => startingTrip.value,
    setPending: (pending) => { startingTrip.value = pending },
    startTrip: (tripId) => tripApi.start(tripId),
    refreshTrip: loadCurrentTrip
  })

  if (result.type === START_RESULT.INVALID) {
    showFailToast('只有待出发且目的地有效的行程可以开始')
  } else if (result.type === START_RESULT.REJECTED) {
    showFailToast(result.error?.message || '开始行程请求被拒绝')
  } else if (result.type === START_RESULT.UNKNOWN) {
    showFailToast('行程状态暂时无法确认，请稍后刷新页面')
  } else if (result.trip?.status === 'active') {
    showSuccessToast('出游已开始，等待定位数据上报')
  }
}
// FIX END: 开始/结束行程时调用真实 API，并始终传递 trip.id。

async function emergency() {
  if (sosSending.value) return
  if (!realMode) {
    showDialog({ title: '紧急求助（演示）', message: '这是 SOS 演示操作，不会向后端发送告警，也不会发起电话拨号。', confirmButtonText: '知道了' })
    return
  }
  if (!tripDataAvailable.value) {
    showFailToast('行程状态未知，求助未发送')
    return
  }
  if (!currentTripId.value || currentTripBackendStatus.value !== 'active') {
    showFailToast('只有进行中的行程可以发送求助')
    return
  }

  sosResult.value = ''
  try {
    const submission = await runSosSubmission({
      isPending: () => sosSending.value,
      setPending: (pending) => { sosSending.value = pending },
      submit: () => alertApi.sos(currentTripId.value)
    })
    if (!submission.submitted) return
    const alert = submission.value
    sosResult.value = presentSosSuccess(alert)
    await showDialog({ title: '求助已由后端记录', message: sosResult.value, confirmButtonText: '知道了' })
  } catch (error) {
    sosResult.value = presentSosFailure(error)
    showFailToast(sosResult.value)
  }
}

function confirmAiPlan() {
  showAiPlan.value = false
  if (!realMode) showSuccessToast('演示安排已记住')
}

async function sendAiMessage() {
  const message = aiInput.value.trim()
  if (!message || aiLoading.value) return
  aiMessages.value.push({ role: 'user', text: message })
  aiInput.value = ''
  aiLoading.value = true
  try {
    if (!isApiConfigured()) throw new Error('API_DISABLED')
    const result = await aiApi.chat(message, elder.id, elder.name)
    aiMessages.value.push({ role: 'assistant', text: result.reply })
  } catch (error) {
    const fallback = error.message === 'API_DISABLED'
      ? '演示模式下我可以帮您查看和整理行程。连接后端后，我会根据您的话生成新的安排。'
      : '现在暂时联系不上小助手，请稍后再试，也可以让家人帮您安排。'
    aiMessages.value.push({ role: 'assistant', text: fallback })
  } finally { aiLoading.value = false }
}

function go(path) { router.push(path) }
</script>

<template>
  <div class="elder-page">
    <header class="elder-header"><div class="brand"><img class="brand-logo" :src="logo" alt="星斗守眼安游"/><strong>银发独游</strong></div><button type="button" aria-label="个人信息" @click="go('/elder/profile')"><van-icon name="manager-o" /></button><p>您好，{{ elder.name }}</p><small>{{ elder.age }} 岁 · {{ realMode ? '真实模式' : '演示守护中' }}</small></header>
    <main class="elder-content">
      <section class="status-card"><div class="status-icon"><van-icon :name="isTripActive ? 'location-o' : 'home-o'" /></div><div><small>当前状态</small><strong>{{ tripStatus }}</strong><p v-if="isTripActive && hasUsableDestination">正在前往：{{ elder.destination }}</p><p v-else-if="realMode && !tripDataAvailable">后端行程数据不可用</p><p v-else-if="realMode && currentTrip && !hasUsableDestination">行程目的地无效，请先设置真实目的地</p><p v-else-if="realMode && currentTrip">待出发：{{ elder.destination }}</p><p v-else>{{ realMode ? '当前没有进行中的真实行程' : '欢迎回家，今天辛苦了' }}</p></div><span :class="['status-dot', { off: !isTripActive }]" /></section>
      <!-- FIX START: 显示脚本中随 API 行程状态更新的 locationStatus。 -->
      <section class="location-card"><div><small>我的位置</small><strong>{{ locationStatus }}</strong><p>{{ isTripActive ? (realMode ? '等待定位数据上传后供家人查看' : '演示：显示模拟位置') : (realMode ? '开始出游后等待定位数据上传' : '演示：开始后显示模拟定位') }}</p></div><van-icon :class="{ paused: !isTripActive }" name="aim" /></section>
      <!-- FIX END: 显示真实的 locationStatus。 -->
      <button class="plan-card" type="button" @click="go('/schedule')"><div class="plan-title"><div><small>今日出游计划</small><strong>{{ planPresentation.title }}</strong></div><van-icon name="arrow" /></div><template v-if="planPresentation.kind === 'demo'"><div class="plan-row"><span><b>08:30</b><small>专车到家</small></span><i></i><span><b>09:00</b><small>到达公园</small></span><i></i><span><b>15:30</b><small>专车回家</small></span></div><p><van-icon name="info-o" /> 演示：沿平整步道游览，途中有休息区</p></template><p v-else-if="planPresentation.kind === 'ready'"><van-icon name="info-o" /> 目的地来自后端；当前接口未提供详细时间安排</p><p v-else><van-icon name="info-o" /> {{ planPresentation.title }}</p></button>
      <section v-if="isCreateUnknown" class="create-state-card"><strong>行程请求结果暂时无法确认</strong><van-button block round type="primary" color="#667eea" :loading="refreshingUnknownTrip" :disabled="refreshingUnknownTrip" @click="refreshUnknownTripState">刷新行程状态</van-button></section>
      <button v-else-if="showCreateTrip" class="create-trip-entry" type="button" @click="createTripVisible = true"><van-icon name="plus" /><span>设置目的地</span></button>
      <button class="main-action" type="button" :disabled="tripActionDisabled" @click="toggleTrip"><van-icon :name="isTripActive ? 'stop-circle-o' : 'play-circle-o'" /><span>{{ isTripActive ? '结束本次出游' : '开始出游' }}</span><small>{{ tripActionHint }}</small></button>
      <!-- FIX START: 给已经实现但没有入口的仿真组件增加可见入口。 -->
      <section class="quick-actions"><button type="button" @click="go('/schedule')"><span class="purple"><van-icon name="todo-list-o" /></span><strong>我的行程</strong><small>查看今天安排</small></button><button v-if="!realMode" type="button" @click="go('/simulation')"><span class="purple"><van-icon name="aim" /></span><strong>定位仿真</strong><small>演示轨迹与围栏告警</small></button><button type="button" :disabled="sosSending" @click="emergency"><span class="red"><van-icon name="warning-o" /></span><strong>{{ sosSending ? '正在发送' : '紧急求助' }}</strong><small>{{ realMode ? '发送至后端告警中心' : '演示操作' }}</small></button></section>
      <p v-if="sosResult" class="sos-result">{{ sosResult }}</p>
      <!-- FIX END: 给仿真组件增加可见入口。 -->
      <button class="ai-plan-card" type="button" @click="showAiChat = true"><span class="ai-badge"><van-icon name="service-o" /></span><div><small>AI 行程管家</small><strong>和小助手说说您的出游想法</strong><p>我会帮您整理安排，确认后再上传</p></div><van-icon name="arrow" /></button>
      <button class="more-button" type="button" @click="showMore = !showMore">{{ showMore ? '收起更多' : '更多信息' }} <van-icon :name="showMore ? 'arrow-up' : 'arrow-down'" /></button>
      <div v-if="showMore" class="more-card"><van-cell title="目的地" :value="elder.destination || '暂无真实行程'"/><van-cell title="最后更新" :value="elder.lastUpdate"/><van-cell title="紧急联系人" :value="elder.family"/><van-cell title="联系电话" :value="elder.familyPhone"/></div>
      <p class="privacy-note">{{ realMode ? '真实模式 · SOS 结果以后端 Alert 为准' : '演示页面 · 姓名、位置和联系电话均为虚构数据' }}</p>
    </main>
    <van-popup v-model:show="createTripVisible" round position="bottom" :close-on-click-overlay="!creatingTrip && !isCreateUnknown" :close-on-popstate="!creatingTrip && !isCreateUnknown" :style="{ padding: '20px 16px 24px' }"><div v-if="isCreateUnknown" class="create-trip-popup create-unknown-popup"><strong>行程请求结果暂时无法确认</strong><van-button block round type="primary" color="#667eea" :loading="refreshingUnknownTrip" :disabled="refreshingUnknownTrip" @click="refreshUnknownTripState">刷新行程状态</van-button></div><div v-else class="create-trip-popup"><strong>创建安心行程</strong><van-field v-model="destinationInput" label="目的地" maxlength="200" show-word-limit clearable placeholder="请输入目的地" @keyup.enter="createRealTrip"/><div class="create-trip-buttons"><van-button round plain :disabled="creatingTrip" @click="createTripVisible = false">取消</van-button><van-button round type="primary" color="#667eea" :loading="creatingTrip" :disabled="creatingTrip || !isValidDestination(destinationInput)" @click="createRealTrip">创建安心行程</van-button></div></div></van-popup>
    <van-popup v-model:show="showAiPlan" round position="bottom" :style="{ padding: '20px 16px 24px' }"><div class="ai-plan-popup"><div class="ai-popup-title"><span class="ai-badge"><van-icon name="service-o" /></span><div><strong>{{ realMode ? '后端真实行程' : 'AI 演示安排' }}</strong><small>{{ realMode ? '仅展示后端已返回的数据' : '演示提醒，不会写入真实业务状态' }}</small></div></div><div v-if="!realMode" class="ai-timeline"><p><b>08:30</b><span>专车到家</span></p><p><b>09:00</b><span>到达天坛公园，慢慢游览</span></p><p><b>15:30</b><span>专车接您回家</span></p></div><div v-else class="ai-timeline"><p><b>目的地</b><span>{{ realDestinationOrPlaceholder(currentTrip) }}</span></p><p><b>详情</b><span>当前后端未提供详细时间安排</span></p></div><van-button block round type="primary" color="#667eea" @click="confirmAiPlan">{{ realMode ? '关闭' : '好的，我知道了' }}</van-button></div></van-popup>
    <van-popup v-model:show="showAiChat" round position="bottom" :style="{ padding: '18px 16px 20px' }"><div class="ai-chat-popup"><div class="ai-popup-title"><span class="ai-badge"><van-icon name="service-o" /></span><div><strong>行程小助手</strong><small>告诉我想去哪里、什么时候出发</small></div></div><div class="ai-messages"><div v-for="(item, index) in aiMessages" :key="index" :class="['ai-message', item.role]"><span>{{ item.text }}</span></div><div v-if="aiLoading" class="ai-message assistant"><span>正在帮您想一想…</span></div></div><div class="ai-quick"><button type="button" @click="aiInput='帮我安排明天出游'">安排明天出游</button><button type="button" @click="aiInput='看看我今天的行程'">查看今天行程</button></div><div class="ai-input-row"><van-field v-model="aiInput" clearable placeholder="例如：帮我安排明天出游" @keyup.enter="sendAiMessage"/><van-button round type="primary" color="#667eea" :loading="aiLoading" @click="sendAiMessage">发送</van-button></div><van-button block round plain type="primary" @click="showAiPlan = true; showAiChat = false">查看今日安排</van-button></div></van-popup>
    <nav class="elder-nav"><button class="active" type="button"><van-icon name="home-o"/><small>首页</small></button><button type="button" @click="go('/schedule')"><van-icon name="todo-list-o"/><small>行程</small></button><button type="button" @click="go('/elder/profile')"><van-icon name="manager-o"/><small>我的</small></button></nav>
  </div>
</template>

<style scoped>
*{box-sizing:border-box}.elder-page{min-height:100vh;padding-bottom:72px;color:#323233;background:#f5f5f5}.elder-header{position:relative;padding:18px 18px 42px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.brand{display:flex;align-items:center;gap:9px}.brand span{width:34px;height:34px;display:grid;place-items:center;border-radius:11px;background:rgba(255,255,255,.18);font-weight:700}.brand strong{font-size:16px}.elder-header>button{position:absolute;right:18px;top:18px;width:34px;height:34px;color:white;border:0;border-radius:50%;background:rgba(255,255,255,.15)}.elder-header>p{margin-top:26px;color:rgba(255,255,255,.78);font-size:13px}.elder-header h1{margin:3px 0 6px;color:white;font-size:25px;font-weight:700}.elder-header>small{color:rgba(255,255,255,.75);font-size:12px}.elder-content{max-width:600px;margin:auto;padding:0 14px}.status-card,.location-card{display:flex;align-items:center;gap:12px;padding:16px;border-radius:12px;background:white;box-shadow:0 3px 12px rgba(45,33,82,.08)}.status-card{margin-top:-25px}.status-icon{width:44px;height:44px;display:grid;place-items:center;color:#667eea;border-radius:13px;background:#efecfa;font-size:23px}.status-card>div:nth-child(2){flex:1}.status-card small,.status-card strong,.status-card p,.location-card small,.location-card strong,.location-card p{display:block}.status-card small,.location-card small{color:#969799;font-size:11px}.status-card strong{margin:2px 0;color:#6657a5;font-size:20px}.status-card p,.location-card p{color:#646566;font-size:11px}.status-dot{width:9px;height:9px;border-radius:50%;background:#52b681;box-shadow:0 0 0 4px #e8f8f0}.status-dot.off{background:#b5b6ba;box-shadow:0 0 0 4px #f0f1f2}.location-card{margin-top:10px;justify-content:space-between}.location-card>div{flex:1}.location-card strong{margin:2px 0;color:#3d9a6a;font-size:15px}.location-card .van-icon{width:40px;height:40px;display:grid;place-items:center;color:#667eea;border-radius:50%;background:#f0edfb;font-size:22px}.location-card .paused{color:#969799;background:#f2f3f5}.main-action{width:100%;display:flex;align-items:center;gap:10px;margin-top:14px;padding:15px 17px;color:white;border:0;border-radius:12px;background:linear-gradient(135deg,#667eea,#764ba2);box-shadow:0 7px 16px rgba(93,76,163,.22);text-align:left}.main-action>.van-icon{font-size:30px}.main-action span{font-size:16px;font-weight:700}.main-action small{margin-left:auto;color:rgba(255,255,255,.78);font-size:9px}.quick-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.quick-actions button{padding:15px;border:0;border-radius:12px;background:white;text-align:left}.quick-actions span{width:34px;height:34px;display:grid;place-items:center;margin-bottom:8px;border-radius:10px;font-size:18px}.quick-actions .purple{color:#6657a5;background:#efecfa}.quick-actions .red{color:#e55d67;background:#fff0f1}.quick-actions strong,.quick-actions small{display:block}.quick-actions strong{font-size:14px}.quick-actions small{margin-top:3px;color:#969799;font-size:10px}.more-button{width:100%;margin-top:16px;padding:9px;color:#667eea;border:0;background:transparent;font-size:12px}.more-card{overflow:hidden;border-radius:10px;background:white}.more-card :deep(.van-cell){padding:12px 14px}.privacy-note{margin:18px 0;color:#b0aab4;text-align:center;font-size:9px}.elder-nav{position:fixed;inset:auto 0 0;z-index:5;height:62px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97)}.elder-nav button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;color:#969799;border:0;background:transparent}.elder-nav button.active{color:#667eea}.elder-nav button .van-icon{font-size:20px}.elder-nav small{font-size:10px}
.plan-card{width:100%;margin-top:10px;padding:15px;border:0;border-radius:12px;background:white;text-align:left}.plan-title{display:flex;align-items:center;justify-content:space-between}.plan-title small,.plan-title strong{display:block}.plan-title small{color:#969799;font-size:11px}.plan-title strong{margin-top:3px;color:#323233;font-size:16px}.plan-title>.van-icon{color:#aaa2b2}.plan-row{display:flex;align-items:center;margin:17px 2px 12px}.plan-row span{display:flex;flex-direction:column;gap:3px}.plan-row b{color:#6657a5;font-size:13px}.plan-row small{color:#969799;font-size:9px}.plan-row i{flex:1;height:1px;margin:0 8px;background:#dcd8ed}.plan-card>p{padding-top:10px;color:#8b7a4f;border-top:1px solid #f1eee5;font-size:10px}.plan-card>p .van-icon{margin-right:3px;color:#d49a43}
 .ai-plan-card{width:100%;display:flex;align-items:center;gap:10px;margin-top:12px;padding:14px;border:1px solid #e8e3f7;border-radius:12px;background:#fff;text-align:left}.ai-plan-card>div{flex:1}.ai-plan-card small,.ai-plan-card strong,.ai-plan-card p{display:block}.ai-plan-card small{color:#8a7fb1;font-size:10px}.ai-plan-card strong{margin-top:3px;color:#403675;font-size:14px}.ai-plan-card p{margin-top:4px;color:#969799;font-size:10px}.ai-plan-card>.van-icon{color:#aaa2b2}.ai-badge{width:36px;height:36px;display:grid;place-items:center;flex:none;color:#6657a5;border-radius:11px;background:#efecfa;font-size:19px}.ai-popup-title{display:flex;align-items:center;gap:10px}.ai-popup-title strong,.ai-popup-title small{display:block}.ai-popup-title strong{color:#403675;font-size:18px}.ai-popup-title small{margin-top:4px;color:#969799;font-size:11px}.ai-timeline{margin:18px 0;padding:3px 0 3px 15px;border-left:2px solid #ddd7f2}.ai-timeline p{display:flex;gap:14px;margin:13px 0;color:#646566;font-size:13px}.ai-timeline b{width:42px;color:#6657a5}.ai-timeline span{flex:1}
</style>
<style scoped>
.elder-header{padding-bottom:22px}.status-card{margin-top:14px}
</style>
<style scoped>
.elder-page { width: 100%; max-width: 430px; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); } .elder-nav { left: 50%; right: auto; width: min(100%,430px); transform: translateX(-50%); }
</style>
<style scoped>
.brand-logo { width: 34px; height: 34px; object-fit: contain; border-radius: 11px; background: #fff; }
</style>
<style scoped>
.elder-header { z-index: 0; }
.elder-content { position: relative; z-index: 1; }
</style>
<style scoped>
.brand strong { line-height: 1; transform: translateY(3px); }
</style>
<style scoped>
.ai-chat-popup { color: #323233; }
.ai-messages { display: grid; gap: 8px; max-height: 240px; overflow-y: auto; margin: 16px 0 10px; padding: 4px 2px; }
.ai-message { display: flex; font-size: 12px; line-height: 1.55; }
.ai-message span { max-width: 86%; padding: 8px 11px; border-radius: 12px; background: #f2f0fa; }
.ai-message.user { justify-content: flex-end; }.ai-message.user span { color: white; background: #667eea; }
.ai-quick { display: flex; gap: 7px; overflow-x: auto; margin-bottom: 9px; }.ai-quick button { flex: none; padding: 7px 10px; color: #6657a5; border: 1px solid #e1dcf3; border-radius: 14px; background: #faf9fe; font-size: 10px; }
.ai-input-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }.ai-input-row :deep(.van-cell) { flex: 1; padding: 8px 10px; border-radius: 20px; background: #f5f5f5; }.ai-input-row .van-button { width: 58px; height: 36px; padding: 0; font-size: 11px; }
.quick-actions button:disabled{cursor:wait;opacity:.65}.sos-result{margin:10px 2px 0;padding:9px 11px;color:#6657a5;border-radius:9px;background:#f0edfb;font-size:10px;line-height:1.5}
.create-trip-entry{width:100%;display:flex;align-items:center;justify-content:center;gap:7px;margin-top:12px;padding:13px;color:#6657a5;border:1px solid #ded7f3;border-radius:12px;background:#fff;font-size:15px;font-weight:700}.create-state-card{display:grid;gap:12px;margin-top:12px;padding:15px;color:#6657a5;border:1px solid #ded7f3;border-radius:12px;background:#fff}.create-state-card strong{text-align:center;font-size:14px}.create-trip-popup{display:grid;gap:16px;color:#323233}.create-trip-popup>strong{font-size:19px}.create-trip-popup :deep(.van-cell){padding:10px 0}.create-trip-buttons{display:grid;grid-template-columns:1fr 2fr;gap:10px}.create-unknown-popup{padding-top:4px;text-align:center}
</style>
