const EARTH_RADIUS_METERS = 6371000


function toRadians(degrees) {
  return degrees * Math.PI / 180
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


/**
 * 使用Haversine公式计算两个经纬度点之间的距离。
 * 返回值单位：米。
 */
export function calculateDistanceMeters(
  pointA,
  pointB,
) {
  if (
    !isValidCoordinate(pointA) ||
    !isValidCoordinate(pointB)
  ) {
    throw new TypeError("用于距离计算的坐标不合法")
  }

  const latitude1 = toRadians(pointA.latitude)
  const latitude2 = toRadians(pointB.latitude)

  const latitudeDifference = toRadians(
    pointB.latitude - pointA.latitude,
  )

  const longitudeDifference = toRadians(
    pointB.longitude - pointA.longitude,
  )

  const haversineValue =
    Math.sin(latitudeDifference / 2) ** 2 +
    Math.cos(latitude1) *
      Math.cos(latitude2) *
      Math.sin(longitudeDifference / 2) ** 2

  const centralAngle =
    2 * Math.asin(
      Math.min(1, Math.sqrt(haversineValue)),
    )

  return EARTH_RADIUS_METERS * centralAngle
}


/**
 * 创建初始风险状态。
 */
export function createInitialGeofenceRiskState() {
  return {
    status: "SAFE",
    consecutiveOutside: 0,
    alertActive: false,
  }
}


/**
 * 对一个新的定位点执行电子围栏风险检测。
 *
 * 状态：
 * SAFE：围栏内
 * PENDING：已经越界，但不足连续3个点
 * ALERT：连续3个点越界
 */
export function detectGeofenceRisk({
  point,
  fence,
  previousState,
  threshold = 3,
}) {
  if (!isValidCoordinate(point)) {
    throw new TypeError("定位点坐标不合法")
  }

  if (
    !fence ||
    !isValidCoordinate(fence.center) ||
    !Number.isFinite(fence.radius) ||
    fence.radius <= 0
  ) {
    throw new TypeError("电子围栏配置不合法")
  }

  const currentState =
    previousState ??
    createInitialGeofenceRiskState()

  const distanceMeters =
    calculateDistanceMeters(
      point,
      fence.center,
    )

  const isOutside =
    distanceMeters > fence.radius

  // 老人回到围栏内
  if (!isOutside) {
    return {
      status: "SAFE",
      distanceMeters,
      isOutside: false,
      consecutiveOutside: 0,
      alertActive: false,
      event: null,
    }
  }

  const consecutiveOutside =
    currentState.consecutiveOutside + 1

  const reachedThreshold =
    consecutiveOutside >= threshold

  const isNewAlert =
    reachedThreshold &&
    !currentState.alertActive

  const alertActive =
    currentState.alertActive ||
    reachedThreshold

  return {
    status: alertActive
      ? "ALERT"
      : "PENDING",

    distanceMeters,
    isOutside: true,
    consecutiveOutside,
    alertActive,

    // 只在首次达到连续3点时产生事件
    event: isNewAlert
      ? {
          type: "GEOFENCE_EXIT",
          level: "HIGH",
          message: `老人连续 ${threshold} 个定位点位于电子围栏外`,
          position: {
            longitude: point.longitude,
            latitude: point.latitude,
          },
          occurredAt: new Date().toISOString(),
        }
      : null,
  }
}