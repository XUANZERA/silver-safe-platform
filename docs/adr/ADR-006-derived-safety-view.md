# ADR-006: Derived Safety View

## Status

Accepted

## Context

当前后端已经持久化 Trip、Location 和 Alert，但没有独立 SafetyState 表。前端因此自行推断或硬编码安全状态：

- `frontend/src/views/elder/ElderHome.vue` 根据 active Trip 显示“定位正常”。
- `frontend/src/views/child/ChildHome.vue` 固定显示“安全区域正常”。
- `frontend/src/views/operator/OperatorDashboard.vue` 从本地 Alert 和 Mock Trip 推导老人状态。

这些状态不是后端权威结果。当前比赛和小规模真实测试的数据量不足以证明需要额外的持久化快照表，引入 SafetyState 表还会产生与 Location/Alert 同步、重建和并发更新问题。

## Decision

Phase 1 不建立持久化 SafetyState 或 SafetySnapshot 表。

后端提供统一的 Safety View/Projection，从以下已持久化事实派生：

- Current Trip
- Latest Location
- Recent reliable Locations
- Open Alerts
- Current calculation time

Safety View 至少包含：

```text
trip_status
location_health
risk_status
open_alert_count
latest_location
calculated_at
```

Safety View 是查询模型，不是新的业务事实来源。所有客户端使用同一后端 projection，不得各自重新组合最终安全状态。

## Alternatives Considered

1. 继续由各前端页面推导：拒绝，会持续产生状态漂移。
2. 立即新增 SafetyState 表：当前规模下增加同步和修复复杂度，暂不采用。
3. 直接只展示 open Alerts：不足以表达没有位置、位置过期或 Trip 未开始。
4. 从现有事实派生统一 Safety View：采用。

## Consequences

### Positive

- 不引入新的持久化一致性问题。
- 可以复用现有 Trip、Location 和 Alert 表及索引。
- 家属和运营端得到相同、可解释的状态。
- 后续如需 Snapshot，可以用已有事实重建和验证。

### Negative

- 每次读取需要查询并组合多个事实。
- 历史 Safety View 不会自动保存。
- PENDING 等状态需要从 recent Locations 计算，而不是直接读取字段。

### Risks

- projection 规则如果散落在多个 route，仍会产生重复逻辑。
- `calculated_at`、位置新鲜度阈值和可靠精度阈值必须统一来自后端配置。
- open Alert 与当前物理风险必须按 ADR-007 分开表达。

## Current Code Impact

- `backend/app/models/trip.py` — `KEEP`：作为 trip status 来源。
- `backend/app/models/location.py` — `KEEP`：作为 latest/recent Location 来源。
- `backend/app/models/alert.py` — `KEEP`：作为 open Alert 来源。
- `backend/app/services/locations.py` — `KEEP`：复用 latest/recent 查询能力。
- `backend/app/services/risk.py` — `EXTEND`：提供可复用的当前风险判定，不创建第二套规则。
- Backend Safety Query/Application Service — `EXTEND`：后续新增统一 projection。
- `frontend/src/views/child/ChildHome.vue` — `REFACTOR`：显示后端 Safety View。
- `frontend/src/views/operator/OperatorDashboard.vue` — `REFACTOR`：显示同一 Safety View。
- 持久化 SafetyState/SafetySnapshot — `LATER`：规模或历史查询需求出现后重新评审。

GAP：当前没有 Safety View schema、service 或 API endpoint。

## Verification

1. 对同一老人、同一时刻，家属和运营读取到相同 Safety View。
2. 没有 Location、Location 过期、低精度 Location 和 open Alert 均有明确结果。
3. Safety View 可完全由数据库中的 Trip、Location 和 Alert 重算。
4. 前端删除硬编码“安全”和基于 Trip 推断“定位正常”的逻辑。
5. 测试覆盖不同事实组合及优先级。
