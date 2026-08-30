<script setup>
import { showFailToast, showSuccessToast, showToast } from 'vant'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { isApiConfigured, loginRequest } from '../services/api'
import logo from '../assets/logo.png'

const router = useRouter()
const userStore = useUserStore()

// 表单数据
const formData = reactive({
  username: '',
  password: '',
})

const loading = ref(false)
const formRef = ref()
const rememberMe = ref(false)

const onSubmit = async () => {
  loading.value = true
  try {
    if (isApiConfigured()) {
      const user = await loginRequest(formData.username, formData.password)
      userStore.setUserInfo({ ...user, path: user.role === 'operator' ? '/operator' : user.role === 'family' ? '/child' : '/elder' })
      showSuccessToast('登录成功')
      await router.push(userStore.userInfo.path)
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 650))
    const accounts = {
      operator01: { id: 9001, username: 'operator01', displayName: '林晓岚', role: 'operator', phone: '188****2608', path: '/operator' },
      elder01: { id: 1001, username: 'elder01', displayName: '张建国', role: 'elder', phone: '138****4031', path: '/elder' },
      child01: { id: 2001, username: 'child01', displayName: '张小明', role: 'family', phone: '138****2256', path: '/child' },
      family01: { id: 2001, username: 'family01', displayName: '张小明', role: 'family', phone: '138****2256', path: '/child' },
    }
    const account = accounts[formData.username]
    if (!account || formData.password !== 'demo123') {
      throw new Error('invalid demo account')
    }
    userStore.setUserInfo(account)
    showSuccessToast('登录成功')
    await router.push(account.path)
  } catch {
    showFailToast('演示账号或密码不正确')
  } finally {
    loading.value = false
  }
}

// 跳转到注册页
function goToRegister() {
  showToast('注册功能开发中...')
}

// 忘记密码
function goToForgotPassword() {
  showToast('忘记密码功能开发中...')
}

const demoAccounts = [
  { username: 'elder01', role: '老人端', displayName: '张建国' },
  { username: 'child01', role: '子女端', displayName: '张小明' },
  { username: 'operator01', role: '运营端', displayName: '林晓岚' },
]

function fillDemoAccount(username) {
  formData.username = username
  formData.password = 'demo123'
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <img class="login-logo" :src="logo" alt="星斗守眼安游" />
      </div>

      <van-form @submit="onSubmit" ref="formRef">
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

        <div class="form-actions">
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

      <div class="demo-title"><span class="demo-dot"></span>选择演示身份</div>
      <div class="demo-accounts">
        <button v-for="account in demoAccounts" :key="account.username" class="demo-account" type="button" @click="fillDemoAccount(account.username)">
          <span class="demo-role">{{ account.role }}</span>
          <strong>{{ account.username }}</strong>
          <small>{{ account.displayName }} · 点击填入</small>
        </button>
      </div>
      <p class="role-note">登录后将根据账号身份自动进入对应页面</p>
      <p class="demo-note">本页面仅使用虚构数据进行产品演示</p>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 18% 18%, rgba(255,255,255,.16), transparent 28%),
    radial-gradient(circle at 88% 78%, rgba(255,255,255,.1), transparent 24%),
    linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
  margin: 0;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  box-sizing: border-box;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: white;
  border-radius: 20px;
  padding: 36px 24px 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  margin-bottom: 28px;
  text-align: center;
}

.brand-mark {
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  color: white;
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  box-shadow: 0 10px 24px rgba(102, 126, 234, .28);
}

.eyebrow {
  color: #8b7ba3;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.4px;
}

.login-header h1 {
  margin: 3px 0 4px;
  color: #292235;
  font-size: 28px;
  font-weight: 700;
}

.subtitle {
  color: #9890a4;
  font-size: 14px;
}

.form-actions {
  margin: 22px 16px 0;
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

.login-logo { display: block; width: 190px; height: 112px; margin: 0 auto 8px; object-fit: contain; }

.demo-title { margin: 18px 16px 8px; color: #6e5a91; font-size: 12px; font-weight: 700; }
.demo-accounts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 0 16px; }
.demo-account {
  min-width: 0;
  padding: 11px 8px;
  border: 1px dashed #c9bfe0;
  border-radius: 12px;
  color: #6e5a91;
  background: #faf8ff;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.demo-account strong {
  display: block;
  margin-top: 5px;
  color: #4f3d70;
  font-size: 12px;
}

.demo-role { display: block; color: #7a68bb; font-size: 11px; font-weight: 700; }
.demo-account small { display: block; margin-top: 4px; color: #a69bb8; font-size: 10px; }

.demo-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 5px;
  border-radius: 50%;
  background: #54b787;
}

.demo-note {
  margin-top: 5px;
  color: #b0a9b9;
  text-align: center;
  font-size: 11px;
}

.role-note {
  margin-top: 13px;
  color: #847a91;
  text-align: center;
  font-size: 11px;
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
