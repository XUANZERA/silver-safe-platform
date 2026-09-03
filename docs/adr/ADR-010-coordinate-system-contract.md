# ADR-010: Coordinate System Contract

## Status

Accepted

## Context

当前 `backend/app/models/location.py::Location` 和 `backend/app/schemas/location.py::LocationCreateRequest` 只有 latitude/longitude，没有坐标参考系字段。`source` 只能表达 `simulation` 或 `h5`，不能表达坐标系。

当前后端演示围栏在 `backend/app/services/seed.py` 中明确与高德仿真地图的 GCJ-02 坐标对齐，但未来 H5 和微信定位的实际输出尚未通过官方文档及真机测试共同确认。如果不同坐标系未经处理进入 `backend/app/services/risk.py`，合法数值仍可能产生错误距离、错误越界和错误地图位置。

## Decision

Location Input 必须显式携带 `source_crs`。

进入 Risk Domain 前，Location 必须经过统一的 Backend Coordinate Normalization：

```text
raw latitude/longitude + source_crs
→ validate known CRS
→ Coordinate Normalization
→ canonical coordinate
→ persistence and/or domain handoff
→ Risk evaluation
```

未知、缺失或当前不支持的 CRS 禁止静默假设，必须拒绝或明确隔离该 Location，使其不能进入风险判断。

坐标转换必须集中在后端明确的 normalization 边界。老人端、家属端、运营端和地图组件不得分别实现互不一致的 Domain 坐标转换。

持久化 Location 必须能够追溯输入 `source_crs`，并明确所存 latitude/longitude 是 raw 还是 canonical。是否同时保存 raw 与 canonical 坐标，在 ADR-TBD-001 决策及详细设计中确定。

### ADR-TBD-001: Canonical Coordinate Reference System

Status = TBD

候选至少包括：

- WGS-84
- GCJ-02

本 ADR 不决定 canonical CRS，也不指定转换函数或第三方实现。

最终决定必须在接入真实 H5 定位之前，基于以下四类证据共同确认：

1. 目标定位平台的官方文档。
2. 当前高德地图实际输入和展示要求。
3. 目标浏览器与目标手机的真机定位测试。
4. Phase 2 未来微信定位接口的要求。

## Alternatives Considered

1. 继续不记录 CRS：拒绝，无法发现或追溯坐标混用。
2. 所有客户端自行转换后上传：拒绝，转换逻辑和版本会漂移。
3. 立即指定 WGS-84 为 canonical：证据尚未完成，暂不决定。
4. 立即指定 GCJ-02 为 canonical：仅当前演示地图不足以支撑长期决定。
5. 显式 source_crs、后端统一 normalization、canonical 保持 TBD：采用。

## Consequences

### Positive

- 坐标含义可验证、可审计。
- Risk Domain 不会静默混用不同 CRS。
- H5、未来微信和高德地图可以通过各自 adapter 接入统一 Domain。
- canonical 决策可以基于证据，而不是当前 Mock 数据猜测。

### Negative

- Location contract 和数据库 schema 需要演进。
- 需要真机测试、固定样本和转换验证。
- 在 canonical 未确定前，真实定位实施存在前置阻塞。

### Risks

- 客户端错误声明 source_crs 仍可能产生错误结果，需要测试和监控。
- 围栏数据也必须迁移或标明 CRS，不能只处理 Location。
- 地图展示坐标与 Domain canonical 可能不同，展示 adapter 必须明确转换责任。
- 未经验证的转换实现不得用于 safety-critical 判断。

## Current Code Impact

- `backend/app/schemas/location.py` — `EXTEND`：Location Input 增加必填 `source_crs`。
- `backend/app/models/location.py` — `EXTEND`：持久化 source CRS，并按详细设计明确 raw/canonical 字段。
- `backend/app/models/geofence.py` — `EXTEND`：围栏坐标必须具备明确 CRS 或迁移到 canonical。
- `backend/app/services/locations.py` — `EXTEND`：在风险调用前执行统一 normalization。
- `backend/app/services/risk.py` — `REFACTOR`：只接收已经归一化的 canonical coordinate。
- `frontend/src/services/simulationLocation.js` — `EXTEND`：Mock Location 明确声明实际 CRS。
- RealLocationProvider — `EXTEND`：上报平台实际输出的 source_crs，不自行猜测。
- `frontend/src/components/map/MapCanvas.vue` — `REFACTOR`：地图 adapter 只处理展示坐标。
- Canonical CRS 和转换实现 — `LATER`：ADR-TBD-001 完成后实施。

GAP：当前 Location、Geofence 和 API contract 均没有显式 CRS；仓库没有统一 Coordinate Normalizer。

## Verification

1. 缺失、未知或不支持的 source_crs 不得进入 Risk Domain。
2. Mock、H5 和未来微信样本均明确标记其实际 CRS。
3. 固定真实位置样本经过 normalization 后，在后端距离计算和高德地图展示中一致。
4. 围栏和 Location 在风险计算前处于同一 canonical CRS。
5. ADR-TBD-001 的最终决策附带官方文档、地图要求、真机测试和微信要求证据。
6. 在 ADR-TBD-001 Accepted 前，不合并任何假定 canonical CRS 的真实定位实现。
