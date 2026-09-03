# ADR-003: MVP Infrastructure

## Status

Accepted

## Context

当前后端运行于 FastAPI，使用同步 SQLAlchemy ORM 和 SQLite。`backend/app/db/session.py::init_database` 通过 `Base.metadata.create_all` 建表，并在启动时写入演示数据。SQLite 已配置 foreign keys、busy timeout 和 WAL。

当前目标是比赛和小规模真实街区测试，而不是多区域、多实例生产平台。现阶段引入 PostgreSQL、Redis、消息队列或微服务会扩大部署和排障成本，但即将出现的 CRS、Safety View 查询和 ServicePoint 变更要求数据库 schema 具有可追踪的演进方式。

## Decision

MVP 继续使用：

- FastAPI
- SQLAlchemy
- SQLite
- 单体应用和现有同步业务事务

MVP 暂不引入：

- PostgreSQL
- Redis
- Message Queue
- WebSocket 基础设施
- 微服务拆分

数据库 schema 演进必须采用明确、可版本化、可审查、可重复执行的 migration 策略。具体 migration 工具在详细设计中选择，本 ADR 不新增技术选型。完成基线 migration 后，`create_all` 不再作为已部署数据库的 schema 升级机制。

## Alternatives Considered

1. 立即迁 PostgreSQL：当前规模下收益不足以覆盖迁移成本。
2. 引入 Redis 和消息队列处理定位：现有同步 Location→Risk→Alert 事务更简单且可验证。
3. 继续只使用 `create_all`：无法记录增量 schema 变化，拒绝。
4. 保持当前基础设施并补 migration 策略：采用。

## Consequences

### Positive

- 最大化复用当前后端和测试。
- 本地、演示和现场部署简单。
- Location、Risk 和 Alert 可以继续保持单事务一致性。
- schema 变化开始具备审计和重复部署基础。

### Negative

- SQLite 的并发写入和多实例能力有限。
- 单机数据库不适合高可用部署。
- migration 基线需要额外设计和验证。

### Risks

- 不能把 SQLite 文件放在多个应用实例间共享。
- `create_all`、seed 和正式 migration 的职责必须明确，避免重复或冲突。
- 保存真实个人位置数据前仍需评审备份、加密、保留期和访问审计。

## Current Code Impact

- `backend/app/main.py` — `KEEP`：保留单体 FastAPI 启动方式。
- `backend/app/db/session.py` — `REFACTOR`：保留 Engine/Session/SQLite 配置，明确初始化、seed 和 migration 边界。
- `backend/app/db/base.py` — `KEEP`：继续作为 SQLAlchemy metadata 根。
- `backend/app/models/*.py` — `KEEP`：继续使用现有 ORM 模型并通过 migration 演进。
- `backend/app/services/locations.py` — `KEEP`：继续同步事务处理。
- PostgreSQL — `LATER`：出现多实例、明显并发瓶颈或正式生产要求时重新评审。
- Redis — `LATER`：出现分布式限流、缓存或事件分发需求时重新评审。
- Message Queue — `LATER`：出现异步通知或复杂调度需求时重新评审。

GAP：仓库当前没有版本化 migration 目录或执行流程。

## Verification

1. 详细设计明确 migration 基线、执行顺序、失败恢复和 seed 边界。
2. 新环境可以从空数据库稳定建立当前 schema。
3. 已存在数据库可以通过版本化步骤升级，不依赖删除数据库。
4. Location→Risk→Alert 的现有事务测试继续通过。
5. 部署文档明确 SQLite 仅用于单实例 MVP。
