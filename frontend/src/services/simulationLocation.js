// FIX START: 在服务层统一完成前端模拟点到后端定位请求字段的映射。
export function createSimulationLocationPayload({
  tripId,
  runId,
  sequence,
  point,
  sourceCrs,
  recordedAt = new Date(),
}) {
  if (!Number.isInteger(tripId) || tripId <= 0) {
    throw new TypeError("tripId 必须是正整数")
  }
  if (typeof runId !== "string" || !/^[A-Za-z0-9]+$/.test(runId)) {
    throw new TypeError("runId 格式不合法")
  }
  if (!Number.isInteger(sequence) || sequence <= 0) {
    throw new TypeError("sequence 必须是正整数")
  }
  if (
    !point ||
    !Number.isFinite(point.latitude) ||
    !Number.isFinite(point.longitude)
  ) {
    throw new TypeError("模拟定位点不合法")
  }

  const timestamp = recordedAt instanceof Date ? recordedAt : new Date(recordedAt)
  if (Number.isNaN(timestamp.getTime())) {
    throw new TypeError("recordedAt 格式不合法")
  }
  if (sourceCrs !== "WGS84") {
    throw new TypeError("Phase 1 模拟定位必须显式声明 sourceCrs=WGS84")
  }

  return {
    client_location_id: `sim:${tripId}:${runId}:${sequence}`,
    latitude: point.latitude,
    longitude: point.longitude,
    speed_mps: null,
    accuracy_meters: 8,
    source: "simulation",
    source_crs: sourceCrs,
    recorded_at: timestamp.toISOString(),
  }
}
// FIX END: 在服务层统一完成模拟定位字段映射。
