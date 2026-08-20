<template>
  <div class="operator-profile-container">
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

      <div class="info-row">
        <span class="label">所属机构：</span>
        <span class="value name-value">{{ userInfo.organization }}</span>
      </div>
      
      <div class="info-row">
        <span class="label">运营角色：</span>
        <span class="value">
          <span class="status-tag status-active">{{ userInfo.role }}</span>
        </span>
      </div>

      <div class="info-row">
        <span class="label">账号状态：</span>
        <span class="value text-success">正常</span>
      </div>
    </div>

    <!-- 操作按钮区域（上下排列） -->
    <div class="action-area">
      <button class="btn-primary" @click="handleViewRecords">查看服务记录</button>
      <button class="btn-secondary" @click="handleEditProfile">修改基础信息</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

// 模拟从后端接口获取的运营端用户数据
const userInfo = reactive({
  account: 'op_wang_admin',
  password: 'Op@Secure2024',
  phoneNumber: '138****5678', 
  organization: '夕阳红文旅服务处',
  role: '高级运营专员'
});

// 密码显隐状态
const showPassword = ref(false);

// 修改密码
const handleEditPassword = () => {
  alert('即将跳转到修改密码页面...');
};

// 查看服务记录
const handleViewRecords = () => {
  alert('即将跳转到服务记录管理列表...');
};

// 修改基础信息
const handleEditProfile = () => {
  alert('即将跳转到修改信息页面...');
};
</script>

<style scoped>
/* 根节点全屏白底，保持全局统一 */
.operator-profile-container {
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
  width: 140px;
  color: #666;
  font-weight: 500;
}

.value {
  color: #1a1a1a;
  font-weight: bold;
}

/* 机构名称使用醒目的深色 */
.name-value {
  font-size: 24px;
  color: #1a1a1a; 
}

.btn-toggle {
    margin-left: 10px;
    padding: 4px 8px;
    font-size: 16px;
    border: 1px solid #ccc;
    background-color: #fffefe;
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

/* 账号正常绿色提示 */
.text-success {
  color: #67c23a;
}

/* 状态标签 */
.status-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 18px;
  font-weight: bold;
}
.status-active {
  background-color: #d9ecff;
  color: #409eff;
  border: 1px solid #409eff;
}

/* 底部按钮区域*/
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

.btn-secondary {
  background-color: #f0f0f0;
  color: #666;
}

.btn-primary:hover, .btn-secondary:hover {
  opacity: 0.85;
}

/* 移动端响应式适配 */
@media (max-width: 600px) {
  .operator-profile-container {
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
}
</style>