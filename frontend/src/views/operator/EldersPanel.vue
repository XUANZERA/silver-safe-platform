<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { showDialog } from 'vant'
import MapCanvas from '../../components/map/MapCanvas.vue'
import { elderApi } from '../../services/api'
import { convertCanonicalLocation, createOperatorSelectionCoordinator } from '../../services/map/amapCoordinateAdapter'
import { validateCanonicalLocation } from '../../services/map/mapLocationMapper'
import { emergencyContactPresentation } from '../../services/modeBoundary'
import { presentLocationHealth } from '../../services/safetyPresentation'

const props = defineProps({ elders: { type: Array, required: true }, realMode: { type: Boolean, default: false } })
const emit = defineEmits(['show-trips'])
const query = ref('')
const selected = ref(null)
const selectedSafetyView = ref(null)
const elderMapPoint = ref(null)
const elderMapStatus = ref('NO_LOCATION')

const contactPresentation = computed(() => emergencyContactPresentation(props.realMode))
const selectedLocationPresentation = computed(() => presentLocationHealth(
  selectedSafetyView.value,
  Boolean(selectedSafetyView.value)
))
const visibleElders = computed(() => props.elders.filter((elder) => [elder.name, elder.phone, elder.family].some((value) => String(value || '').includes(query.value.trim()))))

const selectionCoordinator = createOperatorSelectionCoordinator({
  fetchSafety: (elderId) => elderApi.safety(elderId),
  convertLocation: (canonical) => convertCanonicalLocation(canonical),
  validateLocation: (loc) => validateCanonicalLocation(loc),
  onStateChange: ({ status, point, safetyView }) => {
    elderMapStatus.value = status
    elderMapPoint.value = point
    selectedSafetyView.value = safetyView || null
  }
})

watch(selected, (newElder) => {
  if (!props.realMode) {
    selectedSafetyView.value = null
    elderMapPoint.value = null
    elderMapStatus.value = 'NO_LOCATION'
    return
  }
  if (newElder) {
    void selectionCoordinator.selectElder(newElder)
  } else {
    selectionCoordinator.clearSelection()
  }
})

onUnmounted(() => {
  selectionCoordinator.clearSelection()
})

function contactFamily() {
  const demoMessage = selected.value ? `${selected.value.family} · ${selected.value.familyPhone}\n演示环境不会发起真实电话。` : ''
  const presentation = emergencyContactPresentation(props.realMode, demoMessage)
  showDialog({ title: presentation.title, message: presentation.message, confirmButtonText: '知道了' })
}

function showTrips() {
  selectionCoordinator.clearSelection()
  selected.value = null
  emit('show-trips')
}
</script>

<template>
  <section class="module-page">
    <header class="module-header"><div><h1>老人档案</h1><p>共 {{ elders.length }} 位{{ realMode ? '后端返回的授权老人' : '演示老人' }}</p></div></header>
    <div class="search-wrap"><van-search v-model="query" shape="round" placeholder="搜索姓名、电话或家属" /></div>
    <div class="elder-list">
      <button v-for="elder in visibleElders" :key="elder.id" class="elder-card" type="button" @click="selected = elder"><span class="avatar">{{ elder.name.slice(-1) }}</span><div><strong>{{ elder.name }} <small>{{ elder.gender ? `${elder.gender} · ` : '' }}{{ elder.age ?? '年龄未提供' }}{{ elder.age == null ? '' : ' 岁' }}</small></strong><p><van-icon name="location-o" />{{ elder.lastLocation || (realMode ? '位置需查看后端安全视图' : '演示位置未提供') }}</p><small>{{ elder.updatedAt || (realMode ? '档案来自后端' : '演示数据') }} · {{ elder.family }}</small></div><em :class="{ danger: elder.status === '告警中', attention: elder.status === '需关注' }">{{ elder.status }}</em><van-icon name="arrow" /></button>
      <van-empty v-if="visibleElders.length === 0" description="没有匹配的老人档案" />
    </div>
    <van-popup v-model:show="selected" position="bottom" round :style="{ padding: '22px 18px 30px' }">
      <div v-if="selected" class="detail-sheet"><div class="detail-title"><span>{{ selected.name.slice(-1) }}</span><div><h2>{{ selected.name }}</h2><p>{{ selected.gender ? `${selected.gender} · ` : '' }}{{ selected.age ?? '年龄未提供' }}{{ selected.age == null ? '' : ' 岁' }} · {{ selected.risk }}</p></div></div><van-cell-group inset><van-cell title="联系电话" :value="selected.phone || (realMode ? '当前接口未提供' : '演示号码未提供')"/><van-cell title="关联家属" :value="selected.family"/><van-cell title="当前状态" :value="selected.status"/><van-cell title="最近位置" :label="selected.lastLocation || (realMode ? '请查看后端安全视图' : '演示位置未提供')" :value="selected.updatedAt || ''"/></van-cell-group><div v-if="realMode && selectedLocationPresentation.isStale" class="location-warning"><strong>{{ selectedLocationPresentation.label }}</strong><p>最后定位时间：{{ selectedLocationPresentation.recordedAtText }}</p></div><div v-if="realMode" class="elder-map-container"><MapCanvas :real-mode="true" :latest-point="elderMapPoint" :status="elderMapStatus" :elder-name="selected.name" height="160px" /></div><div class="detail-actions"><van-button block round plain type="primary" @click="contactFamily">{{ contactPresentation.label }}</van-button><van-button block round type="primary" @click="showTrips">查看出游</van-button></div><p class="privacy-note">{{ realMode ? '真实模式 · 当前接口未返回联系人号码，不会发起拨号' : '演示档案已对电话等敏感信息进行脱敏' }}</p></div>
    </van-popup>
  </section>
