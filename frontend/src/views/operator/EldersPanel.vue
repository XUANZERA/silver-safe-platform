<script setup>
import { computed, ref } from 'vue'
import { showDialog } from 'vant'
const props = defineProps({ elders: { type: Array, required: true } })
const emit = defineEmits(['show-trips'])
const query = ref('')
const selected = ref(null)
const visibleElders = computed(() => props.elders.filter((elder) => [elder.name, elder.phone, elder.family].some((value) => value.includes(query.value.trim()))))

function contactFamily(elder) {
  showDialog({ title: '联系家属', message: `${elder.family} · ${elder.familyPhone}\n演示环境不会发起真实电话。`, confirmButtonText: '知道了' })
}

function showTrips() {
  selected.value = null
  emit('show-trips')
}
</script>

<template>
  <section class="module-page">
    <header class="module-header"><div><h1>老人档案</h1><p>共 {{ elders.length }} 位演示老人</p></div></header>
    <div class="search-wrap"><van-search v-model="query" shape="round" placeholder="搜索姓名、电话或家属" /></div>
    <div class="elder-list">
      <button v-for="elder in visibleElders" :key="elder.id" class="elder-card" type="button" @click="selected = elder"><span class="avatar">{{ elder.name.slice(-1) }}</span><div><strong>{{ elder.name }} <small>{{ elder.gender }} · {{ elder.age }} 岁</small></strong><p><van-icon name="location-o" />{{ elder.lastLocation }}</p><small>{{ elder.updatedAt }} · 家属 {{ elder.family }}</small></div><em :class="{ danger: elder.status === '告警中', attention: elder.status === '需关注' }">{{ elder.status }}</em><van-icon name="arrow" /></button>
      <van-empty v-if="visibleElders.length === 0" description="没有匹配的老人档案" />
    </div>
    <van-popup v-model:show="selected" position="bottom" round :style="{ padding: '22px 18px 30px' }">
      <div v-if="selected" class="detail-sheet"><div class="detail-title"><span>{{ selected.name.slice(-1) }}</span><div><h2>{{ selected.name }}</h2><p>{{ selected.gender }} · {{ selected.age }} 岁 · {{ selected.risk }}</p></div></div><van-cell-group inset><van-cell title="联系电话" :value="selected.phone"/><van-cell title="关联家属" :value="selected.family"/><van-cell title="当前状态" :value="selected.status"/><van-cell title="最近位置" :label="selected.lastLocation" :value="selected.updatedAt"/></van-cell-group><div class="detail-actions"><van-button block round plain type="primary" @click="contactFamily(selected)">联系家属</van-button><van-button block round type="primary" @click="showTrips">查看出游</van-button></div><p class="privacy-note">演示档案已对电话等敏感信息进行脱敏</p></div>
    </van-popup>
  </section>
</template>

<style scoped>
.module-page{min-height:calc(100vh - 62px);background:#f5f5f5}.module-header{display:flex;align-items:center;gap:12px;padding:20px 16px 18px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.module-header button{width:34px;height:34px;color:white;border:0;border-radius:50%;background:rgba(255,255,255,.15)}.module-header h1{margin:0;color:white;font-size:20px;font-weight:700}.module-header p{color:rgba(255,255,255,.75);font-size:11px}.search-wrap{background:white}.elder-list{display:grid;gap:9px;max-width:760px;margin:auto;padding:12px 14px}.elder-card{width:100%;display:flex;align-items:center;gap:10px;padding:13px;color:#323233;border:0;border-radius:10px;background:white;text-align:left}.avatar{width:40px;height:40px;display:grid;place-items:center;flex:none;color:#6657a5;border-radius:50%;background:#efecfa;font-size:14px;font-weight:700}.elder-card>div{min-width:0;flex:1}.elder-card strong{display:block;font-size:13px}.elder-card strong small{color:#969799;font-size:10px;font-weight:400}.elder-card p{margin:3px 0;overflow:hidden;color:#646566;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.elder-card div>small{color:#b0aab4;font-size:9px}.elder-card em{padding:4px 7px;color:#3d9a6b;border-radius:9px;background:#eaf8f1;font-size:9px;font-style:normal;white-space:nowrap}.elder-card em.attention{color:#d78335;background:#fff3e2}.elder-card em.danger{color:#e25e66;background:#fff0f1}.elder-card>.van-icon{color:#c8c9cc}.detail-title{display:flex;align-items:center;gap:12px;margin-bottom:18px}.detail-title>span{width:48px;height:48px;display:grid;place-items:center;color:#6657a5;border-radius:50%;background:#efecfa;font-size:17px;font-weight:700}.detail-title h2{margin:0;color:#323233;font-size:18px}.detail-title p{color:#969799;font-size:11px}.detail-sheet :deep(.van-cell-group--inset){margin:0}.privacy-note{margin-top:14px;color:#b0aab4;text-align:center;font-size:10px}
.detail-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:18px}.detail-actions :deep(.van-button--primary){background:#667eea;border-color:#667eea}.detail-actions :deep(.van-button--plain){color:#667eea;background:white}
</style>
