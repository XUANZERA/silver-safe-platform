<template>
  <div class="elderly-schedule-container">
    <!-- 页面标题 -->
    <header class="schedule-header">
      <h1 class="schedule-title">旅游行程单</h1>
    </header>

    <!-- 适老化时间轴区域 -->
    <div class="timeline-wrapper">
      <!-- 这里可以使用 v-for 循环渲染你的行程数据 -->
      <div class="timeline-item" v-for="n in 3" :key="n">
        <!-- 左侧时间轴节点 -->
        <div class="timeline-node">
          <span class="node-time">08:30</span>
          <div class="node-line"></div>
        </div>

        <!-- 右侧行程卡片 -->
        <div class="timeline-card">
          <!-- 标题与交通方式 -->
          <div class="card-header">
            <h2 class="project-title">天坛公园慢游</h2>
            <span class="transport-tag">🚗 专车直达 (约30分钟)</span>
          </div>

          <!-- 行程描述 -->
          <p class="project-desc">
            沿平整步道游览祈年殿，园区路况平缓，空气极佳。
          </p>

          <!-- 适老化专属提示 -->
          <div class="elderly-tips">
            <span class="tip-tag safe">🛋️ 沿途有休息区</span>
            <span class="tip-tag safe">🚶‍♂️ 全程平缓步道</span>
            <span class="tip-tag warning">⚠️ 建议每1小时休息15分钟</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右下角悬浮应急按钮 -->
    <div class="emergency-fab" @click="showEmergencyInfo">
      🆘 紧急联系
    </div>
  </div>
</template>

<script setup>
// 预留你的业务逻辑和数据绑定位置
import { ref } from 'vue';

const showEmergencyInfo = () => {
  // 这里可以触发弹窗、抽屉或跳转，展示紧急联系人、随身药品、附近医院等信息
  alert('📞 紧急联系人：张三 (138xxxxxxx)\n🏥 附近三甲医院：北京同仁医院');
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
  box-sizing: border-box;
}

/* 头部样式 */
.schedule-header {
  text-align: center;
  margin-bottom: 30px;
}
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
  bottom: 30px;
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
.emergency-fab:hover {
  transform: scale(1.05);
}
</style>