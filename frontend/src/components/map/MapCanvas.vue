<template>
  <div class="map-wrapper" :style="{ height: computedHeight }">
    <div
      ref="mapContainer"
      class="map-container"
      :style="{ height: computedHeight }"
    ></div>

    <div
      v-if="!realMode"
      class="simulation-panel"
    >
      <div class="button-row">
        <button
          type="button"
          :disabled="
            !simulatorReady ||
            simulationStatus === 'RUNNING'
          "
          @click="startSimulation"
        >
          开始模拟
        </button>

        <button
          type="button"
          :disabled="
            simulationStatus !== 'RUNNING'
          "
          @click="pauseSimulation"
        >
          暂停
        </button>

        <button
          type="button"
          :disabled="!simulatorReady"
          @click="resetSimulation"
        >
          重置
        </button>
      </div>

      <p>
        模拟状态：
        <strong>{{ simulationStatus }}</strong>
      </p>

      <p>
        定位进度：
        {{ currentPointNumber }}/{{ totalPoints }}
      </p>

      <p>
        围栏状态：
        <strong>{{ riskStatus }}</strong>
      </p>

      <p>
        距围栏中心：
        {{ currentDistanceMeters }} 米
      </p>

      <p>
        连续越界点：
        {{ consecutiveOutsideCount }}
      </p>

      <div
        v-if="riskEvents.length > 0"
        class="event-box"
      >
        <strong>最新风险事件</strong>

        <p>{{ riskEvents[0].message }}</p>

        <p>
          {{ riskEvents[0].displayTime }}
        </p>
      </div>
    </div>

    <div
      v-if="displayMessage"
      class="map-message"
    >
      {{ displayMessage }}
    </div>
  </div>
</template>


<script setup>
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue"

import elderIcon from "./elder.png"
import { isApiConfigured } from "../../services/api.js"
import {
  createMapLifecycleManager,
  formatPolylinePath,
  loadAMapSdk,
} from "../../services/map/amapCoordinateAdapter.js"

const props = defineProps({
  realMode: {
    type: Boolean,
    default: () => isApiConfigured(),
  },
  latestPoint: {
    type: Object,
    default: null,
  },
  trackPoints: {
    type: Array,
    default: () => [],
  },
  status: {
    type: String,
    default: "READY",
  },
  statusMessage: {
    type: String,
    default: "",
  },
  elderName: {
    type: String,
    default: "老人",
  },
  height: {
    type: String,
    default: "",
  },
})

const emit = defineEmits(["map-ready", "map-error"])

const STATUS_MESSAGES = {
  NO_LOCATION: "暂无可用定位数据",
  DATA_UNAVAILABLE: "暂时无法获取最新位置",
  MAP_CONVERSION_FAILED: "位置暂时无法在地图中显示",
  MAP_UNAVAILABLE: "地图暂时无法加载",
}

const mapContainer = ref(null)
const mapMessage = ref("")

// Simulation demo state
const simulatorReady = ref(false)
const simulationStatus = ref("IDLE")
const currentPointNumber = ref(0)
const totalPoints = ref(0)
const riskStatus = ref("SAFE")
const currentDistanceMeters = ref(0)
const consecutiveOutsideCount = ref(0)
const riskEvents = ref([])

let aMapSdk = null
let mapInstance = null
let geofenceCircle = null
let elderMarker = null
let dynamicTrackLine = null
let simulator = null
let simulationPoints = []
let passedTrack = []
let geofenceRiskState = null

// References to dynamically loaded demo modules
let demoGeofence = null
let demoDetectGeofenceRisk = null
let demoCreateInitialGeofenceRiskState = null

const computedHeight = computed(() => {
  if (props.height) return props.height
  return props.realMode ? "220px" : "600px"
})

const displayMessage = computed(() => {
  if (!props.realMode) {
    return mapMessage.value
  }
  if (props.statusMessage) {
    return props.statusMessage
  }
  if (mapMessage.value) {
    return mapMessage.value
  }
  if (props.status && props.status !== "READY") {
    return STATUS_MESSAGES[props.status] || props.status
  }
  return ""
})

function formatRecordedTime(isoString) {
  if (!isoString) return "位置已更新"
  const date = new Date(isoString)
  if (Number.isNaN(date.getTime())) return "位置已更新"
  return `最后定位：${date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })}`
}

function createElderIconElement() {
  const image = document.createElement("img")
  image.src = elderIcon
  image.alt = props.realMode
    ? `${props.elderName}最新记录位置`
    : `${props.elderName}模拟位置`
  image.style.display = "block"
  image.style.width = "36px"
  image.style.height = "36px"
  image.style.maxWidth = "none"
  image.style.objectFit = "contain"
  return image
}

