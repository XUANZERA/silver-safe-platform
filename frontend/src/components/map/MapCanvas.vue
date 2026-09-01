<template>
  <div class="map-wrapper">
    <div
      id="map"
      class="map-container"
    ></div>

    <div class="simulation-panel">
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
      v-if="mapMessage"
      class="map-message"
    >
      {{ mapMessage }}
    </div>
  </div>
</template>


<script setup>
import {
  onMounted,
  onUnmounted,
  ref,
} from "vue"

import AMapLoader from "@amap/amap-jsapi-loader"

import elderIcon from "./elder.png"

import {
  servicePoints,
} from "../../mock/servicePoints.js"

import {
  elderTrack,
} from "../../mock/track.js"

import {
  geofence,
} from "../../mock/geofence.js"

import {
  createLocationSimulator,
} from "../../services/locationSimulator.js"

import {
  createInitialGeofenceRiskState,
  detectGeofenceRisk,
} from "../../domain/risk/geofenceRisk.js"

// FIX START: 仿真页面接入现有行程与定位 API，字段映射留在服务层。
import {
  elderApi,
  isApiConfigured,
  locationApi,
} from "../../services/api.js"
import {
  createSimulationLocationPayload,
} from "../../services/simulationLocation.js"
// FIX END: 仿真页面接入现有行程与定位 API。


const mapMessage = ref("")

const simulatorReady = ref(false)

const simulationStatus = ref("IDLE")

const currentPointNumber = ref(0)

const totalPoints = ref(0)

const riskStatus = ref("SAFE")

const currentDistanceMeters = ref(0)

const consecutiveOutsideCount = ref(0)

const riskEvents = ref([])


let mapInstance = null
let geofenceCircle = null
let elderMarker = null
let dynamicTrackLine = null
let simulator = null

let simulationPoints = []
let passedTrack = []

// FIX START: 保存本次仿真对应的后端行程和有序上传队列。
let activeTripId = null
let simulationRunId = Date.now().toString(36)
let uploadQueue = Promise.resolve()
// FIX END: 保存后端行程和有序上传队列。

let geofenceRiskState =
  createInitialGeofenceRiskState()


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
  if (!Array.isArray(rawPoints)) {
    return []
  }

  return rawPoints.filter(isValidCoordinate)
}


function isValidGeofence(fence) {
  return (
    fence &&
    typeof fence === "object" &&
    isValidCoordinate(fence.center) &&
    Number.isFinite(fence.radius) &&
    fence.radius > 0
  )
}


function createElderIconElement() {
  const image =
    document.createElement("img")

  image.src = elderIcon
  image.alt = "老人当前位置"

  image.style.display = "block"
  image.style.width = "36px"
  image.style.height = "36px"
  image.style.maxWidth = "none"
  image.style.objectFit = "contain"

  return image
}


function createMap(AMap) {
  return new AMap.Map("map", {
    zoom: 15,

    center: [
      geofence.center.longitude,
      geofence.center.latitude,
    ],
  })
}


function createGeofenceCircle(
  AMap,
  map,
) {
  const circle = new AMap.Circle({
    center: [
      geofence.center.longitude,
      geofence.center.latitude,
    ],

    radius: geofence.radius,

    strokeColor: "#1677FF",
    strokeWeight: 3,
    strokeOpacity: 0.9,

    fillColor: "#1677FF",
    fillOpacity: 0.12,

    zIndex: 10,
  })

  map.add(circle)

  return circle
}


function createDynamicTrackLine(
  AMap,
  map,
) {
  const line = new AMap.Polyline({
    // 初始没有已走轨迹
    path: [],

    strokeColor: "#3366FF",
    strokeWeight: 6,
    strokeOpacity: 0.9,

    lineJoin: "round",
    lineCap: "round",

    zIndex: 20,
  })

  map.add(line)

  return line
}


function createElderMarker(
  AMap,
  map,
  initialPoint,
) {
  const marker = new AMap.Marker({
    position: [
      initialPoint.longitude,
      initialPoint.latitude,
    ],

    content: createElderIconElement(),

    anchor: "bottom-center",
    title: "老人当前位置",
    zIndex: 100,
  })

  marker.setLabel({
    direction: "top",
    offset: new AMap.Pixel(0, -8),
    content: "等待开始模拟",
  })

  map.add(marker)

  return marker
}


function createStartMarker(
  AMap,
  map,
  initialPoint,
) {
  const marker = new AMap.Marker({
    position: [
      initialPoint.longitude,
      initialPoint.latitude,
    ],

    title: "老人出游起点",
  })

  marker.setLabel({
    direction: "bottom",
    offset: new AMap.Pixel(0, 5),
    content: "老人出游起点",
  })

  map.add(marker)

  return marker
}


