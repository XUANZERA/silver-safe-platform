<template>
  <div class="child-profile-container">
    <!-- 页面标题 -->
    <h2 class="page-title">我的个人信息</h2>

    <!-- 基础账号信息 -->
    <div class="info-section">
      <div class="info-row">
        <span class="label">登录账号：</span>
        <span class="value">{{ userInfo.account }}</span>
      </div>
      
      <div class="info-row">
        <span class="label">登录密码：</span>
        <span class="value">{{ showPassword ? userInfo.password : '********' }}
            <button class="btn-toggle" @click="showPassword = !showPassword">
              {{ showPassword ? '隐藏' : '查看' }}
            </button>
        </span>
        <span class="link-btn" @click="handleEditPassword">修改密码</span>
      </div>

      <div class="info-row">
        <span class="label">绑定手机：</span>
        <span class="value" :class="{ 'text-danger': !userInfo.phoneNumber }">
          {{ userInfo.phoneNumber || '待绑定' }}
        </span>
      </div>

    <!-- 已绑定老人信息展示 -->
      <div class="info-row">
        <span class="label">绑定老人：</span>
        <span class="value name-value">{{ userInfo.boundElder.elderName }}</span>
      </div>
      
      <div class="info-row">
        <span class="label">当前出游状态：</span>
        <span class="value">
          <span 
            class="status-tag" 
            :class="userInfo.boundElder.travelStatus === '出游中' ? 'status-active' : 'status-inactive'"
          >
            {{ userInfo.boundElder.travelStatus }}
          </span>
        </span>
      </div>

      <div class="info-row">
        <span class="label">最新定位时间：</span>
        <span class="value time-value">{{ userInfo.boundElder.lastLocationTime }}</span>
      </div>
    </div>

    <!-- 操作按钮区域 -->
    <div class="action-area">
      <button class="btn-primary" @click="handleViewLocation">查看实时位置</button>
      <button class="btn-secondary" @click="handleEditProfile">修改基础信息</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

// 模拟从后端接口获取的子女端用户数据
const userInfo = reactive({
  account: 'child_zhang_xm',
  password: 'Child@Secure2024',
  phoneNumber: '', // 假设子女已绑定手机号
  boundElder: {
    elderName: '张建国',
    travelStatus: '出游中', // 可选值：'出游中', '已返程', '休息中'
    lastLocationTime: '2024-05-20 14:30:25'
  }
});

// 密码显隐状态
const showPassword = ref(false);

// 修改密码
const handleEditPassword = () => {
  alert('即将跳转到修改密码页面...');
};

// 查看实时位置
const handleViewLocation = () => {
  alert('即将打开地图，查看老人当前位置...');
};

// 修改基础信息
const handleEditProfile = () => {
  alert('即将跳转到修改信息页面...');
};
</script>

<style scoped>
/* 根节点全屏白底 */
.child-profile-container {
  box-sizing: border-box;
  min-height: 100vh;
  width: 100%;
  padding: 30px;
  background-color: #ffffff;
  font-family: 'Microsoft YaHei', sans-serif;
  color: #333;
}

.page-title {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 30px;
  color: #1a1a1a;
  text-align: center;
}

/* 信息区块 */
.info-section {
  margin-bottom: 20px;
}

/* 纯左对齐排版 */
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
  font-size: 20px;
  color: #000000; 
}

.btn-toggle {
    margin-left: 10px;
    padding: 4px 8px;
    font-size: 16px;
    border: 1px solid #ccc;
    background-color: #fff;
    border-radius: 4px;
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

.btn-primary, .btn-secondary {
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

/* 次级按钮样式，区分主次操作 */
.btn-secondary {
  background-color: #f0f0f0;
  color: #666;
}

.btn-primary:hover, .btn-secondary:hover {
  opacity: 0.85;
}

/* 移动端响应式适配 */
@media (max-width: 600px) {
  .child-profile-container {
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
