# ADR-005: Mock Location Provider

## Status

Accepted

## Context

当前仓库唯一主动产生位置点的实现是：

```text
frontend/src/mock/track.js
→ frontend/src/services/locationSimulator.js
→ frontend/src/components/map/MapCanvas.vue
→ frontend/src/services/simulationLocation.js
→ Location API（配置后）
```

该模拟器已经能够按顺序产生位置点，并通过与真实后端相同的 Location API 触发持久化、后端围栏检测和 Alert。它对于演示和稳定复现风险场景有价值，不能因接入真实定位而删除。

当前 GAP 是模拟器、上传队列、地图和前端风险计算集中在 `MapCanvas.vue`，且尚无 RealLocationProvider。

## Decision

保留 Mock Simulator，并将其定位为 `MockLocationProvider` 的内部实现。

必须提供两个薄的 Location source：

```text
LocationProvider
├─ MockLocationProvider
└─ RealLocationProvider
```

二者必须进入同一个 Location Upload Contract 和同一个后端 Location API。Provider 只负责产生原始位置样本，不负责后端风险判断或最终安全状态。

MockLocationProvider 的正式用途限定为：

- Demo
- Regression Test
- Offline Development
- Failure Reproduction

真实模式必须显式选择 RealLocationProvider，不得在失败时静默切换为 Mock 并继续显示为真实数据。

## Alternatives Considered

1. 接入真实定位后删除模拟器：会失去可重复测试和演示能力。
2. Mock 使用独立后端接口：无法验证真实上传 contract 和后端闭环。
3. 设计通用插件系统：当前只有两个 Provider，属于过度设计。
4. 使用一个最小 Provider 边界和统一上传 contract：采用。

## Consequences

### Positive

- 同一条后端链路既可真实测试，也可确定性回归。
- 风险事件和故障场景容易稳定复现。
- Phase 2 只需增加微信平台 Provider，不改变业务 API。
- 地图不再关心位置来自 Mock 还是真实设备。

### Negative

- 需要从 `MapCanvas.vue` 移出模拟控制和上传协调职责。
- 模拟数据必须携带清晰来源，避免与真实数据混淆。
- Provider contract 需要覆盖权限错误、定位错误和停止状态。

### Risks

- Mock 数据进入真实统计或真实运营页面会污染业务结论。
- Mock 与 Real 使用不同 payload mapper 会造成接口漂移。
- 生产环境必须继续拒绝 simulation 来源；现有后端已有该保护，不得移除。

## Current Code Impact

- `frontend/src/services/locationSimulator.js` — `KEEP`：作为 MockLocationProvider 内核。
- `frontend/src/services/simulationLocation.js` — `REFACTOR`：演进为统一 Location payload mapper 或调用该 mapper。
- `frontend/src/mock/track.js` — `DEMO ONLY`：保留确定性轨迹数据。
- `frontend/src/components/map/MapCanvas.vue` — `REFACTOR`：移出 Provider 生命周期和上传队列。
- `frontend/src/domain/risk/geofenceRisk.js` — `DEMO ONLY`：不得成为 Mock 上传后的权威结果。
- `backend/app/api/routes/locations.py` — `KEEP`：Mock 和 Real 共用该入口。
- `backend/app/services/locations.py` — `KEEP`：继续校验 `source=simulation` 的环境限制。

GAP：当前没有 LocationProvider 接口、RealLocationProvider 或独立 LocationUploadCoordinator。

## Verification

1. Mock 和 Real 产生的数据通过同一个 payload mapper 和 API endpoint。
2. 后端能够明确区分 simulation 和真实来源。
3. 生产环境 simulation 上传仍返回拒绝结果。
4. 切换 Provider 不需要修改 Map 或后端风险代码。
5. 回归测试可以用固定 Mock 轨迹稳定生成预期后端 Alert。
