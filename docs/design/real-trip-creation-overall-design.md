# REAL 模式老人端创建真实 Trip 架构与设计规范

## 1. 架构位置
这个功能非常小，不需要新架构。继续沿用：

```text
┌───────────────────────────┐
│       ElderHome.vue       │
│                           │
│ destination input         │
│ create button             │
│ start button              │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│       frontend API        │
│                           │
│ tripApi.create()          │
│ tripApi.start()           │
│ elderApi.currentTrip()    │
└─────────────┬─────────────┘
              │ HTTP
              ▼
┌───────────────────────────┐
│          FastAPI          │
│                           │
│ POST /trips               │
│ POST /trips/{id}/start    │
│ GET current-trip          │
└─────────────┬─────────────┘
              │
              ▼
        SQLAlchemy / DB
```

不增加新的 Backend Service。
`frontend/src/services/tripCreation.js` 只承担 Trip create/start 编排，不扩展成通用 command framework，也不使用 store。backend 只修改 `TripCreateRequest` 的 request validation，不修改 database model/schema，不新增 migration。

---

## 2. 核心设计原则

### 原则一
将创建命令（`Command`）和查询（`Query`）分开理解。
* 创建：`POST /trips`
* 确认：`GET current-trip`

所以前端使用 **`write` $\rightarrow$ `refetch`** 模式。POST response 只表示命令响应，只有 authoritative `GET current-trip` 可以更新页面 Trip truth。

### 原则二
不要维护两份 Trip truth。禁止：
* `frontend localTrip` + `backend Trip`

只保留：
* `backend currentTrip`

前端临时状态只能有：
* `destinationInput`
* `creatingTrip`
* `startingTrip`
* `createState = CREATE_READY | CREATE_UNKNOWN`
* presentation error

这些是 UI 状态，不是业务状态。

---

## 3. 页面状态设计
建议将 `ElderHome` 看成以下状态机：

```text
              load
               │
        ┌──────┴───────┐
        ▼              ▼
    unavailable      backend OK
                       │
              ┌────────┴────────┐
              ▼                 ▼
          trip = null         Trip
              │                 │
        CREATE_READY       ┌─────┴─────┐
                           ▼           ▼
                        created      active
                           │           │
                       START_READY   TRAVELLING
```

创建命令的结果不确定时，从 `CREATING` 进入 `CREATE_UNKNOWN`。该状态只允许用户手动触发 `GET current-trip`：GET Trip 进入对应 backend 状态，GET 成功且 `data = null` 回到 `CREATE_READY`，GET 失败保持 `CREATE_UNKNOWN`。

再叠加两个 transient state：
* `CREATING`
* `STARTING`

---

## 4. UI 总体方案
不建议重新设计整个老人首页，你截图现在已经比较清楚。建议保留 **今日出游计划** 这张卡。

### 无 Trip 时
卡片变为：
> **今日出游计划**
> 暂无进行中的真实行程
> `[ 设置目的地 ]`

点击 **设置目的地** 打开一个 Vant Popup/Dialog：
> **创建安心行程**
> 目的地
> `[ 请输入目的地           ]`
> `[取消] [创建安心行程]`

输入框初始值必须为空，不预填 `天坛`、`广州塔` 或 `永庆坊`。输入 trim 后不能为空、不能等于两个保留 sentinel，且最大长度为 200。

*为什么推荐弹窗而不是首页一直放 input？*
* 老人首页保持干净；
* 不让键盘和输入框占据主界面；
* 创建行为是一次性动作；
* 当前项目已经使用 Vant Dialog/Popup。

### 创建成功时
> **今日出游计划**
> backend GET 返回的目的地
> 状态：待出发
> `[开始出游]`

### Active 时
> **当前状态**
> 出游中
> 正在前往：backend GET 返回的目的地

---

## 5. 时序设计

### 创建行程
```text
Elder
  │
  │ 输入 destination
  ▼
ElderHome
  │
  │ validate
  ▼
tripApi.create()
  │
  │ POST /trips
  ▼
Backend
  │
  │ create
  ▼
Database
  │
  │ success
  ▼
Frontend
  │
  │ GET current-trip
  ▼
Backend
  │
  ▼
Frontend renders CREATED trip
```

只有 POST 成功且 GET 返回 Trip，才能关闭 popup、清空输入并显示创建成功。`409`、network failure 和 `5xx` 必须执行一次 GET 对账；network/5xx 对账为 null，或 POST 成功后的 GET 失败/null，均进入 `CREATE_UNKNOWN`，绝不自动重新 POST。`409` 对账只能采用 backend Trip，不能制造 local Trip。

### 开始行程
```text
Elder
  │
  │ Start
  ▼
tripApi.start(id)
  │
  ▼
Backend
  │
  │ created → active
  ▼
Frontend
  │
  │ GET current-trip
  ▼
render ACTIVE
```

Start 仅允许 `status = created` 且 destination 有效的 backend Trip。Start POST 有同步 pending guard；成功、`409`、network failure 和 `5xx` 后都 GET `current-trip`，页面不采用 Start POST response。

## 6. API error boundary

现有 fetch client 保持 cookie、401 refresh single-flight、每个原请求 retry once、refresh failure 与 logout cleanup 语义。最小 `ApiError extends Error` 暴露 `message/status/code/hasResponse`；network/CORS rejection 的 `hasResponse = false`，HTTP error 的 `hasResponse = true`。

本设计遵循 [ADR-001 Backend Single Source of Truth](../adr/ADR-001-backend-single-source-of-truth.md) 与 [ADR-004 Polling First](../adr/ADR-004-polling-first.md)。[ADR-005 Mock Location Provider](../adr/ADR-005-mock-location-provider.md) 和 [ADR-010 Coordinate System Contract](../adr/ADR-010-coordinate-system-contract.md) 的 Location/GPS/CRS 决策不在本批次实现范围。
