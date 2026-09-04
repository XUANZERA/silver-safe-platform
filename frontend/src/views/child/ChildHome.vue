<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showSuccessToast } from 'vant'
import { elderApi, isApiConfigured } from '../../services/api'
import { loadDemoItinerary, realDestinationOrPlaceholder } from '../../services/modeBoundary'
import { nextFamilyAttentionState } from '../../services/modePresentation'
import { createPollingController, normalizePollingInterval } from '../../services/polling'
import { presentAlertWorkflow, presentRisk, presentSafety } from '../../services/safetyPresentation'

const router = useRouter()
const realMode = isApiConfigured()
const activeAlert = ref(false)
const stateAvailable = ref(!realMode)
const stateLoading = ref(false)
const stateError = ref('')
const safetyView = ref(null)
const alerts = ref([])
const elder = reactive({
  id: realMode ? null : 1001,
  tripId: null,
  name: realMode ? '老人' : '张建国',
  location: realMode ? '等待后端数据' : '天坛公园东门附近',
  update: realMode ? '尚未同步' : '刚刚',
  destination: realMode ? '暂无真实行程' : '天坛公园慢游'
})

const safetyPresentation = computed(() => realMode
  ? presentSafety(safetyView.value, stateAvailable.value)
  : { trip: '出游中', location: '演示定位', risk: '演示围栏内', tone: 'demo' })
const latestOpenAlert = computed(() => {
  const fromSafety = safetyView.value?.latest_open_alert
  if (fromSafety) return fromSafety
  return alerts.value.find((item) => item.status === 'new' || item.status === 'processing') || null
})
const riskPresentation = computed(() => presentRisk(safetyView.value, stateAvailable.value))
const alertPresentation = computed(() => presentAlertWorkflow(latestOpenAlert.value, stateAvailable.value))

function applySavedItinerary() {
  const items = loadDemoItinerary(realMode, sessionStorage)
  const destinationItem = items?.[1] || items?.[0]
  if (destinationItem?.title) elder.destination = destinationItem.title
}

function formatLocation(location) {
  if (!location) return '暂无后端定位'
  return `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`
}

