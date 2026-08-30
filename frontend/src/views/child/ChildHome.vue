<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showSuccessToast } from 'vant'
import { elderApi, isApiConfigured, locationApi } from '../../services/api'
const router = useRouter()
const activeAlert = ref(false)
const elder = reactive({ id: 1001, tripId: null, name: '张建国', status: '出游中', location: '天坛公园东门附近', update: '刚刚', family: '张小明', phone: '138****2256', destination: '天坛公园慢游' })
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
    if (current) Object.assign(elder, { id: current.id, name: current.name })
    const trip = await elderApi.currentTrip(elder.id)
    if (trip) {
      Object.assign(elder, { tripId: trip.id, destination: trip.destination, status: trip.status === 'active' ? '出游中' : '暂无出游' })
      const latest = await locationApi.latest(trip.id)
      if (latest?.location) Object.assign(elder, { location: `${latest.location.latitude.toFixed(5)}, ${latest.location.longitude.toFixed(5)}`, update: new Date(latest.location.recorded_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    }
  } catch (error) { console.warn('子女端数据加载失败，使用演示数据', error) }
  applySavedItinerary()
})
// FIX START: 家属端只能读取老人后端定位，不能用家属设备定位覆盖老人位置。
async function refresh() {
  if (!isApiConfigured()) {
    elder.update = '刚刚（演示数据）'
    showSuccessToast('演示位置已刷新')
    return
  }

  if (!elder.tripId) {
    showDialog({ title: '暂无进行中的行程', message: '老人开始出游后，这里会显示后端上传的最新位置。' })
    return
  }

  try {
    const latest = await locationApi.latest(elder.tripId)
    if (!latest?.location) {
      showDialog({ title: '暂无定位数据', message: '行程已建立，但后端还没有收到老人定位。' })
      return
    }
    Object.assign(elder, { location: `${latest.location.latitude.toFixed(5)}, ${latest.location.longitude.toFixed(5)}`, update: new Date(latest.location.recorded_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
    showSuccessToast('老人位置已刷新')
  } catch (error) {
    showDialog({ title: '位置更新失败', message: error instanceof Error ? error.message : '无法读取老人最新位置' })
  }
}
// FIX END: 家属端只读取老人后端定位。
function call() { showDialog({ title: '联系老人', message: '演示环境不会拨打真实电话。', confirmButtonText: '知道了' }) }
</script>
<template>
  <div class="child-page"><header class="child-header"><div class="brand"><span>银</span><strong>银发独游</strong></div><button type="button" @click="router.push('/child/profile')"><van-icon name="manager-o" /></button><p>家人守护中心</p><h1>{{ elder.name }}现在安全吗？</h1><small>位置与出游状态实时同步</small></header><main><section class="elder-card"><div class="elder-avatar">张</div><div class="elder-title"><strong>{{ elder.name }}</strong><small>我的家人 · {{ elder.destination }}</small></div><span class="online"><i></i>在线</span></section><section class="location-card"><div class="map-placeholder"><span class="fence"></span><span class="pin"><van-icon name="location" /></span><em>{{ elder.location }}</em></div><div class="location-info"><strong>{{ elder.status }}</strong><p>最后更新：{{ elder.update }}</p><button type="button" @click="refresh"><van-icon name="replay" />刷新位置</button></div></section><section class="notice-card"><van-icon name="shield-o"/><div><strong>安全区域正常</strong><p>老人当前在安全范围内，暂时没有需要处理的提醒。</p></div></section><section class="child-actions"><button type="button" @click="router.push('/schedule')"><span class="purple"><van-icon name="todo-list-o"/></span><strong>查看出游计划</strong><small>了解今天的安排</small></button><button type="button" @click="call"><span class="red"><van-icon name="phone-o"/></span><strong>联系老人</strong><small>电话为脱敏演示号码</small></button></section><button class="alert-button" type="button" @click="activeAlert = !activeAlert"><van-icon name="warning-o"/> {{ activeAlert ? '已开启重点关注' : '开启重点关注' }}</button><p class="note">演示页面 · 姓名、位置和电话均为虚构数据</p></main><nav class="child-nav"><button class="active"><van-icon name="home-o"/><small>首页</small></button><button @click="router.push('/schedule')"><van-icon name="todo-list-o"/><small>行程</small></button><button @click="router.push('/child/profile')"><van-icon name="manager-o"/><small>我的</small></button></nav></div>
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
</style>
