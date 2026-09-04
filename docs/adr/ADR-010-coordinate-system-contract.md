# ADR-010: Coordinate System Contract

## Status

Accepted

## Context

当前 `backend/app/models/location.py::Location` 和 `backend/app/schemas/location.py::LocationCreateRequest` 只有 latitude/longitude，没有坐标参考系字段。`source` 只能表达 `simulation` 或 `h5`，不能表达坐标系。

以下平台事实已经确认：

- Web Geolocation API 的 `GeolocationCoordinates` 使用 WGS84。
- AMap（高德地图）使用 GCJ-02。
- AMap 支持将 GPS/WGS84 坐标转换为高德坐标后展示。

如果不同坐标系未经明确校验和转换就进入持久化、围栏或风险计算，即使 latitude/longitude 数值合法，也可能产生错误距离、错误越界和错误地图位置。因此，坐标系必须成为 Location contract 和地图展示边界的显式约束。

## Decision

采用以下坐标系契约：

| Concern | CRS |
| --- | --- |
| Browser/H5 source | WGS84 |
| Backend canonical | WGS84 |
| Persisted Location | WGS84 |
| Geofence | WGS84 |
| Risk evaluation | WGS84 |
| AMap rendering | GCJ-02 |

### Source CRS

Location Input 必须显式携带 `source_crs`。Phase 1 后端仅接受 `source_crs = WGS84`；Browser/H5 必须按 Web Geolocation API 的实际坐标系声明 WGS84。

`source` 与 `source_crs` 含义不同：`source` 标识数据提供者，`source_crs` 标识该提供者本次上报坐标的参考系，二者不得互相替代。

### Canonical CRS

Backend canonical CRS 为 WGS84。Backend/domain 中使用的 Location、Geofence 以及交给 Risk evaluation 的坐标始终为 WGS84。

### Persistence CRS

持久化 Location 的 latitude/longitude 必须是 canonical WGS84。即使保留原始输入及其 `source_crs` 作为追溯信息，也不得把非 WGS84 原始坐标当作 canonical Location 持久化。

### Geofence CRS

Geofence CRS 为 WGS84。围栏与 Location 必须在相同的 WGS84 坐标系中参与距离和边界计算。

### Risk CRS

Risk evaluation CRS 为 WGS84。Risk Domain 只接收 canonical WGS84 Location 和 WGS84 Geofence，不负责识别、猜测或转换输入 CRS。

### Map CRS

AMap rendering CRS 为 GCJ-02。WGS84 到 GCJ-02 的转换只能发生在进入 AMap 的 presentation boundary 时，转换结果仅用于地图展示，不得回写为 backend canonical coordinate、Persisted Location、Geofence 或 Risk input。

地图组件不得把 AMap/GCJ-02 的展示坐标泄漏回 Backend/domain。

### Unknown CRS Behavior

缺失、未知或当前不支持的 `source_crs` 必须 reject，不得进入 persistence、Geofence comparison 或 Risk evaluation。

禁止对 CRS 进行静默默认、猜测或基于坐标数值推断。Phase 1 中，任何非 WGS84 的 `source_crs` 都属于当前不支持的输入并必须 reject。

### Future Provider Extension

未来若增加输出 GCJ-02 的 source provider，必须显式扩展后端允许的 `source_crs` 集合，并在 Backend Coordinate Normalization boundary 将 GCJ-02 转换为 canonical WGS84。只有归一化成功后的 WGS84 坐标才能进入 persistence、Geofence comparison 和 Risk evaluation。

新增 provider 不得改变 canonical、persistence、Geofence 或 Risk CRS，也不得借用 AMap presentation conversion 处理 Domain 输入。

## Rationale

- Browser/H5 原生输出与 backend canonical 同为 WGS84，Phase 1 不需要在采集链路引入非必要转换。
- Persistence、Geofence 和 Risk evaluation 统一为 WGS84，可以避免跨 CRS 直接计算距离或边界。
- AMap 的 GCJ-02 要求属于展示系统约束，不应反向决定 Domain 和持久化模型。
- 把 WGS84 → GCJ-02 限制在 AMap presentation boundary，可以防止展示坐标污染后端状态。
- 显式 `source_crs` 和 reject-on-unknown 使错误可观察、可测试，避免静默偏移。

## Data Flow

Phase 1 Browser/H5：

