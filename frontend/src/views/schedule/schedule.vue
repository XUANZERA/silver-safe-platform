<template>
  <div class="elderly-schedule-container">
    <header class="app-header"><div class="brand"><img class="brand-logo" :src="logo" alt="星斗守眼安游"/><strong>银发独游</strong></div><small>安心出游，家人守护</small></header>
    <!-- 页面标题 -->
    <header class="schedule-header">
      <button class="back-button" type="button" @click="router.push(homePath)"><van-icon name="arrow-left" /></button>
      <h1 class="schedule-title">旅游行程单</h1>
      <button class="edit-button" type="button" @click="editing ? cancelEdit() : startEdit()">{{ editing ? '取消' : '编辑' }}</button>
    </header>

    <!-- 适老化时间轴区域 -->
    <div class="timeline-wrapper">
      <!-- 这里可以使用 v-for 循环渲染你的行程数据 -->
      <div class="timeline-item" v-for="(item, index) in itinerary" :key="`${item.time}-${index}`">
        <!-- 左侧时间轴节点 -->
        <div class="timeline-node">
          <span v-if="!editing" class="node-time">{{ item.time }}</span>
          <input v-else v-model="item.time" class="time-input" aria-label="行程时间" />
          <div class="node-line"></div>
        </div>

        <!-- 右侧行程卡片 -->
        <div class="timeline-card">
          <!-- 标题与交通方式 -->
          <div v-if="!editing" class="card-header">
            <h2 class="project-title">{{ item.title }}</h2>
            <span class="transport-tag">{{ item.transport }}</span>
          </div>
          <div v-else class="edit-fields"><input v-model="item.title" placeholder="行程名称"/><input v-model="item.transport" placeholder="交通方式"/><textarea v-model="item.description" rows="3" placeholder="行程说明"></textarea><button type="button" @click="removeItem(index)"><van-icon name="delete-o" /> 删除此项</button></div>

          <!-- 行程描述 -->
          <p v-if="!editing" class="project-desc">
            {{ item.description }}
          </p>

          <!-- 适老化专属提示 -->
          <div v-if="!editing" class="elderly-tips">
            <span v-for="tip in item.tips" :key="tip.text" class="tip-tag" :class="tip.type">{{ tip.text }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-if="editing" class="edit-actions"><button type="button" @click="addItem"><van-icon name="plus" /> 新增行程</button><button class="save" type="button" @click="saveEdit">保存行程</button></div>

    <!-- 右下角悬浮应急按钮 -->
    <button class="emergency-fab" type="button" @click="showEmergencyInfo">
      <van-icon name="phone-o" /> 紧急联系家人
    </button>
    <nav class="elder-nav" aria-label="端内导航"><button type="button" @click="router.push(homePath)"><van-icon name="home-o" /><small>首页</small></button><button class="active" type="button"><van-icon name="todo-list-o" /><small>行程</small></button><button type="button" @click="router.push(profilePath)"><van-icon name="manager-o" /><small>我的</small></button></nav>
  </div>
</template>

<script setup>
// 预留你的业务逻辑和数据绑定位置
import { onMounted, reactive, ref } from 'vue'
import { showDialog, showSuccessToast } from 'vant'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import logo from '../../assets/logo.png'
import { elderApi, isApiConfigured } from '../../services/api'
const router = useRouter()
const userStore = useUserStore()
const homePath = userStore.userInfo.role === 'family' ? '/child' : '/elder'
const profilePath = userStore.userInfo.role === 'family' ? '/child/profile' : '/elder/profile'
const destination = ref('天坛公园慢游')
const editing = ref(false)
let editSnapshot = ''
let hasSavedItinerary = false

const itinerary = reactive([
  { time: '08:30', title: '集合出发', transport: '🚗 专车直达（约30分钟）', description: '服务人员到家接送，确认随身物品后前往天坛公园。', tips: [{ text: '🛋️ 专人陪同', type: 'safe' }, { text: '📞 家人可查看位置', type: 'safe' }] },
  { time: '09:00', title: '天坛公园慢游', transport: '🚶 平缓步道', description: '沿平整步道游览祈年殿，园区路况平缓，空气极佳。', tips: [{ text: '🛋️ 沿途有休息区', type: 'safe' }, { text: '🚶‍♂️ 全程平缓步道', type: 'safe' }, { text: '⚠️ 每小时休息15分钟', type: 'warning' }] },
  { time: '15:30', title: '返程回家', transport: '🚗 专车送回', description: '结束游览后由原车送回家，抵达后通知家人。', tips: [{ text: '✅ 已安排返程', type: 'safe' }, { text: '📞 抵达自动提醒', type: 'safe' }] }
])

function startEdit() {
  editSnapshot = JSON.stringify(itinerary)
  editing.value = true
}

function cancelEdit() {
  itinerary.splice(0, itinerary.length, ...JSON.parse(editSnapshot || '[]'))
  editing.value = false
}

function addItem() {
  itinerary.push({ time: '10:00', title: '新的安排', transport: '步行', description: '请填写行程说明。', tips: [{ text: '家人可查看', type: 'safe' }] })
}

function removeItem(index) {
  if (itinerary.length === 1) return showDialog({ title: '至少保留一项', message: '行程单中需要保留至少一个安排。' })
  itinerary.splice(index, 1)
}

function saveEdit() {
  const invalid = itinerary.some((item) => !item.time.trim() || !item.title.trim())
  if (invalid) return showDialog({ title: '请补充信息', message: '每项行程都需要填写时间和名称。' })
  sessionStorage.setItem('helpingold-itinerary', JSON.stringify(itinerary))
  editing.value = false
  showSuccessToast('行程已保存并同步展示')
}

onMounted(async () => {
  const saved = sessionStorage.getItem('helpingold-itinerary')
  if (saved) {
    try { itinerary.splice(0, itinerary.length, ...JSON.parse(saved)); hasSavedItinerary = true } catch { sessionStorage.removeItem('helpingold-itinerary') }
  }
  if (!isApiConfigured()) return
  try {
    const elders = await elderApi.list()
    const elder = elders?.items?.[0]
    if (!elder) return
    const trip = await elderApi.currentTrip(elder.id)
    if (trip?.destination && !hasSavedItinerary) {
      destination.value = trip.destination
      const destinationItem = itinerary[1] || itinerary[0]
      destinationItem.title = trip.destination
      destinationItem.description = `沿平整步道游览${trip.destination}，园区路况平缓，途中可随时休息。`
    }
  } catch (error) {
    console.warn('行程单同步失败，使用演示安排', error)
  }
})

const showEmergencyInfo = () => {
  // 这里可以触发弹窗、抽屉或跳转，展示紧急联系人、随身药品、附近医院等信息
  showDialog({ title: '紧急联系', message: '联系人：张小明（138****2256）\n附近医院：北京同仁医院' });
};
</script>

<style scoped>
/* 全局容器：设定适老化的大字号和柔和背景 */
.elderly-schedule-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background-color: #f9f9f9;
  min-height: 100vh;
  padding-bottom: 100px;
  box-sizing: border-box;
}
.app-header{display:flex;align-items:center;justify-content:space-between;margin:-20px -20px 22px;padding:16px 18px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.brand{display:flex;align-items:center;gap:8px}.brand span{width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:rgba(255,255,255,.18);font-weight:700}.brand strong{font-size:16px}.app-header small{color:rgba(255,255,255,.78);font-size:10px}

/* 头部样式 */
.schedule-header {
  position: relative;
  text-align: center;
  margin-bottom: 30px;
}
.back-button{position:absolute;left:0;top:0;width:34px;height:34px;color:#667eea;border:0;border-radius:50%;background:#efecfa;font-size:16px}
.schedule-title {
  font-size: 28px;
  color: #2c3e50;
  margin: 0;
  font-weight: bold;
}
.schedule-subtitle {
  font-size: 16px;
  color: #7f8c8d;
  margin-top: 8px;
}

/* 时间轴整体布局 */
.timeline-wrapper {
  padding-left: 10px;
}
.timeline-item {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

/* 左侧时间轴节点 */
.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 80px;
  flex-shrink: 0;
}
.node-time {
  font-size: 18px;
  font-weight: bold;
  color: #3498db;
}
.node-line {
  width: 3px;
  flex-grow: 1;
  background-color: #dce4ec;
  margin-top: 8px;
  min-height: 60px;
}

/* 右侧卡片样式 */
.timeline-card {
  flex-grow: 1;
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #3498db;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 8px;
}
.project-title {
  font-size: 22px;
  color: #333;
  margin: 0;
}
.transport-tag {
  font-size: 14px;
  background-color: #e8f4fc;
  color: #2980b9;
  padding: 4px 10px;
  border-radius: 20px;
  white-space: nowrap;
}
.project-desc {
  font-size: 17px;
  color: #555;
  line-height: 1.6;
  margin-bottom: 12px;
}

/* 适老标签样式 */
.elderly-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tip-tag {
  font-size: 14px;
  padding: 4px 10px;
  border-radius: 4px;
}
.tip-tag.safe {
  background-color: #e8f8f5;
  color: #1abc9c;
}
.tip-tag.warning {
  background-color: #fef9e7;
  color: #f39c12;
}

/* 悬浮应急按钮 */
.emergency-fab {
  position: fixed;
  bottom: 82px;
  right: 30px;
  background-color: #e74c3c;
  color: white;
  padding: 15px 20px;
  border-radius: 30px;
  font-size: 18px;
  font-weight: bold;
  box-shadow: 0 4px 12px rgba(231, 76, 60, 0.4);
  cursor: pointer;
  transition: transform 0.2s;
  z-index: 1000;
}
.elder-nav{position:fixed;inset:auto 0 0;z-index:1001;height:62px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97)}.elder-nav button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;color:#969799;border:0;background:transparent}.elder-nav button.active{color:#667eea}.elder-nav .van-icon{font-size:20px}.elder-nav small{font-size:10px}
.emergency-fab:hover {
  transform: scale(1.05);
}
</style>
<style scoped>
.elderly-schedule-container{width:100%;max-width:430px;min-height:100vh;margin:0 auto;padding:0 14px 90px;overflow:hidden;color:#323233;background:#f5f5f5;box-shadow:0 0 28px rgba(38,26,72,.14)}
.app-header{height:68px;margin:0 -14px 18px;padding:14px 18px;background:linear-gradient(135deg,#667eea,#764ba2)}.app-header .brand span{width:34px;height:34px;border-radius:11px}.app-header .brand strong{font-size:16px}.app-header>small{font-size:10px}
.schedule-header{display:flex;align-items:center;justify-content:center;height:42px;margin:0 0 14px}.back-button{left:0;top:4px;width:34px;height:34px;color:#6657a5;background:#efecfa}.schedule-title{color:#403675;font-size:20px}
.timeline-wrapper{padding:0}.timeline-item{align-items:stretch;margin-bottom:12px}.timeline-node{width:56px;align-items:flex-start;padding-top:14px}.node-time{color:#6657a5;font-size:14px}.node-line{width:2px;min-height:70px;margin:8px 0 0 21px;background:#dcd8ed}.timeline-card{min-width:0;padding:15px;border:0;border-radius:12px;border-left:3px solid #7668b5;box-shadow:0 3px 12px rgba(45,33,82,.07)}.card-header{display:block;margin-bottom:8px}.project-title{color:#323233;font-size:16px}.transport-tag{display:inline-block;margin-top:7px;padding:4px 8px;color:#6657a5;border-radius:12px;background:#efecfa;font-size:10px}.project-desc{margin:0 0 10px;color:#646566;font-size:12px;line-height:1.6}.elderly-tips{gap:6px}.tip-tag{padding:4px 7px;border-radius:8px;font-size:9px}.tip-tag.safe{color:#3d9a6a;background:#eaf8f1}.tip-tag.warning{color:#c47c2b;background:#fff5e7}
.emergency-fab{position:static;width:100%;display:flex;align-items:center;justify-content:center;gap:7px;margin:4px 0 16px;padding:12px;color:#e25e66;border:1px solid #f3c7ca;border-radius:22px;background:#fff;font-size:13px;font-weight:600;box-shadow:none}.emergency-fab:hover{transform:none}.elder-nav{left:50%;right:auto;width:min(100%,430px);height:62px;transform:translateX(-50%)}
</style>
<style scoped>
.app-header .brand-logo{width:34px;height:34px;object-fit:contain;border-radius:11px;background:#fff}
.app-header .brand strong{line-height:1;transform:translateY(3px)}
</style>
<style scoped>
.edit-button{position:absolute;right:0;top:5px;padding:7px 10px;color:#6657a5;border:0;border-radius:16px;background:#efecfa;font-size:12px}.time-input{width:50px;padding:6px 4px;color:#6657a5;border:1px solid #d8d1ef;border-radius:8px;background:#fff;font-size:12px;text-align:center;outline:none}.edit-fields{display:grid;gap:8px}.edit-fields input,.edit-fields textarea{width:100%;padding:10px;color:#323233;border:1px solid #e3e0e8;border-radius:9px;background:#fafafa;font:inherit;font-size:12px;outline:none;resize:none}.edit-fields input:focus,.edit-fields textarea:focus,.time-input:focus{border-color:#7b6bb5;background:#fff}.edit-fields button{justify-self:end;padding:5px 0;color:#dc666d;border:0;background:transparent;font-size:10px}.edit-actions{display:grid;grid-template-columns:1fr 1.4fr;gap:10px;margin:4px 0 14px}.edit-actions button{padding:12px;color:#6657a5;border:1px solid #d8d1ef;border-radius:22px;background:#fff;font-size:12px}.edit-actions .save{color:#fff;border-color:#667eea;background:linear-gradient(135deg,#667eea,#764ba2);font-weight:600}
</style>
