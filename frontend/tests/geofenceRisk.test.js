// FIX START: 直接测试 MapCanvas.vue 实际调用的风险状态机。
import assert from "node:assert/strict"
import test from "node:test"

import {
  createInitialGeofenceRiskState,
  detectGeofenceRisk,
} from "../src/domain/risk/geofenceRisk.js"

const fence = {
  center: {
    longitude: 113.2644,
    latitude: 23.1291,
  },
  radius: 300,
}

const insidePoint = {
  longitude: 113.2648,
  latitude: 23.1293,
}

const outsidePoint = {
  longitude: 113.269,
  latitude: 23.1291,
}

test("实际风险状态机在围栏内返回 SAFE", () => {
  const result = detectGeofenceRisk({
    point: insidePoint,
    fence,
    previousState: createInitialGeofenceRiskState(),
  })

  assert.equal(result.status, "SAFE")
  assert.equal(result.consecutiveOutside, 0)
  assert.equal(result.event, null)
})

test("实际风险状态机连续三个越界点只产生一次告警", () => {
  let state = createInitialGeofenceRiskState()

  state = detectGeofenceRisk({ point: outsidePoint, fence, previousState: state })
  assert.equal(state.status, "PENDING")
  assert.equal(state.consecutiveOutside, 1)

  state = detectGeofenceRisk({ point: outsidePoint, fence, previousState: state })
  assert.equal(state.status, "PENDING")
  assert.equal(state.consecutiveOutside, 2)

  state = detectGeofenceRisk({ point: outsidePoint, fence, previousState: state })
  assert.equal(state.status, "ALERT")
  assert.equal(state.consecutiveOutside, 3)
  assert.equal(state.event?.type, "GEOFENCE_EXIT")

  state = detectGeofenceRisk({ point: outsidePoint, fence, previousState: state })
  assert.equal(state.status, "ALERT")
  assert.equal(state.event, null)
})

test("回到围栏内会清零连续越界状态", () => {
  const outsideState = detectGeofenceRisk({
    point: outsidePoint,
    fence,
    previousState: createInitialGeofenceRiskState(),
  })
  const recoveredState = detectGeofenceRisk({
    point: insidePoint,
    fence,
    previousState: outsideState,
  })

  assert.equal(recoveredState.status, "SAFE")
  assert.equal(recoveredState.consecutiveOutside, 0)
  assert.equal(recoveredState.alertActive, false)
})
// FIX END: 直接测试 MapCanvas.vue 实际调用的风险状态机。