function createServiceMarkers(
  AMap,
  map,
  validServicePoints,
) {
  const markers =
    validServicePoints.map((point) => {
      const pointName =
        point.name ?? "未命名服务点"

      const marker = new AMap.Marker({
        position: [
          point.longitude,
          point.latitude,
        ],

        title: pointName,
      })

      marker.setLabel({
        direction: "top",
        offset: new AMap.Pixel(0, -5),
        content: pointName,
      })

      return marker
    })

  if (markers.length > 0) {
    map.add(markers)
  }

  return markers
}


function formatCurrentTime() {
  return new Date().toLocaleTimeString(
    "zh-CN",
    {
      hour12: false,
    },
  )
}


function getRiskStatusText(status) {
  if (status === "ALERT") {
    return "🚨 已确认越界"
  }

  if (status === "PENDING") {
    return "⚠️ 越界待确认"
  }

  return "✅ 围栏内安全"
}


function updateGeofenceAppearance(status) {
  if (!geofenceCircle) {
    return
  }

  if (status === "ALERT") {
    geofenceCircle.setOptions({
      strokeColor: "#FF4D4F",
      fillColor: "#FF4D4F",
      fillOpacity: 0.2,
    })

    return
  }

  if (status === "PENDING") {
    geofenceCircle.setOptions({
      strokeColor: "#FA8C16",
      fillColor: "#FA8C16",
      fillOpacity: 0.16,
    })

    return
  }

  geofenceCircle.setOptions({
    strokeColor: "#1677FF",
    fillColor: "#1677FF",
    fillOpacity: 0.12,
  })
}


// FIX START: 查找当前老人正在进行的行程，并按顺序上传每个模拟点。
async function prepareSimulationUpload() {
  if (!isApiConfigured()) {
    activeTripId = null
    return true
  }

  try {
    const elders = await elderApi.list()
    const currentElder = elders?.items?.[0]
    if (!currentElder) throw new Error("没有可用于仿真的老人资料")

    const trip = await elderApi.currentTrip(currentElder.id)
    if (!trip || trip.status !== "active") {
      throw new Error("请先在老人首页开始行程，再运行定位仿真")
    }

    activeTripId = trip.id
    mapMessage.value = ""
    return true
  } catch (error) {
    activeTripId = null
    mapMessage.value = error instanceof Error ? error.message : "无法读取当前行程"
    return false
  }
}


function queueSimulationUpload(point, pointIndex) {
  if (!isApiConfigured() || !activeTripId) {
    return
  }

  const tripId = activeTripId
  const payload = createSimulationLocationPayload({
    tripId,
    runId: simulationRunId,
    sequence: pointIndex + 1,
    point,
  })

  uploadQueue = uploadQueue
    .then(() => locationApi.upload(tripId, payload))
    .then((response) => {
      console.info("模拟定位已上传：", response)
    })
    .catch((error) => {
      console.error("模拟定位上传失败：", error)
      mapMessage.value = `第 ${pointIndex + 1} 个模拟点上传失败：${error instanceof Error ? error.message : "请求失败"}`
    })
}
// FIX END: 查找当前行程并按顺序上传模拟点。


/**
 * 每收到一个模拟定位点时执行。
 */
function handleLocationPoint(
  rawPoint,
  pointIndex,
) {
  const point = {
    ...rawPoint,
    recordedAt: formatCurrentTime(),
  }

  passedTrack.push(point)

  currentPointNumber.value =
    pointIndex + 1

  // 1. 更新老人Marker
  elderMarker.setPosition([
    point.longitude,
    point.latitude,
  ])

  // 2. 更新已经走过的轨迹
  const passedPath =
    passedTrack.map((trackPoint) => [
      trackPoint.longitude,
      trackPoint.latitude,
    ])

  dynamicTrackLine.setPath(passedPath)

  // 3. 执行电子围栏风险检测
  const result = detectGeofenceRisk({
    point,
    fence: geofence,
    previousState: geofenceRiskState,
    threshold: 3,
  })

  geofenceRiskState = result

  riskStatus.value = result.status

  currentDistanceMeters.value =
    Math.round(result.distanceMeters)

  consecutiveOutsideCount.value =
    result.consecutiveOutside

  // 4. 更新老人标签
  elderMarker.setLabel({
    direction: "top",
    offset: new window.AMap.Pixel(0, -8),

    content:
      `${getRiskStatusText(result.status)} | ` +
      `${currentDistanceMeters.value}米 | ` +
      `${point.recordedAt}`,
  })

  // 5. 更新围栏颜色
  updateGeofenceAppearance(
    result.status,
  )

  // FIX START: 本地展示完成后，将同一个模拟点上传给后端。
  queueSimulationUpload(point, pointIndex)
  // FIX END: 将模拟点上传给后端。

  // 6. 首次达到连续3点越界时产生事件
  if (result.event) {
    const event = {
      ...result.event,

      id:
        `${result.event.type}-${Date.now()}`,

      displayTime:
        new Date(
          result.event.occurredAt,
        ).toLocaleTimeString(
          "zh-CN",
          {
            hour12: false,
          },
        ),
    }

    riskEvents.value.unshift(event)

    // MVP只保留最近5个事件
    riskEvents.value =
      riskEvents.value.slice(0, 5)

    console.warn(
      "产生风险事件：",
      event,
    )
  }
}


