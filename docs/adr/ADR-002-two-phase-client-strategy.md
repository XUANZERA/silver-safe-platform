# ADR-002: Two-Phase Client Strategy

## Status

Accepted

## Context

当前仓库的客户端是 Vue 3/Vite 应用，已经包含老人端、家属端和运营端页面。现有后端 API 已覆盖 Trip、Location、Risk、Alert、SOS、认证和授权，但真实手机定位、家属地图/轨迹/Alert，以及运营端真实业务操作仍存在 GAP。

立即迁移微信小程序会同时引入客户端框架、地图、定位权限、会话和调试方式的变化，并在 Backend Contract 尚未经过真实街区测试前扩大不确定性。继续只做 H5 则无法体现已确定的后续小程序方向。

## Decision

采用两阶段客户端策略。

Phase 1：

```text
Elder   = Vue H5
Family  = Vue H5
Operator = Vue Web
```

Phase 1 使用当前仓库完成真实定位与真实业务闭环，验证并稳定 Trip、Location、Safety View、Alert 和 ServicePoint Backend Contract。

Phase 2：

```text
Elder   = WeChat Mini Program
Family  = WeChat Mini Program
Operator = Vue Web
```

Phase 2 复用 Phase 1 已验证的 Backend Contract。运营 Vue Web 保留，不随移动端迁移而重写。

## Alternatives Considered

1. 永久使用 Vue H5：短期最快，但没有固化小程序方向。
2. 立即迁移微信小程序：当前阶段新增变量过多，拒绝作为默认路径。
3. 老人端立即使用原生壳：仅在真机验证证明 H5 无法满足必要定位行为时重新评审。
4. 先 H5 验证、后小程序复用 API：采用。

## Consequences

### Positive

- 最大化复用当前 Vue 页面和现有后端。
- 可以先验证最关键的数据链路和业务规则。
- Phase 2 的工作重点可集中在客户端能力，而不是同时调试后端语义。
- 运营端投资不会因移动端迁移浪费。

### Negative

- 老人端和家属端会经历一次客户端迁移。
- Phase 1 UI 中部分代码不会直接进入 Phase 2。
- 必须严格隔离平台适配，避免把 H5 特性写入 Backend Contract。

### Risks

- 如果 Phase 1 直接在页面中调用浏览器 API，Phase 2 迁移成本仍会升高。
- 如果小程序认证和定位约束未提前纳入接口评审，Backend Contract 仍可能变化。
- H5 现场测试只能证明测试环境中的行为，不能替代小程序真机验证。

## Current Code Impact

- `frontend/src/views/elder/ElderHome.vue` — `REFACTOR`：Phase 1 接入真实定位和 SOS；Phase 2 由小程序页面替代。
- `frontend/src/views/child/ChildHome.vue` — `REFACTOR`：Phase 1 完成真实家属闭环；Phase 2 由小程序页面替代。
- `frontend/src/views/operator/OperatorDashboard.vue` — `KEEP`：作为长期运营 Web 入口，并在 Phase 1 接入真实后端。
- `frontend/src/services/api.js` — `EXTEND`：形成稳定 Web API facade；小程序使用等价 contract adapter。
- `backend/app/api/routes/locations.py` — `KEEP`：两阶段共用定位接口。
- `backend/app/api/routes/trips.py` — `EXTEND`：补齐客户端所需列表和历史查询。
- `backend/app/api/routes/alerts.py` — `KEEP`：两阶段共用 SOS 和 Alert workflow。

GAP：Phase 1 的 RealLocationProvider 尚未实现；Phase 2 小程序代码尚不存在。

## Verification

1. Phase 1 在两台手机和一个运营浏览器上完成端到端真实闭环。
2. Backend Contract 不包含浏览器或微信专属字段。
3. Provider、HTTP adapter 和地图实现具有明确平台边界。
4. Phase 2 客户端能够复用相同的 Trip、Location、Safety View 和 Alert API 语义。
5. 运营 Web 在 Phase 2 不需要因移动端迁移改变核心业务流程。
