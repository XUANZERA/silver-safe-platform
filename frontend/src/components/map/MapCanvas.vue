<template>
    <div class="map-wrapper">
        <div
            id="map"
            class="map-container"
        ></div>

        <div
            v-if="mapMessage"
            class="map-message"
        >
            {{ mapMessage }}
        </div>
    </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import AMapLoader from "@amap/amap-jsapi-loader"

import elderIcon from "./elder.png"
import { servicePoints } from "../../mock/servicePoints.js"
import { elderTrack } from "../../mock/track.js"
import { geofence } from "../../mock/geofence.js"
import {
    evaluateGeofence,
    isValidCoordinate,
    isValidGeofence,
} from "../../utils/geofence.js"


// 页面上显示的状态或警告信息
const mapMessage = ref("")


/**
 * 清洗轨迹数据。
 */
function normalizeTrack(rawTrack) {
    if (!Array.isArray(rawTrack)) {
        console.warn("轨迹数据不是数组：", rawTrack)
        return []
    }

    return rawTrack.filter(isValidCoordinate)
}


/**
 * 清洗服务点数据。
 */
function normalizeServicePoints(rawServicePoints) {
    if (!Array.isArray(rawServicePoints)) {
        console.warn(
            "服务点数据不是数组：",
            rawServicePoints,
        )

        return []
    }

    return rawServicePoints.filter(isValidCoordinate)
}


/**
 * 创建地图底图。
 */
function createMap(AMap) {
    return new AMap.Map("map", {
        zoom: 15,

        center: [
            113.2644,
            23.1291,
        ],
    })
}


/**
 * 创建圆形电子围栏。
 *
 * 返回值：
 * AMap.Circle 对象
 */
function createGeofenceCircle(AMap, map, fence) {
    if (!isValidGeofence(fence)) {
        throw new Error("电子围栏配置不合法")
    }

    const fenceCenter = new AMap.LngLat(
        fence.center.longitude,
        fence.center.latitude,
    )

    const geofenceCircle = new AMap.Circle({
        center: fenceCenter,

        // 实际地理半径，单位为米
        radius: fence.radius,

        strokeColor: "#1677FF",
        strokeWeight: 3,
        strokeOpacity: 0.9,

        fillColor: "#1677FF",
        fillOpacity: 0.12,

        zIndex: 10,
    })

    map.add(geofenceCircle)

    return geofenceCircle
}


/**
 * 使用高德地图的 GeometryUtil 计算两个经纬度点之间的实际距离。
 */
function createDistanceCalculator(AMap) {
    return (point, center) => {
        const pointLngLat = new AMap.LngLat(
            point.longitude,
            point.latitude,
        )

        const centerLngLat = new AMap.LngLat(
            center.longitude,
            center.latitude,
        )

        return AMap.GeometryUtil.distance(
            pointLngLat,
            centerLngLat,
        )
    }
}


/**
 * 告警状态下将围栏切换为红色。
 */
function updateGeofenceCircleStyle(
    geofenceCircle,
    geofenceState,
) {
    if (!geofenceState?.isConfirmedOutside) {
        return
    }

    geofenceCircle.setOptions({
        strokeColor: "#FF4D4F",
        fillColor: "#FF4D4F",
        fillOpacity: 0.18,
    })
}


/**
 * 把围栏判定结果输出到控制台，方便演示和排查。
 */
function logGeofenceState(geofenceState) {
    if (!geofenceState) {
        return
    }

    console.log(
        "老人距离围栏中心：",
        Math.round(geofenceState.distanceToFenceCenter),
        "米",
    )

    console.log(
        "老人是否越界：",
        geofenceState.isLatestPointOutside,
    )

    console.log("围栏状态：", geofenceState.status)
    console.log("围栏说明：", geofenceState.statusText)
}


/**
 * 创建老人轨迹线。
 *
 * 轨迹少于两个点时不创建折线。
 */
function createTrackLine(AMap, map, validTrack) {
    if (validTrack.length < 2) {
        return null
    }

    const trackPath = validTrack.map((point) => [
        point.longitude,
        point.latitude,
    ])

    const trackLine = new AMap.Polyline({
        path: trackPath,
        strokeColor: "#3366FF",
        strokeWeight: 6,
        strokeOpacity: 0.9,
        lineJoin: "round",
        lineCap: "round",
        zIndex: 20,
    })

    map.add(trackLine)

    return trackLine
}


/**
 * 创建老人图标对应的 HTML 元素。
 */
function createElderIconElement() {
    const image = document.createElement("img")

    image.src = elderIcon
    image.alt = "老人当前位置"

    image.width = 36
    image.height = 36

    image.style.display = "block"
    image.style.width = "36px"
    image.style.height = "36px"
    image.style.maxWidth = "none"
    image.style.objectFit = "contain"

    return image
}


/**
 * 创建老人当前位置 Marker。
 *
 * 轨迹为空时不创建。
 */