function isValidCoordinate(point) {
  return (
    point &&
    typeof point === "object" &&
    Number.isFinite(point.longitude) &&
    Number.isFinite(point.latitude) &&
    point.longitude >= -180 &&
    point.longitude <= 180 &&
    point.latitude >= -90 &&
    point.latitude <= 90
  )
}

function normalizeCoordinateList(rawPoints) {
  if (!Array.isArray(rawPoints)) return []
  return rawPoints.filter(isValidCoordinate)
}

// ----------------------------------------------------
// REAL Mode Presentation Logic
// ----------------------------------------------------

function updateRealMarker(point) {
  if (!mapInstance || !aMapSdk) return

  if (!point || !isValidCoordinate(point) || props.status !== "READY") {
    if (elderMarker) {
      mapInstance.remove(elderMarker)
      elderMarker = null
    }
    return
  }

  const position = [point.longitude, point.latitude]

  if (!elderMarker) {
    elderMarker = new aMapSdk.Marker({
      position,
      content: createElderIconElement(),
      anchor: "bottom-center",
      title: `${props.elderName}最新记录位置`,
      zIndex: 100,
    })
    mapInstance.add(elderMarker)
  } else {
    elderMarker.setPosition(position)
    if (typeof elderMarker.setTitle === "function") {
      elderMarker.setTitle(`${props.elderName}最新记录位置`)
    }
  }

  const timeLabel = formatRecordedTime(point.recordedAt)
  elderMarker.setLabel({
    direction: "top",
    offset: new aMapSdk.Pixel(0, -8),
    content: `${props.elderName} | ${timeLabel}`,
  })

  // Center view on the latest position
  const validPath = formatPolylinePath(props.trackPoints)
  if (validPath.length >= 2 && dynamicTrackLine) {
    mapInstance.setFitView([elderMarker, dynamicTrackLine], false, [40, 40, 40, 40], 17)
  } else {
    mapInstance.setCenter(position)
  }
}

function updateRealTrack(track) {
  if (!mapInstance || !aMapSdk) return

  const path = formatPolylinePath(track)
  if (path.length >= 2) {
    if (!dynamicTrackLine) {
      dynamicTrackLine = new aMapSdk.Polyline({
        path,
        strokeColor: "#3366FF",
        strokeWeight: 6,
        strokeOpacity: 0.9,
        lineJoin: "round",
        lineCap: "round",
        zIndex: 20,
      })
      mapInstance.add(dynamicTrackLine)
    } else {
      dynamicTrackLine.setPath(path)
    }
    if (elderMarker) {
      mapInstance.setFitView([elderMarker, dynamicTrackLine], false, [40, 40, 40, 40], 17)
    }
  } else {
    if (dynamicTrackLine) {
      dynamicTrackLine.setPath([])
    }
    if (elderMarker && props.latestPoint && isValidCoordinate(props.latestPoint)) {
      mapInstance.setCenter([props.latestPoint.longitude, props.latestPoint.latitude])
    }
  }
}

let lifecycleManager = null
let isDestroyed = false

async function initializeRealMap() {
  mapMessage.value = ""

  lifecycleManager = createMapLifecycleManager({
    loadSdk: loadAMapSdk,
    initMap: async (AMap) => {
      if (isDestroyed || !mapContainer.value) return null
      aMapSdk = AMap

      const defaultCenter = props.latestPoint && isValidCoordinate(props.latestPoint)
        ? [props.latestPoint.longitude, props.latestPoint.latitude]
        : [116.397428, 39.90923]

      mapInstance = new AMap.Map(mapContainer.value, {
        zoom: 16,
        center: defaultCenter,
      })

      updateRealMarker(props.latestPoint)
      updateRealTrack(props.trackPoints)
      return mapInstance
    },
    onReady: (map) => {
      if (!isDestroyed && map) {
        emit("map-ready", map)
      }
    },
    onError: (error) => {
      if (!isDestroyed) {
        console.error("真实地图初始化失败：", error)
        mapMessage.value = "地图暂时无法加载"
        emit("map-error", error)
      }
    }
  })

  await lifecycleManager.mount()
}

// ----------------------------------------------------
// DEMO Simulation Mode Logic
// ----------------------------------------------------

