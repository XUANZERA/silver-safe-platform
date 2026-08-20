<!-- eslint-disable unused-imports/no-unused-vars -->
<script setup>
import { Toast } from 'vant'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 表单数据
const formData = reactive({
  username: '',
  password: '',
})

// 记住我
const rememberMe = ref(false)

// 加载状态
const loading = ref(false)

// 表单引用
const formRef = ref()

// 登录提交
const onSubmit = async () => {
  loading.value = true
  
  try {
    // 模拟登录请求
    await new Promise((resolve) => setTimeout(resolve, 1500))
    
    // 保存用户信息到 store
    userStore.setUserInfo({
      username: formData.username,
      token: 'mock-token-123456'
    })
    
    Toast.success('登录成功')
    
    // 跳转到首页
    router.push('/')
  } 
  catch (error) {
    Toast.fail('登录失败，请重试')
  } 
  finally {
    loading.value = false
  }
}


// 跳转到注册页
function goToRegister() {
  // 如果有注册页面的话
  // router.push('/register')
  Toast('注册功能开发中...')
}

// 忘记密码
function goToForgotPassword() {
  Toast('忘记密码功能开发中...')
}
</script>

<template>
  <div class="login-container">
    <!-- 登录卡片 -->
    <div class="login-card">
      <!-- Logo 或标题 -->
      <div class="login-header">
        <h1 class="login-title">银发独游</h1>
      </div>

      <!-- 登录表单 -->
      <van-form @submit="onSubmit" ref="formRef">
        <!-- 用户名 -->
        <van-cell-group inset>
          <van-field
            v-model="formData.username"
            name="username"
            label="账号"
            placeholder="请输入账号"
            :rules="[{ required: true, message: '请填写账号' }]"
            left-icon="user-o"
            clearable
          />
          <!-- 密码 -->
          <van-field
            v-model="formData.password"
            type="password"
            name="password"
            label="密码"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请填写密码' }]"
            left-icon="lock"
            clearable
          />
        </van-cell-group>

        <!-- 登录按钮 -->
        <div class="mt-6 px-4">
          <van-button
            round
            block
            type="primary"
            native-type="submit"
            :loading="loading"
            loading-text="登录中..."
            size="large"
            class="login-btn"
          >
            登录
          </van-button>
        </div>

                <!-- 底部操作栏：记住我 | 注册账号 | 忘记密码 -->
        <div class="bottom-actions">
          <van-checkbox v-model="rememberMe">记住我</van-checkbox>
          <span class="register-btn" @click="goToRegister">
            注册账号
          </span>
          <span class="forgot-password-btn" @click="goToForgotPassword">
            忘记密码？
          </span>
        </div>
      </van-form>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
  margin: 0;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: white;
  border-radius: 20px;
  padding: 30px 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  margin-bottom: 30px;
}

.login-title {
  font-size: 30px;
  font-weight: 900;
  text-align: center;
  color: #000000;
  margin: 0;
}

.login-btn {
  height: 50px;
  font-size: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.login-btn:active {
  transform: scale(0.98);
}

.bottom-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 16px 0 16px;
}

.register-btn {
  color: #1989fa;
  font-size: 14px;
  cursor: pointer;
  transition: color 0.3s;
}

.register-btn:hover {
  color: #1677d6;
}

.forgot-password-btn {
  color: #1989fa;
  font-size: 14px;
  cursor: pointer;
  transition: color 0.3s;
}

.forgot-password-btn:hover {
  color: #1677d6;
}

/* 移动端优化 */
:deep(.van-field) {
  padding: 10px 0;
}

:deep(.van-field__label) {
  width: 70px;
}

/* 覆盖 Vant 默认的 checkbox 颜色，让它更协调 */
:deep(.van-checkbox__icon .van-icon) {
  border-color: #667eea;
}

:deep(.van-checkbox__icon--checked .van-icon) {
  background-color: #667eea;
  border-color: #667eea;
}
</style>
