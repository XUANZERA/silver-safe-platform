<template>
  <div class="elder-profile-container">
    <!-- 页面标题 -->
    <h2 class="page-title">我的个人信息</h2>
    <!-- 基础账号信息卡片 -->
    <div class="info-section">
      <div class="info-row">
        <span class="label">登录账号：</span>
        <span class="value">{{ userInfo.account }}</span>
      </div>
      <div class="info-row">
        <span class="label">登录密码：</span>
        <span class="value">
          {{ showPassword ? userInfo.password : '********' }}
          <button class="btn-toggle" @click="showPassword = !showPassword">
            {{ showPassword ? '隐藏' : '查看' }}
          </button>
        </span>
        <span class="link-btn" @click="handleEditProfile">修改密码</span>
      </div>
    
      <!-- 绑定手机信息 -->
      <div class="info-row">
        <span class="label">绑定手机：</span>
        <span class="value" :class="{ 'text-danger': !userInfo.phoneNumber }">
          {{ userInfo.phoneNumber || '待绑定' }}
        </span>
      </div>

      <div class="info-row">
        <span class="label">老人姓名：</span>
        <span class="value name-value">{{ userInfo.elderName }}</span>
      </div>
      
      <div class="info-row">
        <span class="label">当前出游状态：</span>
        <span class="value">
          <span 
            class="status-tag" 
            :class="userInfo.travelStatus === '出游中' ? 'status-active' : 'status-inactive'"
          >
            {{ userInfo.travelStatus }}
          </span>
        </span>
      </div>

      <div class="info-row">
        <span class="label">最新定位时间：</span>
        <span class="value time-value">{{ userInfo.lastLocationTime }}</span>
      </div>
    </div>

    <!-- 模拟操作按钮 -->
    <div class="action-area">
      <button class="btn-danger" @click="handleEmergencyContact">紧急联系子女</button>
      <button class="btn-primary" @click="handleEditProfile">修改基础信息</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

// 模拟从后端接口获取的用户数据
const userInfo = reactive({
  account: 'elder_zhang_2024',
  password: 'Zhang@123456',
  phoneNumber: '',
  elderName: '张建国',
  travelStatus: '出游中', // 可选值：'出游中', '已返程', '休息中'
  lastLocationTime: '2024-05-20 14:30:25'
});

// 密码显隐状态
const showPassword = ref(false);

//修改密码
const handleEditPassword = () => {
  alert('即将跳转到修改密码页面...');
  // TODO: 路由跳转或打开弹窗
};

// 模拟修改信息事件
const handleEditProfile = () => {
  alert('即将跳转到修改信息页面...');
  // TODO: 路由跳转或打开弹窗
};

// 模拟紧急联系事件
const handleEmergencyContact = () => {
  alert('正在呼叫紧急联系人：张小明 (子女)');
  // TODO: 调用拨打系统电话或发送短信的接口
};
</script>

<style scoped>
/* 适老化基础样式：大字号、高对比度 */
.elder-profile-container {
  box-sizing: border-box;
  width: 100%;
  margin: 0 auto;
  padding: 30px;
  font-family: 'Microsoft YaHei', sans-serif;
  color:#000000;
  min-height: 100vh;
  background-color: #ffffff;
}

.page-title {
  font-size: 30px;
  font-weight: bold;
  margin-bottom: 24px;
  color: #000000;
  text-align: center;
}

.info-section {
  margin-bottom: 20px;
}

.info-row {
  display: flex;
  align-items: center;
  font-size: 20px;
  line-height: 1.6;
  margin-bottom: 16px;
}

.label {
  flex-shrink: 0;
  width: 160px;
  color: #666;
  font-weight: 500;
}

.value {
  color: #1a1a1a;
  font-weight: bold;
}

.name-value {
  font-size: 24px;
  color: #080808;
}

.btn-toggle{
  margin-left: 15px;
  padding: 4px 12px;
  font-size: 20px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #fff;
  cursor: pointer;
}

/* 标准蓝无框文字按钮 */
.link-btn {
  margin-left: 15px;
  color: #0400ff;
  font-size: 18px;
  font-weight: normal;
  cursor: pointer;
  transition: opacity 0.2s;
}

.link-btn:hover {
  opacity: 0.7;
}

/* 待绑定红色提示 */
.text-danger {
  color: #ff1414;
}

/* 出游状态标签 */
.status-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 18px;
  font-weight: bold;
}
.status-active {
  background-color: #e1f3d8;
  color: #67c23a;
  border: 1px solid #67c23a;
}
.status-inactive {
  background-color: #f4f4f5;
  color: #909399;
  border: 1px solid #dcdfe6;
}

/* 时间等宽字体 */
.time-value {
  font-family: 'Courier New', monospace;
  color: #409eff;
}

/* 底部按钮区域 */
.action-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 40px;
}

.btn-primary, .btn-danger {
  width: 100%;
  padding: 16px 0;
  font-size: 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: bold;
  transition: opacity 0.2s;
}

.btn-primary {
  background-color: #409eff;
  color: #fff;
}

.btn-danger {
  background-color: #f56c6c;
  color: #fff;
}

.btn-primary:hover, .btn-danger:hover {
  opacity: 0.85;
}

/* 移动端响应式适配 */
@media (max-width: 600px) {
  .elder-profile-container {
    padding: 15px;
  }
  .info-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .label {
    width: auto;
    margin-bottom: 4px;
  }
  .link-btn {
    margin-left: 0;
    margin-top: 4px;
  }
  .action-area {
    flex-direction: column;
  }
}
</style>
