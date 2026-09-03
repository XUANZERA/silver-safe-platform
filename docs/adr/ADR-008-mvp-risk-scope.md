# ADR-008: MVP Risk Scope

## Status

Accepted

## Context

当前后端已经实现连续可靠位置点的电子围栏越界检测，以及老人主动 SOS。前端 Mock 运营数据还展示“定位长时间未更新”等类型，但后端没有相应规则、状态或后台检测任务。仓库也没有跌倒传感器、电池信息、路线模型或调度引擎。

在真实位置链路尚未完成前同时增加多种风险规则，会扩大误报、数据契约和测试范围，并分散对核心安全闭环的验证。

## Decision

Phase 1 safety-critical MVP 的必需风险范围限定为：

- `GEOFENCE_EXIT`
- `SOS`

Phase 1 暂不要求：

- Fall detection
- Low battery
- Route deviation
- Long stationary
- 复杂调度

`LOCATION_STALE` 作为明确的后续扩展候选，但不属于 Phase 1 必须交付范围。

AI 行程助手不属于 safety-critical 主链。AI 不得直接改变 RiskStatus、创建或解决 Alert，也不得成为 SOS 或围栏判断的必要依赖。

## Alternatives Considered

1. Phase 1 同时实现所有风险类型：数据来源和验证基础不足，拒绝。
2. 只做 SOS：无法验证已有 Location→geofence risk→Alert 链路。
3. 以 GEOFENCE_EXIT 和 SOS 为核心，其他风险后置：采用。

## Consequences

### Positive

- 复用并集中验证现有后端能力。
- 范围清晰，容易完成端到端现场测试。
- 避免用缺乏传感器和基线的数据制造伪风险结论。
- AI 故障不会影响安全主链。

### Negative

- Phase 1 不能检测跌倒、电量低、路线偏离或长时间静止。
- 位置中断只能在 UI 中表现为数据陈旧，除非后续实现 LOCATION_STALE。
- 比赛演示中的风险类型需要与真实后端范围保持一致。

### Risks

- UI 不得继续把 Mock 中的未实现风险类型展示为真实系统能力。
- 围栏规则的精度阈值和连续点数需要现场校准。
- SOS 在没有 active Trip 时是否允许，仍需产品决策。

## Current Code Impact

- `backend/app/services/risk.py` — `KEEP`：Phase 1 保留 GEOFENCE_EXIT 规则。
- `backend/app/services/sos.py` — `KEEP`：Phase 1 保留 SOS 主链。
- `backend/app/services/alerts.py` — `KEEP`：承载两类 MVP Alert。
- `backend/app/models/alert.py` — `KEEP`：当前类型约束与 MVP 范围一致。
- `frontend/src/mock/operator.js` — `DEMO ONLY`：未实现的风险类型不得冒充真实后端事件。
- `backend/app/services/deepseek.py` — `KEEP`：保持非 safety-critical 辅助能力。
- `LOCATION_STALE` — `LATER`：完成真实定位链路后单独设计。
- 跌倒、电量、偏航、静止和复杂调度 — `LATER`。

GAP：老人端尚未调用现有 SOS API；真实 Location Producer 尚未实现。

## Verification

1. 真实 Location 连续越界能够创建唯一、持久化的 GEOFENCE_EXIT Alert。
2. 老人端 SOS 能够创建或幂等返回后端 Alert。
3. 家属和运营可以读取这两类 Alert。
4. AI 服务不可用时，Location、Risk、Alert 和 SOS 仍正常工作。
5. 真实模式 UI 不显示尚未实现的风险检测能力。