```text
Web Geolocation API
  → raw WGS84 latitude/longitude + source_crs=WGS84
  → backend validates source_crs (WGS84 only)
  → Backend Coordinate Normalization (identity for WGS84)
  → canonical WGS84
  ├→ persist Location as WGS84
  ├→ compare with WGS84 Geofence
  └→ Risk evaluation in WGS84
```

AMap presentation：

```text
backend/domain WGS84
  → AMap presentation boundary
  → convert WGS84 to GCJ-02
  → render in AMap as GCJ-02
```

未来 GCJ-02 source provider：

```text
provider GCJ-02 latitude/longitude + source_crs=GCJ-02
  → backend validates explicitly supported source_crs
  → Backend Coordinate Normalization converts GCJ-02 to WGS84
  → canonical WGS84
  ├→ persist Location as WGS84
  ├→ compare with WGS84 Geofence
  └→ Risk evaluation in WGS84
```

## Alternatives Considered

1. 继续不记录 CRS：拒绝，无法发现或追溯坐标混用。
2. 所有客户端自行转换后上传：拒绝，转换逻辑和版本会漂移。
3. 使用 GCJ-02 作为 backend canonical：拒绝，地图展示约束不应扩散到 persistence、Geofence 和 Risk Domain。
4. 在整个系统中同时使用 WGS84 和 GCJ-02：拒绝，会扩大坐标混用和重复转换的风险。
5. Backend/domain 统一 WGS84，仅在 AMap presentation boundary 转为 GCJ-02：采用。

## Consequences

### Positive

- 坐标含义可验证、可审计。
- Persistence、Geofence 和 Risk Domain 不会静默混用不同 CRS。
- Browser/H5 原生 WGS84 可以直接归一化为 canonical WGS84。
- AMap 展示转换与 Domain 坐标转换责任明确分离。
- 未来 provider 可通过统一的 backend normalization boundary 接入，而不改变 Domain contract。

### Negative

- Location contract 和数据库 schema 需要演进。
- 需要维护 WGS84/GCJ-02 转换实现、固定样本和边界测试。
- AMap 上显示的 GCJ-02 坐标不能直接复用为 Domain 坐标。

### Risks

- 客户端错误声明 source_crs 仍可能产生错误结果，需要测试和监控。
- 现有非 WGS84 围栏或 Location 数据必须在使用前明确迁移，不能靠默认值解释。
- 展示转换如果重复执行或结果回流，可能造成二次偏移。
- 未来 GCJ-02 provider 的反向归一化实现必须独立验证后才能用于 safety-critical 判断。

## Current Code Impact

- Location Input contract 需要必填 `source_crs`；Phase 1 只接受 WGS84。
- Persisted Location、Geofence 和 Risk contract 需要明确限定为 WGS84。
- Backend normalization boundary 需要校验 `source_crs`；Phase 1 对 WGS84 执行 identity normalization。
- AMap presentation adapter 需要负责 WGS84 → GCJ-02，并阻止展示坐标回流 Domain。
- 未来支持 GCJ-02 source provider 时，需要在 backend normalization boundary 增加 GCJ-02 → WGS84。

GAP：当前 Location、Geofence 和 API contract 均没有显式 CRS；仓库没有统一 Coordinate Normalizer。

## Testing Requirements

1. Contract tests 必须验证 Phase 1 接受显式 `source_crs=WGS84`。
2. Contract tests 必须验证缺失、未知、大小写/拼写错误以及非 WGS84 的 `source_crs` 被 reject，且不会写入 persistence 或触发 Risk evaluation。
3. Tests 必须证明系统没有 silent CRS default、guess 或基于数值范围的 CRS 推断路径。
4. Persistence tests 必须验证保存的 Location latitude/longitude 被定义并读取为 WGS84；如保留 raw 坐标，必须与 canonical 字段及其 CRS 明确区分。
5. Geofence 和 Risk tests 必须验证参与计算的 Location 与 Geofence 均为 WGS84，Risk Domain 不执行坐标转换。
6. AMap adapter tests 必须使用固定 WGS84/GCJ-02 样本验证 WGS84 → GCJ-02 转换，并验证转换只发生一次。
7. Boundary tests 必须验证 GCJ-02 展示结果不会回写 persistence、Geofence 或 Risk input。
8. 浏览器真机/集成测试必须以已知地点验证 Web Geolocation WGS84 经后端处理后，与转换后的 AMap GCJ-02 展示位置一致，并覆盖转换误差容限。
9. 未来增加 GCJ-02 source provider 前，必须新增 backend normalization tests，验证 GCJ-02 → WGS84 后才允许 persistence 和 Risk evaluation；转换失败必须 reject。
