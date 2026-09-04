<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast, showSuccessToast } from 'vant'
import { useUserStore } from '../../stores/user'
import { alertHistory, alerts as alertSeed, elders as elderSeed, operatorOverview, trips as tripSeed } from '../../mock/operator'
import AlertsPanel from './AlertsPanel.vue'
import EldersPanel from './EldersPanel.vue'
import TripsPanel from './TripsPanel.vue'
import { alertApi, elderApi, isApiConfigured, logoutRequest } from '../../services/api'
import { logoutForMode } from '../../services/modeBoundary'
import {
  replaceAuthoritativeOperatorSnapshot,
  runOperatorAlertAction,
  selectOperatorTrips,
  syncDemoElderState
} from '../../services/operatorAlerts'
import { createPollingController, normalizePollingInterval } from '../../services/polling'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const realMode = isApiConfigured()
const activeNav = ref(['overview', 'alerts', 'elders', 'trips'].includes(route.query.view) ? route.query.view : 'overview')
const showAccount = ref(false)
const alerts = reactive((realMode ? [] : [...alertSeed, ...alertHistory]).map((alert) => ({ ...alert })))
const elders = reactive((realMode ? [] : elderSeed).map((elder) => ({ ...elder })))
const trips = reactive(selectOperatorTrips(realMode, tripSeed))
const operatorDataAvailable = ref(!realMode)
const operatorError = ref('')
const operatorActionId = ref(null)
const liveAlerts = computed(() => alerts.filter((alert) => alert.status !== '已解决'))
const unresolvedAlertCount = computed(() => liveAlerts.value.length)
const activeTripCount = computed(() => trips.filter((trip) => trip.status === '进行中').length)
const resolvedCount = computed(() => alerts.filter((alert) => alert.status === '已解决' && !alert.time.startsWith('昨天')).length + (realMode ? 0 : operatorOverview.resolvedBeforeDemo))
const currentTime = ref('')
const timeFormatter = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long', hour: '2-digit', minute: '2-digit' })
function refreshTime() { currentTime.value = timeFormatter.format(new Date()) }
refreshTime()
const timeTimer = window.setInterval(refreshTime, 30_000)

async function loadOperatorAlerts() {
  const [elderData, alertData] = await Promise.all([
    elderApi.list(),
    alertApi.list('page_size=100')
  ])
  replaceAuthoritativeOperatorSnapshot({ alerts, elders }, elderData, alertData)
  operatorDataAvailable.value = true
  operatorError.value = ''
}

const alertPolling = createPollingController({
  intervalMs: normalizePollingInterval(import.meta.env.VITE_MONITORING_POLL_INTERVAL_MS),
  task: loadOperatorAlerts,
  onError(error) {
    operatorDataAvailable.value = false
    operatorError.value = error instanceof Error ? error.message : '告警队列加载失败'
    console.warn('运营告警队列同步失败', error)
  }
})

function handleVisibilityChange() {
  if (document.hidden) alertPolling.stop()
  else void alertPolling.start()
}

onMounted(() => {
  if (!realMode) return
  document.addEventListener('visibilitychange', handleVisibilityChange)
  void alertPolling.start()
})

