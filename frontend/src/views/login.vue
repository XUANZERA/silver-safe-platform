<!-- eslint-disable unused-imports/no-unused-vars -->
<script setup lang="ts">
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
  showToast('注册功能开发中...')
}
</script>

<template>
  <div class="login-container">
    <!-- 登录卡片 -->
    <div class="login-card">
      <!-- Logo 或标题 -->
      <div class="login-header">
        <h1 class="text-3xl font-bold text-center text-blue-600">银发独游</h1>
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
            left-icon="lock-o"
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

        <!-- 额外操作 -->
        <div class="flex justify-between px-4 mt-4 text-sm">
          <van-checkbox v-model="rememberMe">记住我</van-checkbox>
          <span class="text-blue-500 cursor-pointer" @click="goToRegister">
            注册账号
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

.login-btn {
  height: 50px;
  font-size: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.login-btn:active {
  transform: scale(0.98);
}

/* 移动端优化 */
:deep(.van-field) {
  padding: 10px 0;
}

:deep(.van-field__label) {
  width: 70px;
}
</style>
