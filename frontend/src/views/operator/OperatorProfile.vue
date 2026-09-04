<template>
  <main class="operator-page">
    <header class="app-header">
      <div>
        <div class="brand">银发独游</div>
        <div class="subtitle">运营工作台 · 个人账号</div>
      </div>
      <span class="role-badge">运营端</span>
    </header>

    <section class="profile-hero">
      <div class="avatar">{{ user.name.slice(0, 1) }}</div>
      <div>
        <h1>{{ user.name }}</h1>
        <p>{{ user.role }} · {{ user.organization }}</p>
      </div>
    </section>

    <section class="card info-card">
      <h2>账号信息</h2>
      <van-cell-group inset>
        <van-field v-model="user.name" label="姓名" :readonly="realMode || !editing" />
        <van-field v-model="user.phone" label="联系电话" :readonly="realMode || !editing" />
        <van-field v-model="user.organization" label="所属机构" :readonly="realMode || !editing" />
        <van-cell title="账号角色" :value="user.role" />
        <van-cell title="账号状态"><template #value><span class="ok">{{ realMode ? '后端认证会话' : '演示会话' }}</span></template></van-cell>
      </van-cell-group>
    </section>

    <section class="card actions-card">
      <van-button v-if="!realMode" block round type="primary" @click="toggleEdit">{{ editing ? '保存演示资料' : '编辑演示资料' }}</van-button>
      <button class="logout-button" type="button" @click="logout"><van-icon name="revoke" /> 退出登录</button>
      <small>{{ realMode ? '真实模式下资料编辑尚未接入。' : '本页为虚构演示资料。' }}</small>
    </section>

    <nav class="bottom-nav" aria-label="运营导航">
      <button type="button" @click="goModule('overview')"><span><van-icon name="apps-o" /></span><small>总览</small></button>
      <button type="button" @click="goModule('alerts')"><span><van-icon name="warning-o" /></span><small>告警</small></button>
      <button type="button" @click="goModule('elders')"><span><van-icon name="friends-o" /></span><small>老人</small></button>
      <button type="button" @click="goModule('trips')"><span><van-icon name="location-o" /></span><small>出游</small></button>
      <button class="active" type="button"><span><van-icon name="manager-o" /></span><small>我的</small></button>
    </nav>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import { useUserStore } from '../../stores/user'
import { isApiConfigured, logoutRequest } from '../../services/api'

const router = useRouter()
const editing = ref(false)
const userStore = useUserStore()
const realMode = isApiConfigured()
const user = reactive(realMode
  ? { name: userStore.userInfo.displayName || userStore.userInfo.username || '运营用户', phone: userStore.userInfo.phone || '未提供', organization: '当前接口未提供', role: '平台运营员' }
  : { name: '林晓岚', phone: '188****2608', organization: '夕阳红文旅服务处', role: '平台运营员' })

function toggleEdit() {
  if (editing.value) showSuccessToast('演示资料已保存')
  editing.value = !editing.value
}
function goModule(view) { router.push({ path: '/operator', query: { view } }) }
async function logout() { if (isApiConfigured()) await logoutRequest().catch(() => null); userStore.logout(); router.replace('/login') }
</script>

<style scoped>
.operator-page { min-height: 100vh; box-sizing: border-box; padding-bottom: 84px; background: #f7f5fc; color: #2b2442; }
.app-header { display: flex; align-items: center; gap: 12px; padding: 18px 18px 22px; color: #fff; background: linear-gradient(135deg, #6f4bd8, #8d6be7); }
.back-button { border: 0; background: transparent; color: #fff; font-size: 34px; line-height: 1; padding: 0 4px; cursor: pointer; }
.brand { font-size: 20px; font-weight: 800; letter-spacing: 1px; }
.subtitle { margin-top: 4px; font-size: 12px; opacity: .82; }
.role-badge { margin-left: auto; padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,.2); font-size: 12px; }
.profile-hero { display: flex; align-items: center; gap: 14px; margin: -1px 14px 14px; padding: 20px 18px; border-radius: 0 0 18px 18px; background: #fff; box-shadow: 0 5px 18px rgba(82, 58, 140, .08); }
.avatar { display: grid; place-items: center; width: 58px; height: 58px; border-radius: 50%; color: #fff; font-size: 25px; font-weight: 800; background: linear-gradient(145deg, #8a68e5, #6241c4); }
h1 { margin: 0; font-size: 21px; } .profile-hero p { margin: 7px 0 0; color: #81798f; font-size: 13px; }
.card { margin: 14px; padding: 16px 0; border-radius: 16px; background: #fff; box-shadow: 0 5px 18px rgba(82, 58, 140, .07); }
h2 { margin: 0 18px 12px; font-size: 17px; }
.info-card :deep(.van-cell-group--inset) { margin: 0; } .info-card :deep(.van-cell) { padding: 13px 18px; } .info-card :deep(.van-field__label), .info-card :deep(.van-cell__title) { color: #81798f; } .info-card :deep(.van-field__control), .info-card :deep(.van-cell__value) { color: #2b2442; }
.ok { color: #2ca66f; font-weight: 700; }
.actions-card { display: grid; gap: 12px; padding: 16px; }
.actions-card small{color:#969799;font-size:10px;text-align:center}
.logout-button{width:100%;padding:12px;color:#e25e66;border:1px solid #f3c7ca;border-radius:22px;background:#fff;font-size:13px}
.bottom-nav { position: fixed; z-index: 5; right: 0; bottom: 0; left: 0; height:62px;display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid #ebedf0;background:rgba(255,255,255,.97); }
.bottom-nav button { display:flex;align-items:center;justify-content:center;flex-direction:column;gap:2px;border:0;background:transparent;color:#969799;cursor:pointer}.bottom-nav span{font-size:20px;line-height:1}.bottom-nav small{font-size:10px}.bottom-nav .active{color:#667eea}
</style>
<style scoped>
.operator-page { width: 100%; max-width: 430px; margin: 0 auto; box-shadow: 0 0 28px rgba(38,26,72,.14); } .bottom-nav { left: 50%; right: auto; width: min(100%,430px); transform: translateX(-50%); }
</style>