onBeforeUnmount(() => {
  window.clearInterval(timeTimer)
  alertPolling.stop()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

function elderByName(name) { return elders.find((elder) => elder.name === name) }
function contactFor(name) { const elder = elderByName(name); return elder ? `${elder.family} ${elder.familyPhone}` : '暂无联系人' }
function syncElderState(name) {
  return syncDemoElderState({ realMode, elders, alerts, trips, elderName: name })
}
alerts.forEach((alert) => { alert.familyContact = contactFor(alert.elderName) })
trips.forEach((trip) => { trip.contact = `家属：${contactFor(trip.elderName)}` })

const navItems = [
  { key: 'overview', icon: 'apps-o', label: '运营总览' },
  { key: 'alerts', icon: 'warning-o', label: '告警', badge: 3 },
  { key: 'elders', icon: 'friends-o', label: '老人' },
  { key: 'trips', icon: 'location-o', label: '出游' },
  { key: 'profile', icon: 'manager-o', label: '我的' },
]

function selectNav(item) {
  if (item.key === 'profile') return router.push('/operator/profile')
  activeNav.value = item.key
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handleAlert(alert) {
  if (alert.status === '处理中') {
    activeNav.value = 'alerts'
    return
  }
  operatorActionId.value = alert.id
  try {
    await runOperatorAlertAction({
      realMode,
      action: () => alertApi.accept(alert.id),
      refresh: () => alertPolling.refreshAfterCurrent(),
      applyDemo: () => {
        alert.status = '处理中'
        syncElderState(alert.elderName)
      }
    })
    showSuccessToast(`已接手 ${alert.elderName} 的告警`)
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '告警接单失败')
  } finally {
    operatorActionId.value = null
  }
}

function onAlertChanged(name) { syncElderState(name) }
function onTripEnded(name) {
  if (realMode) return
  syncElderState(name)
}
function refreshOperatorAlerts() { return alertPolling.refreshAfterCurrent() }

async function logout() {
  await logoutForMode({ realMode, logoutRemote: logoutRequest, clearLocal: userStore.logout })
  await router.replace('/login')
}
</script>

<template>
  <div class="operator-page">
    <p v-if="realMode && !operatorDataAvailable" class="operator-error">告警数据不可用：{{ operatorError || '无法获取最新状态' }}</p>
    <AlertsPanel v-if="activeNav === 'alerts'" :alerts="alerts" :real-mode="realMode" :refresh-alerts="refreshOperatorAlerts" @changed="onAlertChanged" />
    <EldersPanel v-else-if="activeNav === 'elders'" :elders="elders" :real-mode="realMode" @show-trips="activeNav = 'trips'" />
    <TripsPanel v-else-if="activeNav === 'trips' && !realMode" :trips="trips" @ended="onTripEnded" />
    <section v-else-if="activeNav === 'trips'" class="trip-source-unavailable"><h1>出游管理</h1><p>真实行程数据尚未接入</p></section>
    <template v-else>
    <header class="operator-header">
      <div class="header-row">
        <div class="brand-line"><span>银</span><strong>银发独游</strong></div>
        <div class="header-actions"><button type="button" aria-label="查看运营账号" @click="showAccount = true"><van-icon name="manager-o" /></button><button type="button" aria-label="退出账号" @click="logout"><van-icon name="sign" /></button></div>
      </div>
      <p>{{ currentTime }}</p>
      <h1>早上好，{{ userStore.userInfo.displayName || userStore.userInfo.username }}</h1>
      <div class="identity"><span></span>平台运营员 · 在线</div>
    </header>

    <main class="operator-content">
      <section class="summary-card">
        <div><small>实时守护</small><strong>{{ realMode ? '—' : activeTripCount }}</strong><span>{{ realMode ? '真实行程数据尚未接入' : '位老人正在出游' }}</span></div>
        <div class="summary-divider"></div>
        <div><small>未解决</small><strong class="warning-number">{{ unresolvedAlertCount }}</strong><span>条安全告警</span></div>
      </section>

      <section class="quick-grid" aria-label="运营数据">
        <button type="button" @click="selectNav(navItems[2])"><span class="quick-icon purple"><van-icon name="friends-o" /></span><strong>{{ elders.length }}</strong><small>服务中老人</small></button>
        <button type="button" @click="selectNav(navItems[3])"><span class="quick-icon blue"><van-icon name="guide-o" /></span><strong>{{ realMode ? '—' : activeTripCount }}</strong><small>{{ realMode ? '行程数据未接入' : '进行中出游' }}</small></button>
        <button type="button" @click="selectNav(navItems[1])"><span class="quick-icon coral"><van-icon name="warning-o" /></span><strong>{{ unresolvedAlertCount }}</strong><small>未解决告警</small></button>
        <button type="button" @click="selectNav(navItems[1])"><span class="quick-icon green"><van-icon name="passed" /></span><strong>{{ resolvedCount }}</strong><small>今日已处理</small></button>
      </section>

      <section class="section-block">
        <div class="section-title"><div><h2>实时告警</h2><p>按紧急程度排序</p></div><button type="button" @click="selectNav(navItems[1])">查看全部 <van-icon name="arrow" /></button></div>
        <div class="list-card">
          <article v-for="alert in liveAlerts.slice(0, 3)" :key="alert.id" class="alert-row">
            <span :class="['alert-icon', alert.level]"><van-icon :name="alert.level === 'urgent' ? 'bell' : 'warning-o'" /></span>
            <div class="alert-main"><div><strong>{{ alert.type }}</strong><time>{{ alert.time }}</time></div><p>{{ alert.elderName }} · {{ alert.location }}</p><button :class="{ handling: alert.status === '处理中' }" type="button" :disabled="operatorActionId === alert.id" @click="handleAlert(alert)">{{ operatorActionId === alert.id ? '提交中' : alert.status === '处理中' ? '处理中' : '立即处理' }}</button></div>
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-title"><div><h2>进行中的出游</h2><p>位置状态实时更新</p></div><button type="button" @click="selectNav(navItems[3])">管理 <van-icon name="arrow" /></button></div>
        <div class="list-card">
          <p v-if="realMode" class="trip-source-note">真实行程数据尚未接入</p>
          <article v-for="trip in realMode ? [] : trips.filter((item) => item.status === '进行中')" :key="trip.id" class="trip-row">
            <span class="avatar">{{ trip.elderName.slice(-1) }}</span>
            <div class="trip-main"><strong>{{ trip.elderName }}</strong><p><van-icon name="location-o" />{{ trip.destination }}</p><small>{{ trip.startedAt }} 出发 · {{ trip.duration }}</small></div>
            <em :class="{ attention: trip.state === '需关注' }">{{ trip.state }}</em>
          </article>
        </div>
      </section>

      <p class="demo-note">{{ realMode ? '真实模式 · 告警状态来自后端' : '演示环境 · 页面中的姓名、位置及健康相关信息均为虚构数据' }}</p>
    </main>
    </template>

    <nav class="bottom-nav" aria-label="运营端主导航">
      <button v-for="item in navItems" :key="item.key" :class="{ active: activeNav === item.key }" type="button" @click="selectNav(item)"><span><van-icon :name="item.icon" /><em v-if="item.key === 'alerts' && unresolvedAlertCount">{{ unresolvedAlertCount }}</em></span><small>{{ item.label }}</small></button>
    </nav>
    <van-popup v-model:show="showAccount" position="bottom" round :style="{ padding: '22px 18px 30px' }"><div class="account-sheet"><div class="account-title"><span>{{ (userStore.userInfo.displayName || userStore.userInfo.username || '运').slice(0, 1) }}</span><div><h2>{{ userStore.userInfo.displayName || userStore.userInfo.username }}</h2><p>平台运营员 · {{ userStore.userInfo.username }}</p></div></div><van-cell-group inset><van-cell title="账号身份" value="运营端"/><van-cell title="联系电话" :value="userStore.userInfo.phone || '未提供'"/><van-cell title="登录状态" :value="realMode ? '后端认证会话' : '演示会话有效'"/></van-cell-group><van-button block round plain type="primary" @click="logout">退出登录</van-button><p>{{ realMode ? '真实模式 · 账号信息来自后端登录响应' : '账号及电话均为虚构演示信息' }}</p></div></van-popup>
  </div>
</template>

<style scoped>
* { box-sizing: border-box; }
button { font: inherit; }
.operator-page { min-height: 100vh; padding-bottom: 72px; color: #323233; background: #f5f5f5; text-align: left; }
.operator-header { padding: 16px 18px 24px; color: white; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.header-row { display: flex; align-items: center; justify-content: space-between; }
.header-actions{display:flex;gap:7px}
.brand-line { display: flex; align-items: center; gap: 10px; }.brand-line span { width: 40px; height: 40px; display: grid; place-items: center; border: 3px solid rgba(255,255,255,.9); border-radius: 12px; background: rgba(255,255,255,.18); font-size: 15px; font-weight: 700; }.brand-line strong { font-size: 17px; letter-spacing: .2px; }
.header-row button { width: 34px; height: 34px; color: white; border: 0; border-radius: 50%; background: rgba(255,255,255,.14); cursor: pointer; }
.operator-header>p { margin: 18px 0 2px; color: rgba(255,255,255,.72); font-size: 11px; }.operator-header h1 { margin: 0 0 7px; color: white; font-size: 23px; font-weight: 700; }.identity { display: flex; align-items: center; gap: 6px; color: rgba(255,255,255,.82); font-size: 11px; }.identity span { width: 7px; height: 7px; border-radius: 50%; background: #7ee2a8; box-shadow: 0 0 0 3px rgba(126,226,168,.18); }
.operator-content { max-width: 760px; margin: 0 auto; padding: 0 14px 28px; }
.summary-card { min-height: 122px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; margin-top: 0; padding: 16px 18px; border-radius: 16px; background: white; box-shadow: 0 6px 18px rgba(40,28,65,.1); text-align: center; }.summary-card div:not(.summary-divider) { display: grid; gap: 1px; }.summary-card small { color: #969799; font-size: 11px; }.summary-card strong { color: #5e50a0; font-size: 30px; line-height: 1.2; }.summary-card span { color: #646566; font-size: 11px; }.summary-card .warning-number { color: #ee5a62; }.summary-divider { width: 1px; height: 58px; background: #ebedf0; }
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 14px 0 22px; }.quick-grid button { min-width: 0; padding: 13px 4px 12px; border: 0; border-radius: 10px; background: white; cursor: pointer; }.quick-grid strong,.quick-grid small { display: block; }.quick-grid strong { margin-top: 6px; color: #323233; font-size: 18px; }.quick-grid small { margin-top: 1px; color: #969799; font-size: 10px; white-space: nowrap; }.quick-icon { width: 32px; height: 32px; display: grid; place-items: center; margin: auto; border-radius: 10px; font-size: 17px; }.quick-icon.purple{color:#6657a5;background:#f0edfb}.quick-icon.blue{color:#3f8cc6;background:#eaf5fc}.quick-icon.coral{color:#e45d66;background:#fdecee}.quick-icon.green{color:#44a676;background:#eaf8f1}
.section-block { margin-top: 18px; }.section-title { display: flex; align-items: center; justify-content: space-between; margin: 0 2px 9px; }.section-title h2 { margin: 0; color: #323233; font-size: 16px; font-weight: 700; }.section-title p { margin-top: 2px; color: #969799; font-size: 10px; }.section-title button { color: #7a68bb; border: 0; background: transparent; font-size: 11px; cursor: pointer; }
.list-card { overflow: hidden; border-radius: 10px; background: white; }.alert-row,.trip-row { display: flex; gap: 11px; align-items: flex-start; padding: 14px; border-bottom: 1px solid #ebedf0; }.alert-row:last-child,.trip-row:last-child { border-bottom: 0; }.alert-icon { width: 36px; height: 36px; display: grid; place-items: center; flex: none; border-radius: 9px; }.alert-icon.urgent { color: #ee4f59; background: #fff0f1; }.alert-icon.warning { color: #e28b35; background: #fff6e8; }.alert-main { min-width: 0; flex: 1; }.alert-main>div { display: flex; justify-content: space-between; gap: 8px; }.alert-main strong,.trip-main strong { color: #323233; font-size: 13px; }.alert-main time { color: #969799; font-size: 10px; }.alert-main p,.trip-main p { margin: 3px 0 7px; overflow: hidden; color: #969799; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.alert-main button { padding: 5px 10px; color: white; border: 0; border-radius: 12px; background: #667eea; font-size: 10px; cursor: pointer; }.alert-main button.handling { color: #d17b2d; background: #fff2df; }
.avatar { width: 38px; height: 38px; display: grid; place-items: center; flex: none; color: #6657a5; border-radius: 50%; background: #efecfa; font-size: 13px; font-weight: 700; }.trip-main { min-width: 0; flex: 1; }.trip-main p { margin-bottom: 2px; }.trip-main small { color: #c0bac5; font-size: 10px; }.trip-row em { align-self: center; padding: 4px 7px; color: #3c9b6a; border-radius: 10px; background: #eaf8f1; font-size: 9px; font-style: normal; white-space: nowrap; }.trip-row em.attention { color: #d78234; background: #fff2e2; }
.demo-note { margin: 20px 5px 0; color: #b3adb8; text-align: center; font-size: 9px; }
.bottom-nav { position: fixed; inset: auto 0 0; z-index: 5; height: 62px; display: grid; grid-template-columns: repeat(5, 1fr); border-top: 1px solid #ebedf0; background: rgba(255,255,255,.97); }.bottom-nav button { position: relative; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 2px; color: #969799; border: 0; background: transparent; cursor: pointer; }.bottom-nav button>span { position: relative; font-size: 20px; line-height: 1; }.bottom-nav small { font-size: 10px; }.bottom-nav .active { color: #667eea; }.bottom-nav em { position: absolute; top: -7px; right: -12px; min-width: 16px; padding: 1px 4px; color: white; border-radius: 8px; background: #ee5a62; font-size: 9px; font-style: normal; }
.account-title{display:flex;align-items:center;gap:12px;margin-bottom:18px}.account-title>span{width:48px;height:48px;display:grid;place-items:center;color:#6657a5;border-radius:50%;background:#efecfa;font-size:17px;font-weight:700}.account-title h2{margin:0;color:#323233;font-size:18px}.account-title p{color:#969799;font-size:11px}.account-sheet :deep(.van-cell-group--inset){margin:0}.account-sheet>.van-button{margin-top:18px;color:#667eea;border-color:#667eea}.account-sheet>p{margin-top:12px;color:#b0aab4;text-align:center;font-size:9px}
@media (min-width: 761px) { .operator-header { padding-inline: calc((100% - 732px) / 2 + 14px); }.bottom-nav { left: 50%; width: 760px; transform: translateX(-50%); border-inline: 1px solid #ebedf0; }.operator-page { background: #eeeaf2; }.operator-content { background: #f5f5f5; } }
</style>
<style scoped>
.operator-page { width: 100%; max-width: 430px; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); } .bottom-nav { left: 50%; right: auto; width: min(100%,430px); transform: translateX(-50%); }
</style>
<style scoped>
.brand-line span{color:transparent;font-size:0;background:#fff url('/src/assets/logo.png') center/contain no-repeat}
</style>
<style scoped>
/* Keep the summary card visually attached to the header without covering text. */
.summary-card { margin-top: -4px; }
.brand-line span { width: 34px; height: 34px; border-width: 2px; border-radius: 11px; }
.brand-line strong { font-size: 16px; letter-spacing: 0; }
</style>
<style scoped>
.brand-line strong { line-height: 1; transform: translateY(3px); }
</style>
<style scoped>
.operator-error{position:sticky;top:0;z-index:8;margin:0;padding:9px 14px;color:#a33f46;background:#fff0f1;font-size:11px;text-align:center}.alert-main button:disabled{cursor:wait;opacity:.65}.trip-source-unavailable{min-height:calc(100vh - 62px);padding:48px 20px;color:#646566;background:#f5f5f5;text-align:center}.trip-source-unavailable h1{margin:0 0 10px;color:#323233;font-size:20px}.trip-source-unavailable p,.trip-source-note{color:#969799;font-size:12px;text-align:center}.trip-source-note{padding:24px 12px}
</style>