function handleSimulationPoint(rawPoint, pointIndex) {
  const point = {
    ...rawPoint,
    recordedAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
  }

  passedTrack.push(point)
  currentPointNumber.value = pointIndex + 1

  elderMarker?.setPosition([point.longitude, point.latitude])

  const passedPath = passedTrack.map((tp) => [tp.longitude, tp.latitude])
  dynamicTrackLine?.setPath(passedPath)

  if (demoDetectGeofenceRisk && demoGeofence) {
    const result = demoDetectGeofenceRisk({
      point,
      fence: demoGeofence,
      previousState: geofenceRiskState,
      threshold: 3,
    })
    geofenceRiskState = result
    riskStatus.value = result.status
    currentDistanceMeters.value = Math.round(result.distanceMeters)
    consecutiveOutsideCount.value = result.consecutiveOutside

    elderMarker?.setLabel({
      direction: "top",
      offset: new aMapSdk.Pixel(0, -8),
      content: `${result.status === "ALERT" ? "🚨 已确认越界" : result.status === "PENDING" ? "⚠️ 越界待确认" : "✅ 围栏内安全"} | ${currentDistanceMeters.value}米 | ${point.recordedAt}`,
    })

    if (geofenceCircle) {
      if (result.status === "ALERT") {
        geofenceCircle.setOptions({ strokeColor: "#FF4D4F", fillColor: "#FF4D4F", fillOpacity: 0.2 })
      } else if (result.status === "PENDING") {
        geofenceCircle.setOptions({ strokeColor: "#FA8C16", fillColor: "#FA8C16", fillOpacity: 0.16 })
      } else {
        geofenceCircle.setOptions({ strokeColor: "#1677FF", fillColor: "#1677FF", fillOpacity: 0.12 })
      }
    }

    if (result.event) {
      const event = {
        ...result.event,
        id: `${result.event.type}-${Date.now()}`,
        displayTime: new Date(result.event.occurredAt).toLocaleTimeString("zh-CN", { hour12: false }),
      }
      riskEvents.value.unshift(event)
      riskEvents.value = riskEvents.value.slice(0, 5)
    }
  }
}

async function startSimulation() {
  if (!simulator) {
    mapMessage.value = "定位模拟器尚未初始化"
    return
  }
  if (simulationStatus.value === "COMPLETED") {
    resetSimulation()
  }
  simulator.start()
}

function pauseSimulation() {
  simulator?.pause()
}

function resetSimulation() {
  simulator?.reset()
  passedTrack = []
  if (demoCreateInitialGeofenceRiskState) {
    geofenceRiskState = demoCreateInitialGeofenceRiskState()
  }
  currentPointNumber.value = 0
  currentDistanceMeters.value = 0
  consecutiveOutsideCount.value = 0
  riskStatus.value = "SAFE"
  riskEvents.value = []
  dynamicTrackLine?.setPath([])

  const firstPoint = simulationPoints[0]
  if (firstPoint && elderMarker && aMapSdk) {
    elderMarker.setPosition([firstPoint.longitude, firstPoint.latitude])
    elderMarker.setLabel({
      direction: "top",
      offset: new aMapSdk.Pixel(0, -8),
      content: "等待开始模拟",
    })
  }
}

