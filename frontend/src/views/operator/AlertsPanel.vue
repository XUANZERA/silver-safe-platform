<script setup>
import { computed, ref } from 'vue'
import { showDialog, showSuccessToast } from 'vant'

const props = defineProps({ alerts: { type: Array, required: true } })
const emit = defineEmits(['back', 'changed'])
const filter = ref('全部')
const selected = ref(null)
const resolution = ref('已联系家属并持续关注')
const filters = ['全部', '待处理', '处理中', '已解决']
const visibleAlerts = computed(() => filter.value === '全部' ? props.alerts : props.alerts.filter((item) => item.status === filter.value))

function accept(alert) {
  alert.status = '处理中'
  emit('changed', alert.elderName)
  selected.value = alert
  showSuccessToast('已接手该告警')
}

function contactFamily(alert) {
  showDialog({ title: '联系家属', message: `${alert.familyContact}\n演示环境不会发起真实电话。`, confirmButtonText: '知道了' })
}

function resolveAlert() {
  if (!selected.value) return
  selected.value.status = '已解决'
  selected.value.resolution = resolution.value
  emit('changed', selected.value.elderName)
  selected.value = null
  showSuccessToast('告警已解决并记录')
}
</script>

<template>
  <section class="module-page">
    <header class="module-header"><button type="button" @click="emit('back')"><van-icon name="arrow-left" /></button><div><h1>告警中心</h1><p>及时响应安全风险</p></div></header>
    <div class="filter-tabs"><button v-for="item in filters" :key="item" :class="{ active: filter === item }" type="button" @click="filter = item">{{ item }}</button></div>
    <div class="module-list">
      <article v-for="alert in visibleAlerts" :key="alert.id" class="module-card alert-card">
        <div class="card-top"><span :class="['level-icon', alert.level]"><van-icon :name="alert.level === 'urgent' ? 'bell' : 'warning-o'" /></span><div><strong>{{ alert.type }}</strong><p>{{ alert.elderName }} · {{ alert.time }}</p></div><em :class="`status-${alert.status}`">{{ alert.status }}</em></div>
        <p class="location"><van-icon name="location-o" />{{ alert.location }}</p>
        <p v-if="alert.resolution" class="resolution">处置记录：{{ alert.resolution }}</p>
        <div v-if="alert.status !== '已解决'" class="card-actions"><button type="button" @click="contactFamily(alert)"><van-icon name="phone-o" />联系家属</button><button class="primary" type="button" @click="accept(alert)">{{ alert.status === '处理中' ? '继续处置' : '立即处理' }}</button></div>
      </article>
      <van-empty v-if="visibleAlerts.length === 0" description="当前没有相关告警" />
    </div>
    <van-popup v-model:show="selected" position="bottom" round :style="{ padding: '22px 18px 30px' }">
      <div v-if="selected" class="resolve-sheet"><h2>处置告警</h2><p>{{ selected.elderName }} · {{ selected.type }}</p><van-field v-model="resolution" rows="3" autosize type="textarea" maxlength="100" show-word-limit label="处置记录" placeholder="请输入处理结果"/><van-button block round type="primary" @click="resolveAlert">标记为已解决</van-button></div>
    </van-popup>
  </section>
</template>

<style scoped>
.module-page{min-height:calc(100vh - 62px);background:#f5f5f5}.module-header{display:flex;align-items:center;gap:12px;padding:20px 16px 18px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.module-header button{width:34px;height:34px;color:white;border:0;border-radius:50%;background:rgba(255,255,255,.15)}.module-header h1{margin:0;color:white;font-size:20px;font-weight:700}.module-header p{color:rgba(255,255,255,.75);font-size:11px}.filter-tabs{display:flex;gap:8px;padding:12px 14px;overflow:auto;background:white}.filter-tabs button{flex:none;padding:6px 13px;color:#646566;border:0;border-radius:16px;background:#f2f3f5;font-size:11px}.filter-tabs button.active{color:white;background:#667eea}.module-list{display:grid;gap:10px;max-width:760px;margin:auto;padding:12px 14px}.module-card{padding:14px;border-radius:10px;background:white}.card-top{display:flex;align-items:center;gap:10px}.card-top>div{min-width:0;flex:1}.card-top strong{font-size:13px}.card-top p{margin-top:2px;color:#969799;font-size:10px}.card-top em{padding:4px 7px;border-radius:10px;font-size:9px;font-style:normal}.level-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:9px}.level-icon.urgent{color:#ee4f59;background:#fff0f1}.level-icon.warning{color:#e28b35;background:#fff6e8}.status-待处理{color:#e25e66;background:#fff0f1}.status-处理中{color:#d78335;background:#fff3e2}.status-已解决{color:#3c9b6a;background:#eaf8f1}.location{margin:12px 0;color:#646566;font-size:11px}.resolution{padding:9px;color:#5a916f;border-radius:7px;background:#eff9f3;font-size:10px}.card-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.card-actions button{height:32px;color:#667eea;border:1px solid #c9d0f8;border-radius:16px;background:white;font-size:11px}.card-actions .primary{color:white;border-color:#667eea;background:#667eea}.resolve-sheet h2{margin:0;color:#323233;font-size:18px}.resolve-sheet>p{margin:4px 0 16px;color:#969799;font-size:11px}.resolve-sheet .van-button{margin-top:18px}.resolve-sheet :deep(.van-button--primary){background:#667eea;border-color:#667eea}
</style>
