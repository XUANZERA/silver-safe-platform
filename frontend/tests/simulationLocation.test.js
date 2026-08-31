// FIX START: 验证仿真服务层生成后端要求的 snake_case 请求字段。
import assert from "node:assert/strict"
import test from "node:test"

import {
  createSimulationLocationPayload,
} from "../src/services/simulationLocation.js"

test("模拟点会映射为后端定位上传格式", () => {
  const payload = createSimulationLocationPayload({
    tripId: 42,
    runId: "run1",
    sequence: 3,
    point: {
      latitude: 23.1291,
      longitude: 113.2644,
    },
    recordedAt: new Date("2026-08-31T10:00:00Z"),
  })

  assert.deepEqual(payload, {
    client_location_id: "sim:42:run1:3",
    latitude: 23.1291,
    longitude: 113.2644,
    speed_mps: null,
    accuracy_meters: 8,
    source: "simulation",
    recorded_at: "2026-08-31T10:00:00.000Z",
  })
})

test("非法行程 ID 不会生成上传请求", () => {
  assert.throws(
    () => createSimulationLocationPayload({
      tripId: undefined,
      runId: "run1",
      sequence: 1,
      point: { latitude: 23.1291, longitude: 113.2644 },
    }),
    /tripId 必须是正整数/,
  )
})
// FIX END: 验证仿真服务层请求字段映射。
