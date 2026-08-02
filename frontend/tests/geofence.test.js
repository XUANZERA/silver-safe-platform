import assert from "node:assert/strict"
import test from "node:test"

import {
    evaluateGeofence,
    GEOFENCE_STATUS,
} from "../src/utils/geofence.js"

const EARTH_RADIUS_IN_METERS = 6_371_000

const geofence = {
    center: {
        longitude: 113.2644,
        latitude: 23.1291,
    },
    radius: 300,
}

function toRadians(degrees) {
    return (degrees * Math.PI) / 180
}

function calculateHaversineDistance(point, center) {
    const latitudeDelta = toRadians(point.latitude - center.latitude)
    const longitudeDelta = toRadians(point.longitude - center.longitude)
    const pointLatitude = toRadians(point.latitude)
    const centerLatitude = toRadians(center.latitude)

    const haversine =
        Math.sin(latitudeDelta / 2) ** 2 +
        Math.cos(centerLatitude) *
            Math.cos(pointLatitude) *
            Math.sin(longitudeDelta / 2) ** 2

    return (
        2 *
        EARTH_RADIUS_IN_METERS *
        Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine))
    )
}

function createPoint(longitude, latitude, recordedAt) {
    return { longitude, latitude, recordedAt }
}

test("最后三个点均在围栏内时状态为 SAFE", () => {
    const track = [
        createPoint(113.2648, 23.1293, "09:05"),
        createPoint(113.2652, 23.1296, "09:07"),
        createPoint(113.2658, 23.13, "09:09"),
    ]

    const result = evaluateGeofence(
        track,
        geofence,
        calculateHaversineDistance,
    )

    assert.equal(result.status, GEOFENCE_STATUS.SAFE)
    assert.equal(result.statusText, "✅ 老人在电子围栏内")
    assert.equal(result.isLatestPointOutside, false)
    assert.equal(result.isConfirmedOutside, false)
    assert.ok(result.distanceToFenceCenter < geofence.radius)
})

test("只有最新点越界时状态为 PENDING", () => {
    const track = [
        createPoint(113.2648, 23.1293, "09:05"),
        createPoint(113.2652, 23.1296, "09:07"),
        createPoint(113.269, 23.1291, "09:09"),
    ]

    const result = evaluateGeofence(
        track,
        geofence,
        calculateHaversineDistance,
    )

    assert.equal(result.status, GEOFENCE_STATUS.PENDING)
    assert.equal(
        result.statusText,
        "⚠️ 检测到单点越界，等待后续位置确认",
    )
    assert.equal(result.isLatestPointOutside, true)
    assert.equal(result.isConfirmedOutside, false)
    assert.ok(result.distanceToFenceCenter > geofence.radius)
})

test("最后三个点连续越界时状态为 ALERT", () => {
    const track = [
        createPoint(113.269, 23.1291, "09:05"),
        createPoint(113.2695, 23.1293, "09:07"),
        createPoint(113.27, 23.1295, "09:09"),
    ]

    const result = evaluateGeofence(
        track,
        geofence,
        calculateHaversineDistance,
    )

    assert.equal(result.status, GEOFENCE_STATUS.ALERT)
    assert.equal(
        result.statusText,
        "🚨 老人已连续三次越出电子围栏",
    )
    assert.equal(result.isLatestPointOutside, true)
    assert.equal(result.isConfirmedOutside, true)
    assert.ok(result.distanceToFenceCenter > geofence.radius)
})

test("围栏半径不合法时拒绝继续判定", () => {
    const invalidGeofence = {
        ...geofence,
        radius: -1,
    }

    assert.throws(
        () =>
            evaluateGeofence(
                [createPoint(113.2648, 23.1293, "09:05")],
                invalidGeofence,
                calculateHaversineDistance,
            ),
        /电子围栏配置不合法/,
    )
})
