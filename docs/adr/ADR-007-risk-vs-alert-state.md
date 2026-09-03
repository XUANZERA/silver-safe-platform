# ADR-007: Risk State versus Alert State

## Status

Accepted

## Context

当前代码使用了两个容易混淆的概念：

- 前端围栏算法返回 `SAFE`、`PENDING`、`ALERT`。
- 后端 `Alert.status` 使用 `new`、`processing`、`resolved`。

前者描述老人当前物理风险，后者描述运营人员处理一个事件的进度。如果把二者合并，运营人员接单可能被误解为老人风险下降，老人回到围栏内也可能错误地自动关闭尚未完成处置的事件。

## Decision

RiskStatus 和 AlertStatus 是两个独立状态机。

RiskStatus：

```text
SAFE
PENDING
ALERT
```

它描述基于当前和近期 Location 得出的物理安全风险。

AlertStatus：

```text
NEW
PROCESSING
RESOLVED
```

它描述运营人员对一个已经生成的事件的处理进度。当前数据库值为小写 `new`、`processing`、`resolved`；对外枚举命名可以在 schema 中统一，但语义不得改变。

两个状态允许同时存在。例如老人已经回到围栏内：

```text
RiskStatus  = SAFE
AlertStatus = PROCESSING
```

客户端必须分别展示当前风险和事件处置状态，不得用其中一个覆盖另一个。

## Alternatives Considered

1. 使用一个统一 `status` 字段：拒绝，物理状态和工作流状态生命周期不同。
2. 老人回到围栏后自动将 Alert 标记 resolved：拒绝作为默认规则，处置完成仍需业务确认。
3. RiskStatus 与 AlertStatus 分离，并通过 Safety View 组合展示：采用。

## Consequences

### Positive

- 运营工作流不会改变物理风险事实。
- 老人恢复安全后仍能保留完整事件处置过程。
- UI 可以清楚表达“当前已安全，但事件仍处理中”。
- Risk 和 Alert 可以独立演进和测试。

### Negative

- 前端需要同时展示两个状态，文案设计更复杂。
- Safety View 必须定义两者同时存在时的展示优先级。
- 自动恢复、再次告警和结案之间需要明确业务规则。

### Risks

- 如果前端仍只有一个颜色或一个状态字段，可能再次混淆。
- 如果 Alert resolved 后老人仍处于 ALERT，后端可能需要重新生成或延续事件；规则尚需详细设计。
- PENDING 当前没有持久化字段，只能从 recent Locations 派生。

## Current Code Impact

- `backend/app/models/alert.py` — `KEEP`：保留 Alert workflow 状态机。
- `backend/app/services/alerts.py` — `KEEP`：保留 NEW→PROCESSING→RESOLVED 条件更新。
- `backend/app/services/risk.py` — `EXTEND`：明确返回或支持派生 RiskStatus。
- Backend Safety View — `EXTEND`：分别输出 `risk_status` 和 open Alert 信息。
- `frontend/src/domain/risk/geofenceRisk.js` — `DEMO ONLY`：其 RiskStatus 语义可用于测试参考，但不是权威结果。
- `frontend/src/views/child/ChildHome.vue` — `REFACTOR`：分别展示当前风险和事件状态。
- `frontend/src/views/operator/AlertsPanel.vue` — `REFACTOR`：只管理 AlertStatus，不修改 RiskStatus。

GAP：当前后端没有显式 RiskStatus response；当前页面尚未分别展示两类状态。

## Verification

1. 测试覆盖 `RiskStatus=SAFE + AlertStatus=PROCESSING`。
2. accept Alert 不会改变 RiskStatus。
3. 新 Location 导致 RiskStatus 恢复 SAFE 时，不会未经业务规则自动 resolved Alert。
4. UI 同时展示当前风险和事件处理进度，字段和文案不复用。
5. API schema 使用不同字段和不同枚举类型。
