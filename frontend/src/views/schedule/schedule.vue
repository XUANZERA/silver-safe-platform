<template>
  <div class="elderly-schedule-container">
    <header class="app-header"><div class="brand"><span>银</span><strong>银发独游</strong></div><small>安心出游，家人守护</small></header>
    <!-- 页面标题 -->
    <header class="schedule-header">
      <button class="back-button" type="button" @click="router.push(homePath)"><van-icon name="arrow-left" /></button>
      <h1 class="schedule-title">旅游行程单</h1>
    </header>

    <!-- 适老化时间轴区域 -->
    <div class="timeline-wrapper">
      <!-- 这里可以使用 v-for 循环渲染你的行程数据 -->
      <div class="timeline-item" v-for="item in itinerary" :key="item.time">
        <!-- 左侧时间轴节点 -->
        <div class="timeline-node">
          <span class="node-time">{{ item.time }}</span>
          <div class="node-line"></div>
        </div>

        <!-- 右侧行程卡片 -->
        <div class="timeline-card">
          <!-- 标题与交通方式 -->
          <div class="card-header">
            <h2 class="project-title">{{ item.title }}</h2>
            <span class="transport-tag">{{ item.transport }}</span>
          </div>

          <!-- 行程描述 -->
          <p class="project-desc">
            {{ item.description }}
          </p>

          <!-- 适老化专属提示 -->
          <div class="elderly-tips">
            <span v-for="tip in item.tips" :key="tip.text" class="tip-tag" :class="tip.type">{{ tip.text }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右下角悬浮应急按钮 -->
    <div class="emergency-fab" @click="showEmergencyInfo">
      🆘 紧急联系
    </div>
    <nav class="elder-nav" aria-label="端内导航"><button type="button" @click="router.push(homePath)"><van-icon name="home-o" /><small>首页</small></button><button class="active" type="button"><van-icon name="todo-list-o" /><small>行程</small></button><button type="button" @click="router.push(profilePath)"><van-icon name="manager-o" /><small>我的</small></button></nav>
  </div>
</template>

<script setup>
// 预留你的业务逻辑和数据绑定位置
import { showDialog } from 'vant'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
const router = useRouter()
const userStore = useUserStore()
const homePath = userStore.userInfo.role === 'family' ? '/child' : '/elder'
const profilePath = userStore.userInfo.role === 'family' ? '/child/profile' : '/elder/profile'

const itinerary = [
  { time: '08:30', title: '集合出发', transport: '🚗 专车直达（约30分钟）', description: '服务人员到家接送，确认随身物品后前往天坛公园。', tips: [{ text: '🛋️ 专人陪同', type: 'safe' }, { text: '📞 家人可查看位置', type: 'safe' }] },
  { time: '09:00', title: '天坛公园慢游', transport: '🚶 平缓步道', description: '沿平整步道游览祈年殿，园区路况平缓，空气极佳。', tips: [{ text: '🛋️ 沿途有休息区', type: 'safe' }, { text: '🚶‍♂️ 全程平缓步道', type: 'safe' }, { text: '⚠️ 每小时休息15分钟', type: 'warning' }] },
  { time: '15:30', title: '返程回家', transport: '🚗 专车送回', description: '结束游览后由原车送回家，抵达后通知家人。', tips: [{ text: '✅ 已安排返程', type: 'safe' }, { text: '📞 抵达自动提醒', type: 'safe' }] }
]

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
.elderly-schedule-container{padding-top:0}.schedule-header{margin-bottom:20px}
</style>
<style scoped>
.app-header .brand span{color:transparent;background:#fff url('/src/assets/logo.png') center/contain no-repeat}
</style>
<style scoped>
.elderly-schedule-container { width: 100%; max-width: 430px; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); } .elder-nav { left: 50%; right: auto; width: min(100%,430px); transform: translateX(-50%); }
</style>
