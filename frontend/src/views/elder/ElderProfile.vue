<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showSuccessToast } from 'vant'
import { useUserStore } from '../../stores/user'
import { elderApi, isApiConfigured, logoutRequest } from '../../services/api'
import { emergencyContactPresentation } from '../../services/modeBoundary'
const router = useRouter(); const editing = ref(false)
const userStore = useUserStore()
const realMode = isApiConfigured()
const contactPresentation = emergencyContactPresentation(realMode)
const elder = ref(realMode
  ? { name: userStore.userInfo.username || '老人', age: '后端数据待同步', phone: userStore.userInfo.phone || '未提供', family: '当前接口未提供', familyPhone: '当前接口未提供', address: '当前接口未提供' }
  : { name: '张建国', age: '72 岁', phone: '138****4031', family: '张小明', familyPhone: '138****2256', address: '北京市东城区（演示地址）' })
onMounted(async () => {
  if (!realMode) return
  try {
    const data = await elderApi.list()
    const current = data?.items?.[0]
    if (current) Object.assign(elder.value, { name: current.name, age: current.age === null ? '未提供' : `${current.age} 岁` })
  } catch {
    elder.value.age = '数据不可用'
  }
})
function save() { editing.value = false; showSuccessToast('演示资料已保存') }
function emergency() { showDialog({ title: contactPresentation.title, message: contactPresentation.message, confirmButtonText: '知道了' }) }
async function logout() { if (isApiConfigured()) await logoutRequest().catch(() => null); userStore.logout(); router.replace('/login') }
</script>
<template>
  <div class="profile-page"><header><button type="button" @click="router.push('/elder')"><van-icon name="arrow-left" /></button><h1>我的信息</h1><button v-if="!realMode" type="button" @click="editing = !editing">{{ editing ? '取消' : '编辑演示资料' }}</button><span v-else></span></header><main><section class="profile-card"><span class="avatar">{{ elder.name.slice(0, 1) }}</span><h2>{{ elder.name }}</h2><p>银发独游用户 · {{ elder.age }}</p></section><section class="info-card"><van-field v-model="elder.name" label="姓名" :readonly="realMode || !editing"/><van-field v-model="elder.age" label="年龄" :readonly="realMode || !editing"/><van-field v-model="elder.phone" label="我的电话" :readonly="realMode || !editing"/><van-field v-model="elder.family" label="家属姓名" :readonly="realMode || !editing"/><van-field v-model="elder.familyPhone" label="家属电话" :readonly="realMode || !editing"/><van-field v-model="elder.address" label="常住地址" :readonly="realMode || !editing"/></section><van-button v-if="!realMode && editing" block round type="primary" @click="save">保存演示修改</van-button><button class="family-button" type="button" @click="emergency"><van-icon name="records-o" /> {{ contactPresentation.label }}</button><button class="logout-button" type="button" @click="logout"><van-icon name="revoke"/> 退出登录</button><p class="note">{{ realMode ? '真实模式 · 仅显示当前授权接口返回的信息，资料编辑尚未接入' : '演示信息已脱敏，不会发起真实拨号' }}</p></main><nav class="elder-nav"><button type="button" @click="router.push('/elder')"><van-icon name="home-o"/><small>首页</small></button><button type="button" @click="router.push('/schedule')"><van-icon name="todo-list-o"/><small>行程</small></button><button class="active" type="button"><van-icon name="manager-o"/><small>我的</small></button></nav></div>
</template>
<style scoped>
*{box-sizing:border-box}.profile-page{min-height:100vh;padding-bottom:86px;background:#f5f5f5;color:#323233}.profile-page header{display:flex;align-items:center;justify-content:space-between;padding:16px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.profile-page header button{min-width:42px;padding:6px;color:white;border:0;background:transparent;font-size:13px}.profile-page h1{margin:0;color:white;font-size:19px}.profile-page main{max-width:600px;margin:auto;padding:15px}.profile-card{padding:22px;text-align:center;border-radius:12px;background:white}.avatar{width:58px;height:58px;display:grid;place-items:center;margin:auto;color:#6657a5;border-radius:50%;background:#efecfa;font-size:22px;font-weight:700}.profile-card h2{margin:10px 0 2px;font-size:20px}.profile-card p{color:#969799;font-size:11px}.info-card{overflow:hidden;margin:12px 0;border-radius:12px;background:white}.info-card :deep(.van-cell){padding:14px}.info-card :deep(.van-field__label){width:76px;color:#646566}.profile-page :deep(.van-button--primary){background:#667eea;border-color:#667eea}.family-button{width:100%;margin-top:12px;padding:13px;color:#e25e66;border:1px solid #f3c7ca;border-radius:22px;background:white;font-size:14px}.note{margin-top:18px;color:#b0aab4;text-align:center;font-size:10px}.elder-nav{position:fixed;inset:auto 0 0;z-index:5;height:62px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97)}.elder-nav button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;color:#969799;border:0;background:transparent}.elder-nav button.active{color:#667eea}.elder-nav .van-icon{font-size:20px}.elder-nav small{font-size:10px}
</style>
<style scoped>
.profile-page { width: 100%; max-width: 430px; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); } .elder-nav { left: 50%; right: auto; width: min(100%,430px); transform: translateX(-50%); }
.logout-button{width:100%;margin-top:10px;padding:13px;color:#e25e66;border:1px solid #f3c7ca;border-radius:22px;background:#fff;font-size:13px}
.profile-page header > button:first-child { display: none; }
</style>
