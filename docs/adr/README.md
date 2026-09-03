# Architecture Decision Records

本目录记录 `silver-safe-platform` 已确认的架构决策，作为后续需求分析、总体设计、详细设计、实施计划和代码修改的共同基线。

ADR 只描述架构决策及其约束，不把规划中的能力写成当前已经实现。文档中的 `GAP` 表示当前仓库尚未完成、需要在后续设计或实施阶段补齐的内容。

## Decision Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-backend-single-source-of-truth.md) | Backend Single Source of Truth | Accepted |
| [ADR-002](ADR-002-two-phase-client-strategy.md) | Two-Phase Client Strategy | Accepted |
| [ADR-003](ADR-003-mvp-infrastructure.md) | MVP Infrastructure | Accepted |
| [ADR-004](ADR-004-polling-first.md) | Polling First | Accepted |
| [ADR-005](ADR-005-mock-location-provider.md) | Mock Location Provider | Accepted |
| [ADR-006](ADR-006-derived-safety-view.md) | Derived Safety View | Accepted |
| [ADR-007](ADR-007-risk-vs-alert-state.md) | Risk State versus Alert State | Accepted |
| [ADR-008](ADR-008-mvp-risk-scope.md) | MVP Risk Scope | Accepted |
| [ADR-009](ADR-009-single-circular-geofence.md) | Single Circular Geofence | Accepted |
| [ADR-010](ADR-010-coordinate-system-contract.md) | Coordinate System Contract | Accepted (`ADR-TBD-001` remains TBD) |

## Status Definitions

- `Accepted`: 已批准，后续设计和实施必须遵守。
- `Proposed`: 已提出但尚未批准，不得作为已定方案实施。
- `TBD`: 证据不足或仍需产品、平台或现场验证后决定。

## Current Code Impact Labels

- `KEEP`: 保留当前职责和主要实现。
- `EXTEND`: 保留现有实现并增加能力。
- `REFACTOR`: 保留业务价值，但调整职责或依赖边界。
- `DEMO ONLY`: 仅允许用于演示、测试或离线开发，不进入真实业务权威链路。
- `LATER`: 当前阶段不实施，满足触发条件后再评审。

## Governance

1. ADR 编号和文件名一经引用不得复用。
2. 已接受 ADR 如需改变，应新增替代 ADR，并在旧 ADR 中标记被替代关系。
3. 需求、总体设计、详细设计和实施计划应引用相关 ADR 编号。
4. 代码实现与 ADR 不一致时，应先确认是实现缺陷还是架构决策需要修订。
