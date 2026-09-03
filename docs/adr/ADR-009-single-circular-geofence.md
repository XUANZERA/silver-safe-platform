# ADR-009: Single Circular Geofence

## Status

Accepted

## Context

当前 `backend/app/models/geofence.py::Geofence` 以 `elder_id` 为主键，每位老人最多一个围栏，字段是中心纬度、中心经度、半径和 enabled。`backend/app/services/risk.py` 使用 Haversine 距离判断点是否位于该圆形围栏外。前端 Mock 围栏也是一个中心点加 300 米半径。

当前没有多个围栏、Polygon、时段、版本或围栏写入 API。Phase 1 的目标是验证真实定位和后端安全闭环，而不是建立通用空间规则系统。

## Decision

Phase 1 采用“一位老人一个圆形电子围栏”：

```text
elder_id
center coordinate
radius
enabled
```

Phase 1 暂不设计：

- 多个围栏
- Polygon geofence
- Time-window geofence
- 围栏组合和优先级

围栏坐标必须遵守 ADR-010 的显式 CRS 和 normalization 决策。

## Alternatives Considered

1. 多圆形围栏：当前没有明确业务需要，暂不采用。
2. Polygon 围栏：需要空间数据、编辑 UI 和更复杂算法，暂不采用。
3. 带时间窗口的围栏：需要计划和调度语义，暂不采用。
4. 保留当前单圆模型并完善真实链路：采用。

## Consequences

### Positive

- 最大化复用当前模型、风险算法和测试。
- 围栏配置和现场校准简单。
- 不需要空间数据库或新的 GIS 基础设施。
- 适合 Phase 1 的街区试验。

### Negative

- 无法表达不规则街区边界。
- 无法同时表达家庭、目的地和临时安全区。
- 一个围栏半径可能只能近似真实游览范围。

### Risks

- 圆形范围过大或过小会产生漏报或误报，必须现场校准。
- CRS 错误会直接破坏围栏判断。
- 围栏修改权限和审计尚未定义。

## Current Code Impact

- `backend/app/models/geofence.py` — `KEEP`：保留一位老人一个圆形围栏的数据模型。
- `backend/app/services/risk.py` — `KEEP`：保留圆形距离判断。
- `backend/app/api/routes/elders.py::get_geofence` — `KEEP`：保留围栏读取。
- `backend/app/services/seed.py` — `KEEP`：继续提供演示围栏，但坐标需遵守 ADR-010。
- `frontend/src/mock/geofence.js` — `DEMO ONLY`：只用于仿真。
- `frontend/src/components/map/MapCanvas.vue` — `REFACTOR`：真实模式绘制后端围栏，不读取 Mock 围栏。
- 多围栏、Polygon 和时段围栏 — `LATER`。

GAP：当前没有围栏创建/更新 API、管理 UI、修改审计或真实模式地图接入。

## Verification

1. 同一老人最多存在一个有效圆形围栏。
2. 家属和运营读取并展示同一个后端围栏。
3. 后端风险测试覆盖圆内、边界附近、圆外和无效围栏。
4. 现场使用真实设备校准半径和精度阈值。
5. Phase 1 schema 和 UI 不预先加入 Polygon 或多围栏复杂度。
