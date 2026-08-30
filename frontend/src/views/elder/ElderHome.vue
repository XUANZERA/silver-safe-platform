<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
// FIX START: API 失败时向用户展示后端返回的真实错误。
import { showConfirmDialog, showDialog, showFailToast, showSuccessToast } from 'vant'
// FIX END: API 失败时向用户展示后端返回的真实错误。
import { elderApi, isApiConfigured, tripApi } from '../../services/api'
import logo from '../../assets/logo.png'

const router = useRouter()
const tripStatus = ref('出游中')
const locationStatus = ref('定位正常')
const showMore = ref(false)
const showAiPlan = ref(false)
// FIX START: 单独保存行程 ID，不能把老人 ID 当成行程 ID。
const currentTripId = ref(null)
// FIX END: 单独保存行程 ID。
const elder = reactive({ id: 1001, name: '张建国', age: 72, family: '张小明', familyPhone: '138****2256', destination: '天坛公园慢游', lastUpdate: '刚刚' })
const isTripActive = computed(() => tripStatus.value === '出游中')

function applySavedItinerary() {
  try {
    const items = JSON.parse(sessionStorage.getItem('helpingold-itinerary') || '[]')
    const destinationItem = items[1] || items[0]
    if (destinationItem?.title) elder.destination = destinationItem.title
  } catch { sessionStorage.removeItem('helpingold-itinerary') }
}

onMounted(async () => {
  applySavedItinerary()
  if (!isApiConfigured()) return
  try {
    const list = await elderApi.list()
    const current = list?.items?.[0]
    if (current) Object.assign(elder, { id: current.id, name: current.name, age: current.age ?? elder.age })
    if (elder.id) {
      const trip = await elderApi.currentTrip(elder.id)
      // FIX START: 用后端返回的行程 ID 和状态初始化页面。
      if (trip) {
        currentTripId.value = trip.id
        Object.assign(elder, { destination: trip.destination })
        tripStatus.value = trip.status === 'active' ? '出游中' : '待出发'
        locationStatus.value = trip.status === 'active' ? '定位正常' : '定位已暂停'
      } else {
        currentTripId.value = null
        tripStatus.value = '已返程'
        locationStatus.value = '已停止定位'
      }
      // FIX END: 用后端返回的行程 ID 和状态初始化页面。
    }
  } catch (error) { console.warn('老人端数据加载失败，使用演示数据', error) }
  applySavedItinerary()
})

// FIX START: 开始/结束行程时调用真实 API，并始终传递 trip.id。
async function toggleTrip() {
  if (isTripActive.value) {
    try {
      await showConfirmDialog({ title: '结束本次出游？', message: '确认已经安全回到家了吗？' })
    } catch {
      return
    }

    try {
      if (isApiConfigured()) {
        if (!currentTripId.value) throw new Error('没有可结束的行程')
        await tripApi.end(currentTripId.value)
        currentTripId.value = null
      }
      tripStatus.value = '已返程'
      locationStatus.value = '已停止定位'
      showSuccessToast('出游已结束，辛苦了')
    } catch (error) {
      showFailToast(error instanceof Error ? error.message : '结束行程失败')
    }
    return
  }

  try {
    if (isApiConfigured()) {
      let tripId = currentTripId.value
      if (!tripId) {
        const createdTrip = await tripApi.create(elder.destination)
        tripId = createdTrip.id
      }
      const startedTrip = await tripApi.start(tripId)
      currentTripId.value = startedTrip.id
    }
    tripStatus.value = '出游中'
    locationStatus.value = '定位正常'
    showSuccessToast('已开始出游，家人可以看到您的位置')
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '开始行程失败')
  }
}
// FIX END: 开始/结束行程时调用真实 API，并始终传递 trip.id。

function emergency() {
  showDialog({ title: '紧急联系', message: `将联系您的家人：${elder.family}\n电话：${elder.familyPhone}\n\n这是演示操作，不会拨打真实电话。`, confirmButtonText: '知道了' })
}

function confirmAiPlan() {
  showAiPlan.value = false
  showSuccessToast('AI 已记住今天的安排')
}

function go(path) { router.push(path) }
</script>

