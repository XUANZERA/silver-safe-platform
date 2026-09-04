<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import { useUserStore } from '../../stores/user'
import { elderApi, isApiConfigured, logoutRequest } from '../../services/api'
const router = useRouter(); const editing=ref(false)
const userStore = useUserStore()
const realMode = isApiConfigured()
const user=ref(realMode
  ? { name:userStore.userInfo.displayName || userStore.userInfo.username || '家属用户', phone:userStore.userInfo.phone || '未提供', relation:'授权关系待同步', notify:'当前接口未返回提醒设置' }
  : { name:'张小明', phone:'138****2256', relation:'张建国的子女', notify:'已开启演示安全提醒' })
onMounted(async () => {
  if (!realMode) return
  try {
    const data = await elderApi.list()
    const names = (data?.items || []).map((elder) => elder.name)
    user.value.relation = names.length ? `已授权查看：${names.join('、')}` : '暂无已授权老人'
  } catch {
    user.value.relation = '授权关系数据不可用'
  }
})
function save(){editing.value=false;showSuccessToast('演示资料已保存')}
async function logout(){if(isApiConfigured()) await logoutRequest().catch(()=>null);userStore.logout();router.replace('/login')}
</script>
<template><div class="profile-page"><header><button @click="router.push('/child')"><van-icon name="arrow-left"/></button><h1>我的信息</h1><button v-if="!realMode" @click="editing=!editing">{{editing?'取消':'编辑演示资料'}}</button><span v-else></span></header><main><section class="profile-card"><span>{{ user.name.slice(0, 1) }}</span><h2>{{user.name}}</h2><p>{{user.relation}}</p></section><section class="info-card"><van-field v-model="user.name" label="姓名" :readonly="realMode || !editing"/><van-field v-model="user.phone" label="联系电话" :readonly="realMode || !editing"/><van-field v-model="user.relation" label="关系" readonly/><van-cell title="安全提醒" :value="user.notify"/></section><van-button v-if="!realMode && editing" block round type="primary" @click="save">保存演示修改</van-button><button class="logout-button" type="button" @click="logout"><van-icon name="revoke"/> 退出登录</button><p class="note">{{ realMode ? '真实模式 · 资料编辑与提醒设置尚未接入' : '演示信息已脱敏' }}</p></main><nav class="child-nav"><button type="button" @click="router.push('/child')"><van-icon name="home-o"/><small>首页</small></button><button type="button" @click="router.push('/schedule')"><van-icon name="todo-list-o"/><small>行程</small></button><button class="active" type="button"><van-icon name="manager-o"/><small>我的</small></button></nav></div></template>
<style scoped>
*{box-sizing:border-box}.profile-page{min-height:100vh;background:#f5f5f5;color:#323233}.profile-page header{display:flex;align-items:center;justify-content:space-between;padding:16px;color:#fff;background:linear-gradient(135deg,#667eea,#764ba2)}header button{min-width:42px;padding:6px;color:#fff;border:0;background:transparent}h1{margin:0;color:#fff;font-size:19px}.profile-page main{max-width:600px;margin:auto;padding:15px}.profile-card{padding:22px;text-align:center;border-radius:12px;background:#fff}.profile-card>span{width:58px;height:58px;display:grid;place-items:center;margin:auto;color:#6657a5;border-radius:50%;background:#efecfa;font-size:22px;font-weight:700}.profile-card h2{margin:10px 0 2px;font-size:20px}.profile-card p,.note{color:#969799;font-size:11px}.info-card{overflow:hidden;margin:12px 0;border-radius:12px;background:#fff}.info-card :deep(.van-cell){padding:14px}.info-card :deep(.van-field__label){width:76px;color:#646566}.profile-page :deep(.van-button--primary){background:#667eea;border-color:#667eea}.note{margin-top:18px;text-align:center;font-size:10px}
</style>
<style scoped>
.profile-page main{padding:18px 15px}.profile-card{padding:28px 22px;border-radius:14px}.profile-card h2{margin:14px 0 4px;font-size:21px}.info-card{margin:18px 0;border-radius:14px}.info-card :deep(.van-cell){min-height:58px;padding:17px 20px;border-bottom:1px solid #f1f2f3}.info-card :deep(.van-cell:last-child){border-bottom:0}.info-card :deep(.van-field__label){width:86px}.info-card :deep(.van-field__control),.info-card :deep(.van-cell__value){font-size:15px}.note{margin-top:22px}
</style>
<style scoped>
.profile-page { width: 100%; max-width: 430px; min-height: 100vh; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); }
</style>
<style scoped>
.profile-page{padding-bottom:76px}.child-nav{position:fixed;left:50%;right:auto;bottom:0;z-index:5;width:min(100%,430px);height:62px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97);transform:translateX(-50%)}.child-nav button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;color:#969799;border:0;background:transparent}.child-nav button.active{color:#667eea}.child-nav .van-icon{font-size:20px}.child-nav small{font-size:10px}
.logout-button{width:100%;margin-top:12px;padding:13px;color:#e25e66;border:1px solid #f3c7ca;border-radius:22px;background:#fff;font-size:13px}
</style>
