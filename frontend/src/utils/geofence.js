export const GEOFENCE_STATUS = Object.freeze({
    SAFE: "SAFE",
    PENDING: "PENDING",
    ALERT: "ALERT",
})

const STATUS_TEXT = Object.freeze({
    [GEOFENCE_STATUS.SAFE]: "✅ 老人在电子围栏内",
    [GEOFENCE_STATUS.PENDING]: "⚠️ 检测到单点越界，等待后续位置确认",
    [GEOFENCE_STATUS.ALERT]: "🚨 老人已连续三次越出电子围栏",
})

function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value)
}

export function isValidCoordinate(point) {
    return Boolean(
        point &&
        typeof point === "object" &&
        isFiniteNumber(point.longitude) &&
        point.longitude >= -180 &&
        point.longitude <= 180 &&
        isFiniteNumber(point.latitude) &&
        point.latitude >= -90 &&
        point.latitude <= 90,
    )
}

export function isValidGeofence(fence) {
    return Boolean(
        fence &&
        typeof fence === "object" &&
        isValidCoordinate(fence.center) &&
        isFiniteNumber(fence.radius) &&
        fence.radius > 0,
    )
}

function measureDistance(point, center, calculateDistance) {
    const distance = calculateDistance(point, center)

    if (!isFiniteNumber(distance) || distance < 0) {
        throw new Error("围栏距离计算结果不合法")
    }

    return distance
}

/**
 * 根据轨迹末尾的连续三个点计算当前电子围栏状态。
 *
 * calculateDistance 由调用方注入，使业务判定不依赖具体地图 SDK。
 */
export function evaluateGeofence(track, fence, calculateDistance) {
    if (!isValidGeofence(fence)) {
        throw new Error("电子围栏配置不合法")
    }

    if (!Array.isArray(track) || track.length === 0) {
        return null
    }

    if (typeof calculateDistance !== "function") {
        throw new TypeError("围栏距离计算函数不合法")
    }

    const latestLocation = track[track.length - 1]

    if (!isValidCoordinate(latestLocation)) {
        throw new Error("老人最新位置不合法")
    }

    const distanceToFenceCenter = measureDistance(
        latestLocation,
        fence.center,
        calculateDistance,
    )

    const isLatestPointOutside = distanceToFenceCenter > fence.radius
    const recentThreePoints = track.slice(-3)
    const isConfirmedOutside =
        recentThreePoints.length === 3 &&
        recentThreePoints.every((point) => {
            if (!isValidCoordinate(point)) {
                return false
            }

            return (
                measureDistance(point, fence.center, calculateDistance) >
                fence.radius
            )
        })

    let status = GEOFENCE_STATUS.SAFE

    if (isLatestPointOutside) {
        status = isConfirmedOutside
            ? GEOFENCE_STATUS.ALERT
            : GEOFENCE_STATUS.PENDING
    }

    return {
        status,
        statusText: STATUS_TEXT[status],
        distanceToFenceCenter,
        isLatestPointOutside,
        isConfirmedOutside,
        latestLocation,
    }
}