<template>
  <div class="elder-page">
    <header class="elder-header"><div class="brand"><img class="brand-logo" :src="logo" alt="星斗守眼安游"/><strong>银发独游</strong></div><button type="button" aria-label="个人信息" @click="go('/elder/profile')"><van-icon name="manager-o" /></button><p>您好，{{ elder.name }}</p><small>{{ elder.age }} 岁 · 家人守护中</small></header>
    <main class="elder-content">
      <section class="status-card"><div class="status-icon"><van-icon :name="isTripActive ? 'location-o' : 'home-o'" /></div><div><small>当前状态</small><strong>{{ tripStatus }}</strong><p v-if="isTripActive">正在前往：{{ elder.destination }}</p><p v-else>欢迎回家，今天辛苦了</p></div><span :class="['status-dot', { off: !isTripActive }]" /></section>
      <!-- FIX START: 显示脚本中随 API 行程状态更新的 locationStatus。 -->
      <section class="location-card"><div><small>我的位置</small><strong>{{ locationStatus }}</strong><p>{{ isTripActive ? '家人可以看到您的最新位置' : '开始出游后将自动开启定位' }}</p></div><van-icon :class="{ paused: !isTripActive }" name="aim" /></section>
      <!-- FIX END: 显示真实的 locationStatus。 -->
      <button class="plan-card" type="button" @click="go('/schedule')"><div class="plan-title"><div><small>今日出游计划</small><strong>天坛公园慢游</strong></div><van-icon name="arrow" /></div><div class="plan-row"><span><b>08:30</b><small>专车到家</small></span><i></i><span><b>09:00</b><small>到达公园</small></span><i></i><span><b>15:30</b><small>专车回家</small></span></div><p><van-icon name="info-o" /> 沿平整步道游览，途中有休息区</p></button>
      <button class="main-action" type="button" @click="toggleTrip"><van-icon :name="isTripActive ? 'stop-circle-o' : 'play-circle-o'" /><span>{{ isTripActive ? '结束本次出游' : '开始出游' }}</span><small>{{ isTripActive ? '确认安全到家后点击' : '点击后家人可以看到您的位置' }}</small></button>
      <!-- FIX START: 给已经实现但没有入口的仿真组件增加可见入口。 -->
      <section class="quick-actions"><button type="button" @click="go('/schedule')"><span class="purple"><van-icon name="todo-list-o" /></span><strong>我的行程</strong><small>查看今天安排</small></button><button type="button" @click="go('/simulation')"><span class="purple"><van-icon name="aim" /></span><strong>定位仿真</strong><small>测试轨迹与围栏告警</small></button><button type="button" @click="emergency"><span class="red"><van-icon name="phone-o" /></span><strong>紧急联系</strong><small>联系家人</small></button></section>
      <!-- FIX END: 给仿真组件增加可见入口。 -->
      <button class="ai-plan-card" type="button" @click="showAiPlan = true"><span class="ai-badge"><van-icon name="service-o" /></span><div><small>AI 行程管家</small><strong>已经为您安排好今天的行程</strong><p>出发前会提醒您，家人也能同步看到</p></div><van-icon name="arrow" /></button>
      <button class="more-button" type="button" @click="showMore = !showMore">{{ showMore ? '收起更多' : '更多信息' }} <van-icon :name="showMore ? 'arrow-up' : 'arrow-down'" /></button>
      <div v-if="showMore" class="more-card"><van-cell title="目的地" :value="elder.destination"/><van-cell title="最后更新" :value="elder.lastUpdate"/><van-cell title="紧急联系人" :value="elder.family"/><van-cell title="联系电话" :value="elder.familyPhone"/></div>
      <p class="privacy-note">演示页面 · 姓名、位置和联系电话均为虚构数据</p>
    </main>
    <van-popup v-model:show="showAiPlan" round position="bottom" :style="{ padding: '20px 16px 24px' }"><div class="ai-plan-popup"><div class="ai-popup-title"><span class="ai-badge"><van-icon name="service-o" /></span><div><strong>AI 已为您安排</strong><small>不用操作，我会按时提醒您</small></div></div><div class="ai-timeline"><p><b>08:30</b><span>专车到家</span></p><p><b>09:00</b><span>到达天坛公园，慢慢游览</span></p><p><b>15:30</b><span>专车接您回家</span></p></div><van-button block round type="primary" color="#667eea" @click="confirmAiPlan">好的，我知道了</van-button></div></van-popup>
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