async function startSimulation() {
  if (!simulator) {
    mapMessage.value =
      "定位模拟器尚未初始化"

    return
  }

  // 完成后再次点击开始，自动从头播放
  if (
    simulationStatus.value ===
    "COMPLETED"
  ) {
    resetSimulation()
  }

  // FIX START: 配置了真实 API 时，没有 active trip 就不发送伪造行程数据。
  if (isApiConfigured() && !activeTripId) {
    const readyToUpload = await prepareSimulationUpload()
    if (!readyToUpload) return
  }
  // FIX END: 启动前确认后端 active trip。

  simulator.start()
}


function pauseSimulation() {
  simulator?.pause()
}


function resetSimulation() {
  simulator?.reset()

  // FIX START: 每次重放使用新的幂等键前缀，避免与上一次仿真冲突。
  simulationRunId = Date.now().toString(36)
  // FIX END: 每次重放使用新的幂等键前缀。

  passedTrack = []

  geofenceRiskState =
    createInitialGeofenceRiskState()

  currentPointNumber.value = 0
  currentDistanceMeters.value = 0
  consecutiveOutsideCount.value = 0

  riskStatus.value = "SAFE"
  riskEvents.value = []

  dynamicTrackLine?.setPath([])

  const firstPoint =
    simulationPoints[0]

  if (firstPoint && elderMarker) {
    elderMarker.setPosition([
      firstPoint.longitude,
      firstPoint.latitude,
    ])

    elderMarker.setLabel({
      direction: "top",
      offset: new window.AMap.Pixel(
        0,
        -8,
      ),
      content: "等待开始模拟",
    })
  }

  updateGeofenceAppearance("SAFE")
}


async function initializeMap() {
  try {
    mapMessage.value = ""

    if (!isValidGeofence(geofence)) {
      throw new Error(
        "电子围栏配置不合法",
      )
    }

    simulationPoints =
      normalizeCoordinateList(elderTrack)

    if (simulationPoints.length === 0) {
      throw new Error(
        "没有有效的模拟轨迹点",
      )
    }

    const validServicePoints =
      normalizeCoordinateList(
        servicePoints,
      )

    totalPoints.value =
      simulationPoints.length

    const AMap =
      await AMapLoader.load({
        key:
          import.meta.env.VITE_AMAP_KEY,

        version: "2.0",
      })

    mapInstance = createMap(AMap)

    geofenceCircle =
      createGeofenceCircle(
        AMap,
        mapInstance,
      )

    dynamicTrackLine =
      createDynamicTrackLine(
        AMap,
        mapInstance,
      )

    const initialPoint =
      simulationPoints[0]

    elderMarker =
      createElderMarker(
        AMap,
        mapInstance,
        initialPoint,
      )

    const startMarker =
      createStartMarker(
        AMap,
        mapInstance,
        initialPoint,
      )

    const serviceMarkers =
      createServiceMarkers(
        AMap,
        mapInstance,
        validServicePoints,
      )

    // 初始化时显示围栏、起点和服务点
    mapInstance.setFitView(
      [
        geofenceCircle,
        startMarker,
        elderMarker,
        ...serviceMarkers,
      ],

      false,
      [60, 60, 60, 60],
      17,
    )

    simulator =
      createLocationSimulator({
        points: simulationPoints,

        intervalMs: 2000,

        onPoint:
          handleLocationPoint,

        onStatusChange:
          (nextStatus) => {
            simulationStatus.value =
              nextStatus
          },

        onComplete: () => {
          console.log(
            "定位模拟完成",
          )
        },
      })

    simulatorReady.value = true

    // FIX START: 地图可用后预加载 active trip；失败不破坏本地地图初始化。
    await prepareSimulationUpload()
    // FIX END: 预加载 active trip。
  } catch (error) {
    console.error(
      "地图模块初始化失败：",
      error,
    )

    mapMessage.value =
      error instanceof Error
        ? error.message
        : "地图初始化失败"
  }
}


onMounted(initializeMap)


/*
 * 离开页面时停止定时器并销毁地图。
 */
onUnmounted(() => {
  simulator?.destroy()
  mapInstance?.destroy()
})
</script>


<style scoped>
.map-wrapper {
  position: relative;
  width: 100%;
}

.map-container {
  width: 100%;
  height: 600px;
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
  padding: 10px 16px;

  color: #333;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #ddd;
  border-radius: 8px;
}
</style>
