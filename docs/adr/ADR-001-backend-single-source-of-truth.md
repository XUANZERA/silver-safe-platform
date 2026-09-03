# ADR-001: Backend Single Source of Truth

## Status

Accepted

## Context

当前后端已经形成真实的 `Location → persistence → risk evaluation → Alert` 链路：

- `backend/app/api/routes/locations.py::upload_location` 接收定位。
- `backend/app/services/locations.py::record_location` 校验、幂等保存定位，并调用风险检测。
- `backend/app/services/risk.py::evaluate_location_risk` 执行后端电子围栏判断。
- `backend/app/models/location.py::Location` 和 `backend/app/models/alert.py::Alert` 持久化数据。

与此同时，`frontend/src/components/map/MapCanvas.vue::handleLocationPoint` 会在浏览器中调用 `frontend/src/domain/risk/geofenceRisk.js::detectGeofenceRisk`，并把结果写入组件内的 `riskEvents`。家属页面还硬编码“安全区域正常”，运营页面的部分状态与操作来自本地 Mock。

这会让同一个老人同时存在前端风险状态、后端 Alert 状态和运营本地状态，无法保证家属、老人和运营人员看到相同结论。

## Decision

Backend is the single source of truth for real business state.

真实模式下的数据链路必须是：

```text
Location Input
→ Backend Validation and Persistence
→ Backend Risk Evaluation
→ Backend Alert Persistence
→ Backend Query/Projection
→ Elder, Family and Operator Presentation
```

前端可以执行输入校验、地图渲染和演示预览，但不得独立形成或持久化最终风险结论。所有角色展示的 Trip、Location、RiskStatus 和 AlertStatus 必须来自后端数据或后端派生视图。

## Alternatives Considered

1. 前端和后端各自计算风险：拒绝。算法版本、状态和事件去重会发生漂移。
2. 以前端计算为主、后端只保存结果：拒绝。客户端不可作为安全关键业务的可信边界。
3. 保留现有后端闭环，并让所有客户端消费后端结果：采用。

## Consequences

### Positive

- 老人、家属和运营端共享同一业务事实。
- 风险规则、权限、幂等和事件生成可以集中测试。
- 后续迁移微信小程序不会复制风险引擎。
- 服务端可以统一审计和追溯安全事件。

### Negative

- 前端在网络不可用时不能声称得到最新安全结论。
- 地图演示中的即时本地结果只能标记为预览，不能冒充后端状态。
- 家属和运营页面必须从本地 Mock 状态迁移到后端查询。

### Risks

- 如果 UI 未清楚区分“数据不可用”和“安全”，仍可能产生错误安全感。
- 如果前端写操作后不重新读取后端结果，仍可能短暂显示过期状态。
- 后端 Risk 与 Alert 之间的事务边界必须继续保持一致。

## Current Code Impact

- `backend/app/services/locations.py` — `KEEP`：保留定位校验、幂等、持久化及风险调用主链。
- `backend/app/services/risk.py` — `KEEP`：保留为真实模式的唯一风险引擎；坐标契约按 ADR-010 演进。
- `backend/app/services/alerts.py` — `KEEP`：保留 Alert 持久化和状态流转权威。
- `frontend/src/components/map/MapCanvas.vue` — `REFACTOR`：移除真实模式的风险决策和本地最终事件职责。
- `frontend/src/domain/risk/geofenceRisk.js` — `DEMO ONLY`：仅用于演示或单元测试。
- `frontend/src/views/child/ChildHome.vue` — `REFACTOR`：移除硬编码安全结论，读取后端 Safety View/Alert。
- `frontend/src/views/operator/OperatorDashboard.vue` — `REFACTOR`：真实模式不得混入 Mock 业务状态。
- `frontend/src/views/operator/AlertsPanel.vue` — `REFACTOR`：通过后端 accept/resolve API 更新事件。

GAP：当前尚无统一 Backend Safety View；家属端和运营端尚未完成后端权威状态接入。

## Verification

1. 同一 Trip 的相同 Location 只能由后端产生一组可追溯风险结果和 Alert。
2. 前端真实模式代码不再调用本地风险引擎决定最终状态。
3. 家属端和运营端对同一老人展示相同的 Trip、latest Location、RiskStatus 和 open Alert 数量。
4. 断开后端时，前端明确显示数据不可用，不显示“安全”。
5. 端到端测试覆盖定位上传、风险触发、家属读取、运营接单和结案。