function formatTime(value) {
  if (!value) return '尚未同步'
  return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function loadAuthoritativeState() {
  stateLoading.value = true
  try {
    const elderList = await elderApi.list()
    const currentElder = elderList?.items?.[0]
    if (!currentElder) throw new Error('没有可查看的老人资料')
    const [view, alertList, trip] = await Promise.all([
      elderApi.safety(currentElder.id),
      elderApi.alerts(currentElder.id),
      elderApi.currentTrip(currentElder.id)
    ])
    if (!view) throw new Error('后端未返回安全状态')

    const latestLocation = view.latest_location
    Object.assign(elder, {
      id: currentElder.id,
      tripId: trip?.id || null,
      name: currentElder.name,
      destination: realDestinationOrPlaceholder(trip),
      location: formatLocation(latestLocation),
      update: formatTime(latestLocation?.recorded_at)
    })
    safetyView.value = view
    alerts.value = alertList?.items || []
    stateAvailable.value = true
    stateError.value = ''
  } finally {
    stateLoading.value = false
  }
}

const polling = createPollingController({
  intervalMs: normalizePollingInterval(import.meta.env.VITE_MONITORING_POLL_INTERVAL_MS),
  task: loadAuthoritativeState,
  onError(error) {
    stateAvailable.value = false
    stateError.value = error instanceof Error ? error.message : '无法获取最新状态'
    elder.location = '数据不可用'
    elder.update = '无法获取最新状态'
    console.warn('家属端后端状态同步失败', error)
  }
})

function handleVisibilityChange() {
  if (document.hidden) polling.stop()
  else void polling.start()
}

onMounted(() => {
  applySavedItinerary()
  if (!realMode) return
  document.addEventListener('visibilitychange', handleVisibilityChange)
  void polling.start()
})

onBeforeUnmount(() => {
  polling.stop()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

async function refresh() {
  if (!realMode) {
    elder.update = '刚刚（演示数据）'
    showSuccessToast('演示位置已刷新')
    return
  }
  const result = await polling.refresh()
  if (result.ok) showSuccessToast('后端状态已刷新')
  else showDialog({ title: '状态更新失败', message: stateError.value || '无法获取最新状态' })
}

function call() {
  showDialog({
    title: '老人联系信息',
    message: realMode ? '当前版本暂未接入拨号功能。' : '演示环境不会拨打真实电话。',
    confirmButtonText: '知道了'
  })
}

function toggleDemoAttention() {
  activeAlert.value = nextFamilyAttentionState(realMode, activeAlert.value)
}
</script>
<template>
  <div class="child-page">
    <header class="child-header">
      <div class="brand"><span>银</span><strong>银发独游</strong></div>
      <button type="button" @click="router.push('/child/profile')"><van-icon name="manager-o" /></button>
      <p>家人守护中心</p><h1>{{ elder.name }}现在安全吗？</h1><small>位置与出游状态定时同步</small>
    </header>
    <main>
      <section class="elder-card">
        <div class="elder-avatar">{{ elder.name.slice(0, 1) }}</div>
        <div class="elder-title"><strong>{{ elder.name }}</strong><small>我的家人 · {{ elder.destination }}</small></div>
        <span class="online" :class="{ unavailable: realMode && !stateAvailable }"><i></i>{{ realMode ? (stateAvailable ? '后端已同步' : '数据不可用') : '演示模式' }}</span>
      </section>
      <section class="location-card">
        <div class="map-placeholder"><span class="fence"></span><span class="pin"><van-icon name="location" /></span><em>{{ elder.location }}</em></div>
        <div class="location-info">
          <div><strong>{{ safetyPresentation.trip }}</strong><p>最后定位：{{ elder.update }}</p></div>
          <button type="button" :disabled="stateLoading" @click="refresh"><van-icon name="replay" />{{ stateLoading ? '同步中' : '刷新状态' }}</button>
        </div>
      </section>
      <section v-if="realMode" class="status-grid">
        <div><small>Trip status</small><strong>{{ safetyPresentation.trip }}</strong></div>
        <div><small>Location health</small><strong>{{ safetyPresentation.location }}</strong></div>
        <div><small>Risk status</small><strong>{{ safetyPresentation.risk }}</strong></div>
        <div><small>Open alerts</small><strong>{{ stateAvailable ? safetyView?.open_alert_count : '不可用' }}</strong></div>
      </section>
      <section v-if="realMode" class="notice-card risk-card" :class="riskPresentation.tone">
        <van-icon :name="riskPresentation.tone === 'danger' ? 'warning-o' : 'shield-o'" />
        <div>
          <small>当前风险</small>
          <strong>{{ riskPresentation.label }}</strong>
          <p>{{ stateAvailable ? safetyPresentation.location : (stateError || '后端状态尚未同步') }}</p>
        </div>
      </section>
      <section v-if="realMode" class="event-card" :class="alertPresentation.tone">
        <van-icon name="records-o" />
        <div>
          <small>事件处置</small>
          <strong>{{ alertPresentation.label }}</strong>
          <p v-if="alertPresentation.detail">{{ alertPresentation.detail }}</p>
        </div>
      </section>
      <section v-else class="notice-card demo">
        <van-icon name="shield-o" />
        <div><strong>演示状态：围栏内</strong><p>这是 Mock 展示，不代表后端真实安全结论。</p></div>
      </section>
      <section class="child-actions">
        <button type="button" @click="router.push('/schedule')"><span class="purple"><van-icon name="todo-list-o"/></span><strong>查看出游计划</strong><small>了解今天的安排</small></button>
        <button type="button" @click="call"><span class="red"><van-icon name="records-o"/></span><strong>查看老人联系信息</strong><small>{{ realMode ? '当前接口未提供可拨号码' : '电话为脱敏演示号码' }}</small></button>
      </section>
      <button v-if="!realMode" class="alert-button" type="button" @click="toggleDemoAttention"><van-icon name="warning-o"/> {{ activeAlert ? '已开启演示重点关注' : '开启演示重点关注' }}</button>
      <p v-else class="attention-unavailable">重点关注功能尚未接入</p>
      <p class="note">{{ realMode ? '真实模式 · 状态来自后端派生视图' : '演示模式 · 姓名、位置和电话均为虚构数据' }}</p>
    </main>
    <nav class="child-nav"><button class="active"><van-icon name="home-o"/><small>首页</small></button><button @click="router.push('/schedule')"><van-icon name="todo-list-o"/><small>行程</small></button><button @click="router.push('/child/profile')"><van-icon name="manager-o"/><small>我的</small></button></nav>
  </div>
</template>
<style scoped>
*{box-sizing:border-box}.child-page{min-height:100vh;padding-bottom:72px;color:#323233;background:#f5f5f5}.child-header{position:relative;padding:18px 18px 42px;color:#fff;background:linear-gradient(135deg,#667eea,#764ba2)}.brand{display:flex;align-items:center;gap:8px}.brand span{width:34px;height:34px;display:grid;place-items:center;border-radius:11px;background:rgba(255,255,255,.18);font-weight:700}.brand strong{font-size:16px}.child-header>button{position:absolute;right:18px;top:18px;width:34px;height:34px;color:#fff;border:0;border-radius:50%;background:rgba(255,255,255,.15)}.child-header>p{margin-top:25px;color:rgba(255,255,255,.78);font-size:12px}.child-header h1{margin:4px 0;color:#fff;font-size:23px}.child-header>small{color:rgba(255,255,255,.75);font-size:11px}.child-page main{max-width:600px;margin:auto;padding:0 14px}.elder-card{display:flex;align-items:center;gap:10px;margin-top:-25px;padding:14px;border-radius:12px;background:#fff;box-shadow:0 3px 12px rgba(45,33,82,.08)}.elder-avatar{width:42px;height:42px;display:grid;place-items:center;color:#6657a5;border-radius:50%;background:#efecfa;font-size:16px;font-weight:700}.elder-title{flex:1}.elder-title strong,.elder-title small{display:block}.elder-title strong{font-size:15px}.elder-title small{margin-top:3px;color:#969799;font-size:10px}.online{color:#3d9a6a;font-size:10px}.online i{display:inline-block;width:7px;height:7px;margin-right:4px;border-radius:50%;background:#50b47f}.location-card{margin-top:10px;overflow:hidden;border-radius:12px;background:#fff}.map-placeholder{position:relative;height:180px;overflow:hidden;background:linear-gradient(135deg,#edf2ea,#e7edf2)}.map-placeholder:before,.map-placeholder:after{content:'';position:absolute;background:rgba(255,255,255,.9)}.map-placeholder:before{width:120%;height:24px;left:-10%;top:78px;transform:rotate(-14deg)}.map-placeholder:after{width:22px;height:120%;left:58%;top:-10%;transform:rotate(17deg)}.fence{position:absolute;left:50%;top:50%;width:110px;height:110px;border:2px solid rgba(102,126,234,.5);border-radius:50%;background:rgba(102,126,234,.1);transform:translate(-50%,-50%)}.pin{position:absolute;left:50%;top:47%;z-index:2;width:32px;height:32px;display:grid;place-items:center;color:#fff;border:3px solid #fff;border-radius:50%;background:#667eea;transform:translate(-50%,-50%)}.map-placeholder em{position:absolute;left:50%;top:68%;z-index:2;padding:5px 8px;color:#4f4669;border-radius:9px;background:rgba(255,255,255,.9);font-size:9px;font-style:normal;transform:translateX(-50%);white-space:nowrap}.location-info{display:flex;align-items:center;padding:13px 15px}.location-info strong,.location-info p{display:block}.location-info strong{color:#3d9a6a;font-size:15px}.location-info p{margin-top:3px;color:#969799;font-size:10px}.location-info button{margin-left:auto;padding:7px 10px;color:#667eea;border:0;border-radius:16px;background:#efecfa;font-size:10px}.notice-card{display:flex;gap:10px;align-items:flex-start;margin-top:10px;padding:14px;color:#3d9a6a;border-radius:10px;background:#eaf8f1}.notice-card>.van-icon{font-size:20px}.notice-card strong{font-size:13px}.notice-card p{margin-top:3px;color:#5b8c70;font-size:10px;line-height:1.5}.child-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.child-actions button{padding:15px;border:0;border-radius:12px;background:#fff;text-align:left}.child-actions span{width:34px;height:34px;display:grid;place-items:center;margin-bottom:8px;border-radius:10px;font-size:18px}.child-actions .purple{color:#6657a5;background:#efecfa}.child-actions .red{color:#e25e66;background:#fff0f1}.child-actions strong,.child-actions small{display:block}.child-actions strong{font-size:13px}.child-actions small{margin-top:3px;color:#969799;font-size:9px}.alert-button{width:100%;margin-top:13px;padding:12px;color:#d78335;border:1px solid #f2d2a9;border-radius:22px;background:#fff8ec;font-size:12px}.note{margin:18px 0;color:#b0aab4;text-align:center;font-size:9px}.child-nav{position:fixed;inset:auto 0 0;z-index:5;height:62px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97)}.child-nav button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;color:#969799;border:0;background:transparent}.child-nav button.active{color:#667eea}.child-nav .van-icon{font-size:20px}.child-nav small{font-size:10px}
</style>
<style scoped>
.child-header{padding:16px 18px 18px;min-height:76px}.child-page main{padding-top:14px}.elder-card{margin-top:0}
</style>
<style scoped>
.child-page { width: 100%; max-width: 430px; min-height: 100vh; margin: 0 auto; box-shadow: 0 0 28px rgba(38, 26, 72, .14); }
.child-nav { left: 50%; right: auto; width: min(100%, 430px); transform: translateX(-50%); }
</style>
<style scoped>
.child-header > p,.child-header > h1,.child-header > small{display:none}
.child-header{padding-bottom:24px}
.child-page main{position:relative;z-index:1}
.brand span{color:transparent;font-size:0;background:#fff url('/src/assets/logo.png') center/contain no-repeat}
.brand strong{line-height:1;transform:translateY(3px)}
</style>
<style scoped>
.online.unavailable{color:#b36b45}.online.unavailable i{background:#d18a60}.location-info button:disabled{cursor:wait;opacity:.6}.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.status-grid div{padding:11px;border-radius:10px;background:#fff}.status-grid small,.status-grid strong{display:block}.status-grid small{color:#969799;font-size:9px}.status-grid strong{margin-top:4px;font-size:11px}.notice-card small,.event-card small{display:block;margin-bottom:3px;color:inherit;font-size:9px}.notice-card.neutral{color:#7d6f67;background:#f1efed}.notice-card.neutral p{color:#7d6f67}.notice-card.warning{color:#a26725;background:#fff7e8}.notice-card.warning p{color:#966b37}.notice-card.danger{color:#c64048;background:#fff0f1}.notice-card.danger p{color:#a4555a}.notice-card.demo{color:#6657a5;background:#f1effa}.notice-card.demo p{color:#756c91}.event-card{display:flex;gap:10px;align-items:flex-start;margin-top:10px;padding:14px;color:#646566;border-radius:10px;background:#fff}.event-card>.van-icon{font-size:20px}.event-card strong{font-size:13px}.event-card p{margin-top:3px;font-size:10px}.event-card.warning{color:#a26725;background:#fff7e8}.event-card.processing{color:#5d5a9d;background:#f1effa}.event-card.success{color:#3d9a6a;background:#eaf8f1}.event-card.neutral{color:#7d6f67;background:#f1efed}.attention-unavailable{margin-top:13px;padding:12px;color:#7d6f67;border:1px solid #dedad7;border-radius:22px;background:#f5f3f1;font-size:12px;text-align:center}
</style>