</template>

<style scoped>
.module-page{min-height:calc(100vh - 62px);background:#f5f5f5}.module-header{display:flex;align-items:center;gap:12px;padding:20px 16px 18px;color:white;background:linear-gradient(135deg,#667eea,#764ba2)}.module-header button{width:34px;height:34px;color:white;border:0;border-radius:50%;background:rgba(255,255,255,.15)}.module-header h1{margin:0;color:white;font-size:20px;font-weight:700}.module-header p{color:rgba(255,255,255,.75);font-size:11px}.search-wrap{background:white}.elder-list{display:grid;gap:9px;max-width:760px;margin:auto;padding:12px 14px}.elder-card{width:100%;display:flex;align-items:center;gap:10px;padding:13px;color:#323233;border:0;border-radius:10px;background:white;text-align:left}.avatar{width:40px;height:40px;display:grid;place-items:center;flex:none;color:#6657a5;border-radius:50%;background:#efecfa;font-size:14px;font-weight:700}.elder-card>div{min-width:0;flex:1}.elder-card strong{display:block;font-size:13px}.elder-card strong small{color:#969799;font-size:10px;font-weight:400}.elder-card p{margin:3px 0;overflow:hidden;color:#646566;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.elder-card div>small{color:#b0aab4;font-size:9px}.elder-card em{padding:4px 7px;color:#3d9a6b;border-radius:9px;background:#eaf8f1;font-size:9px;font-style:normal;white-space:nowrap}.elder-card em.attention{color:#d78335;background:#fff3e2}.elder-card em.danger{color:#e25e66;background:#fff0f1}.elder-card>.van-icon{color:#c8c9cc}.detail-title{display:flex;align-items:center;gap:12px;margin-bottom:18px}.detail-title>span{width:48px;height:48px;display:grid;place-items:center;color:#6657a5;border-radius:50%;background:#efecfa;font-size:17px;font-weight:700}.detail-title h2{margin:0;color:#323233;font-size:18px}.detail-title p{color:#969799;font-size:11px}.detail-sheet :deep(.van-cell-group--inset){margin:0}.privacy-note{margin-top:14px;color:#b0aab4;text-align:center;font-size:10px}
.detail-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:18px}.detail-actions :deep(.van-button--primary){background:#667eea;border-color:#667eea}.detail-actions :deep(.van-button--plain){color:#667eea;background:white}
.elder-map-container{margin:12px 0;border-radius:10px;overflow:hidden}
.location-warning{margin:12px 0;padding:12px;color:#a26725;border-radius:10px;background:#fff7e8}.location-warning strong,.location-warning p{display:block}.location-warning strong{font-size:13px}.location-warning p{margin-top:4px;font-size:10px}
</style>
