# ADR-004: Polling First

## Status

Accepted

## Context

家属端需要查看 active Trip、latest Location、track 和 Alert；运营端需要查看 active Trip、位置和 Alert 队列。当前后端已经提供 latest、track 和 Alert 查询，但没有 WebSocket、SSE 或消息分发基础设施。当前规模是比赛和小规模真实测试。

现有前端只在页面挂载或手动刷新时读取部分数据，尚未形成持续更新。立即引入长连接会增加认证、重连、连接管理、移动端兼容和调试复杂度。

## Decision

Phase 1 使用 HTTP Polling 获取家属和运营所需的动态状态，不使用 WebSocket。

轮询周期必须是可配置参数，由现场测试根据定位上传频率、页面可见性、网络情况和后端负载调整。本 ADR 不规定固定 interval。

客户端必须：

- 只在相关页面处于可见/活动状态时正常轮询。
- 页面进入后台时暂停或降低频率。
- 网络失败时退避，避免无界重试。
- 防止同一资源出现重叠请求。
- 写操作成功后立即重新读取后端权威状态。

## Alternatives Considered

1. 手动刷新：不足以支持家属监控和运营告警队列。
2. SSE：单向更新适合未来优化，但当前不是必要条件。
3. WebSocket：当前没有双向实时协议需求，复杂度过高。
4. 可配置 Polling：采用。

## Consequences

### Positive

- 直接复用现有 REST API、认证和权限模型。
- 浏览器和未来客户端都容易实现和调试。
- 不引入新的基础设施。
- 现场可快速调整刷新策略。

### Negative

- 更新延迟受轮询周期影响。
- 相同数据可能被重复读取。
- 页面数量或用户数上升后会增加请求量。

### Risks

- 不可把“本次请求失败”解释成“老人安全”。
- 过短周期可能增加 SQLite 和审计日志压力。
- 多个组件各自轮询同一资源会产生重复请求，应由页面级协调器统一管理。

## Current Code Impact

- `frontend/src/views/child/ChildHome.vue` — `REFACTOR`：增加可配置、可停止的页面级轮询。
- `frontend/src/views/operator/OperatorDashboard.vue` — `REFACTOR`：统一轮询 Alert、active Trip 和必要的位置摘要。
- `frontend/src/services/api.js` — `EXTEND`：补齐相关 GET API。
- `backend/app/api/routes/locations.py` — `KEEP`：复用 latest/track 查询。
- `backend/app/api/routes/alerts.py` — `KEEP`：复用 Alert list/detail 查询。
- SSE — `LATER`：轮询负载或延迟不再满足需求时评审。
- WebSocket — `LATER`：出现明确双向实时协作需求时评审。

GAP：当前没有通用 polling coordinator；家属端只在挂载和手动刷新时读取 latest Location，运营端只在挂载时读取数据。

## Verification

1. 页面可见时能持续获取后端最新 Location 和 Alert。
2. 页面离开或不可见后不再保持正常频率请求。
3. 网络失败会退避并显示数据陈旧/不可用状态。
4. accept/resolve 后 UI 通过重新查询得到后端最终状态。
5. interval 可在不修改业务逻辑的情况下调整，并通过现场测试确定。