async function initializeDemoSimulation() {
  try {
    mapMessage.value = ""

    if (isApiConfigured()) {
      mapMessage.value = "定位仿真仅在演示模式可用，不会作为真实定位数据上传"
      return
    }

    // Lazy load mock & simulator modules only in demo mode
    const [
      { servicePoints },
      { elderTrack },
      { geofence },
      { createLocationSimulator },
      { createInitialGeofenceRiskState, detectGeofenceRisk },
    ] = await Promise.all([
      import("../../mock/servicePoints.js"),
      import("../../mock/track.js"),
      import("../../mock/geofence.js"),
      import("../../services/locationSimulator.js"),
      import("../../domain/risk/geofenceRisk.js"),
    ])

    demoGeofence = geofence
    demoDetectGeofenceRisk = detectGeofenceRisk
    demoCreateInitialGeofenceRiskState = createInitialGeofenceRiskState
    geofenceRiskState = createInitialGeofenceRiskState()

    simulationPoints = normalizeCoordinateList(elderTrack)
    if (simulationPoints.length === 0) {
      throw new Error("没有有效的模拟轨迹点")
    }
    totalPoints.value = simulationPoints.length
    const validServicePoints = normalizeCoordinateList(servicePoints)

    const AMap = await loadAMapSdk()
    if (isDestroyed || !mapContainer.value) return
    aMapSdk = AMap

    mapInstance = new AMap.Map(mapContainer.value, {
      zoom: 15,
      center: [geofence.center.longitude, geofence.center.latitude],
    })

    geofenceCircle = new AMap.Circle({
      center: [geofence.center.longitude, geofence.center.latitude],
      radius: geofence.radius,
      strokeColor: "#1677FF",
      strokeWeight: 3,
      strokeOpacity: 0.9,
      fillColor: "#1677FF",
      fillOpacity: 0.12,
      zIndex: 10,
    })
    mapInstance.add(geofenceCircle)

    dynamicTrackLine = new AMap.Polyline({
      path: [],
      strokeColor: "#3366FF",
      strokeWeight: 6,
      strokeOpacity: 0.9,
      lineJoin: "round",
      lineCap: "round",
      zIndex: 20,
    })
    mapInstance.add(dynamicTrackLine)

    const initialPoint = simulationPoints[0]
    elderMarker = new AMap.Marker({
      position: [initialPoint.longitude, initialPoint.latitude],
      content: createElderIconElement(),
      anchor: "bottom-center",
      title: "老人当前位置",
      zIndex: 100,
    })
    elderMarker.setLabel({
      direction: "top",
      offset: new AMap.Pixel(0, -8),
      content: "等待开始模拟",
    })
    mapInstance.add(elderMarker)

    const startMarker = new AMap.Marker({
      position: [initialPoint.longitude, initialPoint.latitude],
      title: "老人出游起点",
    })
    startMarker.setLabel({
      direction: "bottom",
      offset: new AMap.Pixel(0, 5),
      content: "老人出游起点",
    })
    mapInstance.add(startMarker)

    const serviceMarkers = validServicePoints.map((point) => {
      const pointName = point.name ?? "未命名服务点"
      const marker = new AMap.Marker({
        position: [point.longitude, point.latitude],
        title: pointName,
      })
      marker.setLabel({
        direction: "top",
        offset: new AMap.Pixel(0, -5),
        content: pointName,
      })
      return marker
    })
    if (serviceMarkers.length > 0) {
      mapInstance.add(serviceMarkers)
    }

    mapInstance.setFitView(
      [geofenceCircle, startMarker, elderMarker, ...serviceMarkers],
      false,
      [60, 60, 60, 60],
      17,
    )

    simulator = createLocationSimulator({
      points: simulationPoints,
      intervalMs: 2000,
      onPoint: handleSimulationPoint,
      onStatusChange: (nextStatus) => {
        simulationStatus.value = nextStatus
      },
      onComplete: () => {
        console.log("定位模拟完成")
      },
    })
    simulatorReady.value = true
  } catch (error) {
    console.error("地图模块初始化失败：", error)
    mapMessage.value = error instanceof Error ? error.message : "地图初始化失败"
  }
}

// Watchers for reactive updates in REAL mode
watch(
  () => props.latestPoint,
  (newPoint) => {
    if (props.realMode) {
      updateRealMarker(newPoint)
    }
  },
  { deep: true },
)

watch(
  () => props.trackPoints,
  (newTrack) => {
    if (props.realMode) {
      updateRealTrack(newTrack)
    }
  },
  { deep: true },
)

watch(
  () => props.status,
  (newStatus) => {
    if (props.realMode) {
      updateRealMarker(props.latestPoint)
      if (newStatus !== "READY" && dynamicTrackLine) {
        dynamicTrackLine.setPath([])
      }
    }
  },
)

onMounted(() => {
  if (props.realMode) {
    void initializeRealMap()
  } else {
    void initializeDemoSimulation()
  }
})

onUnmounted(() => {
  isDestroyed = true
  lifecycleManager?.destroy()
  simulator?.destroy()
  if (elderMarker && mapInstance) {
    mapInstance.remove(elderMarker)
    elderMarker = null
  }
  if (dynamicTrackLine && mapInstance) {
    mapInstance.remove(dynamicTrackLine)
    dynamicTrackLine = null
  }
  if (geofenceCircle && mapInstance) {
    mapInstance.remove(geofenceCircle)
    geofenceCircle = null
  }
  mapInstance?.destroy()
  mapInstance = null
  aMapSdk = null
})
</script>


<style scoped>
.map-wrapper {
  position: relative;
  width: 100%;
}

.map-container {
  width: 100%;
  height: 100%;
}

.simulation-panel {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 1000;

  width: 260px;
  padding: 14px;

  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #ddd;
  border-radius: 10px;
}

.simulation-panel p {
  margin: 8px 0;
}

.button-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.button-row button {
  padding: 7px 10px;
  cursor: pointer;
}

.button-row button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.event-box {
  margin-top: 12px;
  padding: 10px;

  color: #a8071a;
  background: #fff1f0;
  border: 1px solid #ffa39e;
  border-radius: 8px;
}

.map-message {
  position: absolute;
  top: 16px;
  left: 50%;
  z-index: 1001;

  transform: translateX(-50%);

  max-width: calc(100% - 32px);
  padding: 8px 14px;

  font-size: 11px;
  color: #333;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  pointer-events: none;
}
</style>