function createElderMarker(
    AMap,
    map,
    validTrack,
    geofenceState,
) {
    if (validTrack.length === 0) {
        return null
    }

    const latestLocation =
        validTrack[validTrack.length - 1]

    const elderMarker = new AMap.Marker({
        position: [
            latestLocation.longitude,
            latestLocation.latitude,
        ],

        content: createElderIconElement(),
        anchor: "bottom-center",
        title: "老人当前位置",

        zIndex: 100,
    })

    const recordedAt =
        latestLocation.recordedAt ??
        latestLocation.recordAt ??
        "时间未知"

    elderMarker.setLabel({
        direction: "top",
        offset: new AMap.Pixel(0, -8),
        content: geofenceState
            ? [
                geofenceState.statusText,
                `距围栏中心：${Math.round(
                    geofenceState.distanceToFenceCenter,
                )}米`,
                `更新时间：${recordedAt}`,
            ].join("<br>")
            : `老人当前位置 ${recordedAt}`,
    })

    map.add(elderMarker)

    return elderMarker
}


/**
 * 创建老人出游起点。
 *
 * 至少需要两个有效轨迹点；
 * 单点轨迹不重复显示起点和当前位置。
 */
function createStartMarker(AMap, map, validTrack) {
    if (validTrack.length < 2) {
        return null
    }

    const firstLocation = validTrack[0]

    const startMarker = new AMap.Marker({
        position: [
            firstLocation.longitude,
            firstLocation.latitude,
        ],

        title: "老人出游起点",
    })

    startMarker.setLabel({
        direction: "bottom",
        offset: new AMap.Pixel(0, 5),
        content: "老人出游起点",
    })

    map.add(startMarker)

    return startMarker
}


/**
 * 创建全部服务点 Marker。
 */
function createServiceMarkers(
    AMap,
    map,
    validServicePoints,
) {
    const markers = validServicePoints.map((point) => {
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


/**
 * 把非空覆盖物添加到 overlays 数组。
 */
function addOverlay(overlays, overlay) {
    if (overlay) {
        overlays.push(overlay)
    }
}


/**
 * 生成数据清洗提示信息。
 */
function buildDataMessages(
    rawTrack,
    validTrack,
    rawServicePoints,
    validServicePoints,
) {
    const messages = []

    if (validTrack.length === 0) {
        messages.push("暂无有效轨迹数据")
    }

    if (Array.isArray(rawTrack)) {
        const invalidTrackCount =
            rawTrack.length - validTrack.length

        if (invalidTrackCount > 0) {
            messages.push(
                `已忽略 ${invalidTrackCount} 个非法轨迹点`,
            )
        }
    }

    if (Array.isArray(rawServicePoints)) {
        const invalidServicePointCount =
            rawServicePoints.length -
            validServicePoints.length

        if (invalidServicePointCount > 0) {
            messages.push(
                `已忽略 ${invalidServicePointCount} 个非法服务点`,
            )
        }
    }

    return messages
}


/**
 * 初始化整个地图组件。
 *
 * 它只负责安排执行顺序，
 * 具体绘制工作交给上面的函数。
 */
async function initializeMap() {
    try {
        mapMessage.value = ""

        // 1. 加载高德地图 API
        const AMap = await AMapLoader.load({
            key: import.meta.env.VITE_AMAP_KEY,
            version: "2.0",
        })

        // 2. 创建底图
        const map = createMap(AMap)

        // 3. 清洗外部输入数据
        const validTrack =
            normalizeTrack(elderTrack)

        const validServicePoints =
            normalizeServicePoints(servicePoints)

        // 4. 保存参与自动缩放的覆盖物
        const overlays = []

        // 5. 创建电子围栏
        const geofenceCircle =
            createGeofenceCircle(
                AMap,
                map,
                geofence,
            )

        addOverlay(overlays, geofenceCircle)

        // 6. 计算围栏状态；连续三个轨迹点越界才触发正式告警
        const geofenceState = evaluateGeofence(
            elderTrack,
            geofence,
            createDistanceCalculator(AMap),
        )

        updateGeofenceCircleStyle(
            geofenceCircle,
            geofenceState,
        )

        logGeofenceState(geofenceState)

        // 7. 创建轨迹线
        const trackLine =
            createTrackLine(
                AMap,
                map,
                validTrack,
            )

        addOverlay(overlays, trackLine)

        // 8. 创建老人当前位置并显示围栏状态
        const elderMarker =
            createElderMarker(
                AMap,
                map,
                validTrack,
                geofenceState,
            )

        addOverlay(overlays, elderMarker)

        // 9. 创建出游起点
        const startMarker =
            createStartMarker(
                AMap,
                map,
                validTrack,
            )

        addOverlay(overlays, startMarker)

        // 10. 创建服务点
        const serviceMarkers =
            createServiceMarkers(
                AMap,
                map,
                validServicePoints,
            )

        overlays.push(...serviceMarkers)

        // 11. 自动调整地图视野
        if (overlays.length > 0) {
            map.setFitView(
                overlays,
                false,
                [60, 60, 60, 60],
                17,
            )
        }

        // 12. 显示数据清洗信息
        const messages = buildDataMessages(
            elderTrack,
            validTrack,
            servicePoints,
            validServicePoints,
        )

        if (messages.length > 0) {
            mapMessage.value = messages.join("；")
            console.warn(mapMessage.value)
        }
    } catch (error) {
        console.error(
            "地图模块初始化失败：",
            error,
        )

        const reason =
            error instanceof Error
                ? error.message
                : "未知错误"

        mapMessage.value =
            `地图初始化失败：${reason}`
    }
}

onMounted(initializeMap)
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

.map-message {
    position: absolute;
    top: 16px;
    left: 50%;
    z-index: 1000;
    transform: translateX(-50%);

    max-width: calc(100% - 32px);
    padding: 10px 16px;

    color: #333;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #ddd;
    border-radius: 8px;
}
</style>
