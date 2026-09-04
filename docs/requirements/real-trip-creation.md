# REAL 模式老人端创建真实 Trip 功能需求与设计规范

## 1. 背景
当前 REAL 模式已经能够：
* 登录真实后端；
* 获取老人身份；
* 获取 current-trip；
* 展示已有 Trip；
* 启动已有 created Trip；
* active Trip 下触发 SOS；
* Family 查看 Safety View；
* Operator 接单与结案。

但是当前老人端缺少“创建真实 Trip”的 UI。
因此当：
> `GET current-trip` $\rightarrow$ `data = null`

老人只能看到：
* 暂无进行中的真实行程
* 请先设置真实目的地

但无法在页面上实际“设置真实目的地”。
因此核心业务链在：
> 无 Trip $\rightarrow$ 创建 Trip

这里断开。

---

## 2. 本功能目标
允许 Elder 用户在 REAL 模式：
* 输入真实目的地；
* 创建一条 backend Trip；
* 获取后端确认的 Trip；
* 再启动这条 Trip；
* 后续复用现有 Safety / SOS / Alert 流程。

**重点是：**
> Trip 一旦创建，后端立即成为唯一事实源。
> 前端不得创建一个“本地 Trip 对象”假装成功。

---

## 3. 本批次范围

### IN SCOPE
* 功能本批次输入目的地 ✅
* 创建真实 Trip ✅
* 展示 created Trip ✅
* 启动 created Trip ✅
* 创建/启动失败处理 ✅
* 防重复提交 ✅
* REAL/DEMO 隔离 ✅
* 创建成功后重新读取 backend ✅

### OUT OF SCOPE
* 功能本批次 GPS ❌
* RealLocationProvider ❌
* CRS 转换 ❌
* 地图选点 ❌
* 高德地点搜索 ❌
* 多日 itinerary ❌
* 路线规划 ❌
* Operator 创建 Trip ❌
* Family 创建 Trip ❌
* 微信小程序 ❌
* 紧急联系人 API ❌

> **说明：** 第一版目的地就是一个普通字符串。例如用户自己输入：`广州塔`，而不是系统现在就理解 Poi、经纬度、路线。

---

## 4. 用户角色
* **本功能创建者：** `Elder`
* **Family：** 只读取，不创建 Trip
* **Operator：** 本批次不创建 Trip

---

## 5. 用户故事

### US-TRIP-001
作为老人，当我尚未创建出游行程时，我希望输入我要去的地方并创建安心行程，以便系统开始为这次出游建立安全业务上下文。

### US-TRIP-002
作为老人，在行程成功创建后，我希望看到系统确认的目的地，然后点击“开始出游”。

### US-TRIP-003
如果后端不可用，我希望系统告诉我当前无法确认行程，而不是显示一个假的行程或自动切换到演示模式。

---

## 6. Functional Requirements

### FR-TRIP-001：识别无 Trip 状态
REAL 模式下：
> `GET /elders/{elder_id}/current-trip`

返回空时，页面必须展示真实空状态。
不得显示：
* `天坛公园`
* `暂无行程`（作为业务目的地）
* `Demo itinerary`

### FR-TRIP-002：目的地输入
无 Trip 时允许老人输入目的地。第一版只要求文本输入。例如：
> `广州塔`

必须：
1. `trim()` 之后验证。
2. 禁止：
   * `""`
   * `"   "`
   * `暂无行程`
   * `暂无真实行程`
3. trim 后长度不得超过现有 `max_length=200` contract。
4. 前端和 backend `TripCreateRequest` 必须执行相同的空值、保留值和长度校验；非法 backend 请求返回 `422 / VALIDATION_ERROR`。
5. 不得预填 `天坛`、`广州塔`、`永庆坊` 或其他真实感 Demo 目的地；这些值只能来自用户输入。

这是 request validation，不改变数据库 schema，也不新增 migration。普通中文、HTML-like 字符和其他现有 backend 允许的内容不得被额外禁止。

### FR-TRIP-003：创建 Trip
用户主动点击 **创建安心行程** 才允许发送创建请求。
预计调用：
> `POST /api/v1/trips`

实际 request schema 必须由实施者读取当前 backend schema 确认，不得猜字段。根据目前代码审计，核心字段是：
```json
{
  "destination": "广州塔"
}
```
但实施前仍必须检查实际 `TripCreateRequest`。

创建者身份只取自已认证的当前 Elder。即使请求 body 额外包含 `elder_id`，也不得替调用者为其他老人创建 Trip。

### FR-TRIP-004：创建成功以后端为准
创建接口成功后，不要仅做 `currentTrip = response.data`。
推荐执行流：
> `POST Trip` $\downarrow$ `backend success` $\downarrow$ `GET current-trip` $\downarrow$ 用重新读取的数据更新 UI

这样页面仍遵循 Backend Single Source of Truth。

### FR-TRIP-005：启动 Trip
只有后端确认存在：
> `status = created` + 有效 `destination`

才显示可用：**开始出游**。
点击后调用现有：
> `POST /api/v1/trips/{trip_id}/start`

成功后再次：
> `GET /elders/{elder_id}/current-trip`

确认：
> `status = active`

### FR-TRIP-006：防止重复提交
创建过程中：
> **创建安心行程** $\rightarrow$ `disabled`

同时 handler 必须有：
```ts
if (creatingTrip.value) return
```
不能只依赖按钮 `disabled`。Start 同理。

### FR-TRIP-007：后端空结果不得 fallback Demo
* REAL：`backend empty` $\rightarrow$ `empty`
* REAL：`backend failure` $\rightarrow$ `unavailable`

绝对不能：
> `backend failure` $\rightarrow$ 天坛 Demo

### FR-TRIP-008：结构化 API 错误
frontend API layer 的最小 `ApiError extends Error` 必须保留：

* backend message；
* HTTP `status`；
* backend error `code`；
* `hasResponse`。

fetch 的 network/CORS rejection 使用 `hasResponse = false`；收到 HTTP error response 使用 `hasResponse = true`。现有 fetch、cookie、401 refresh single-flight、每个原请求最多重试一次及 logout cleanup 语义不得改变。

---

## 7. Business Rules

### BR-TRIP-001
UI placeholder 永远不是业务数据。以下值禁止作为真实 destination：
* `暂无行程`
* `暂无真实行程`

### BR-TRIP-002
无 backend Trip：
* 不能直接 Start

### BR-TRIP-003
已有 created Trip：
* 不能再展示创建入口，优先处理已有 Trip。

### BR-TRIP-004
已有 active Trip：
* 不能再创建第二条当前 Trip，页面直接展示活动行程。

### BR-TRIP-005
REAL 与 DEMO 必须严格隔离。
* Demo 可以继续：`天坛公园慢游`
* REAL 不可以。

---

## 8. 异常要求（重点）

### 创建请求明确失败
例如最终收到 `400`、`401`、`403`、`422`，不得显示“创建成功”，可以保留并展示 backend message。`409`、`5xx` 和 network failure 按下述对账规则处理。

### `409` / 状态冲突
可能发生：
* 设备 A 创建 Trip
* 设备 B 页面仍认为没有 Trip
* 设备 B 点击创建

如果 backend 返回冲突：不要本地制造结果。应该：
> `409` $\downarrow$ 重新 `GET current-trip` $\downarrow$ 展示后端真实状态

### `CREATE_UNKNOWN`
network failure、`5xx`、POST 成功但 authoritative GET 失败，以及 POST 成功但 authoritative GET 暂时返回 `data = null`，都不得自动重新 POST。例如：
> `POST` 已经到达 server $\rightarrow$ server 创建成功 $\rightarrow$ `response` 在网络途中丢失

前端可以执行一次 `GET current-trip` 对账，但不能根据 POST response 构造本地 Trip：

* 对账 GET 返回 Trip：使用该 backend Trip；
* 对账 GET 失败或返回 `null`：进入 `CREATE_UNKNOWN`；
* `CREATE_UNKNOWN` 只显示“行程请求结果暂时无法确认”和“刷新行程状态”；
* 用户手动刷新返回 Trip：使用 backend Trip；
* 用户手动刷新成功且明确 `data = null`：恢复 `CREATE_READY`；
* 用户手动刷新失败：保持 `CREATE_UNKNOWN`。

任何上述路径都不得自动重新 `POST /trips`，不得显示 local fake Trip，也不得提示用户“再次创建”。

---

## 9. 验收标准
最重要的验收链：

1. `REAL Login`
2. `current-trip = null` $\rightarrow$ 显示真实空状态
3. 输入 `广州塔`
4. 点击 **创建安心行程** $\rightarrow$ `POST /trips`
5. `GET current-trip` $\rightarrow$ 显示：`广州塔` / `待出发`
6. 点击 **开始出游** $\rightarrow$ `POST /trips/{id}/start`
7. `GET current-trip` $\rightarrow$ `status = active`

创建和 Start 的按钮与 handler 都必须有同步 pending guard。POST 的 response 不是最终页面事实；创建和 Start 均由随后的 authoritative GET 决定。两个独立数据库 session 的并发回归还必须验证：并发 Create 最终最多一个 unfinished Trip，并发 Start 只有一个状态转换成功且最终为 `active`。

**Network 中不得出现：**
* `destination = 暂无行程`
* `destination = 暂无真实行程`
* `destination = 天坛公园慢游`

本需求遵循 [ADR-001 Backend Single Source of Truth](../adr/ADR-001-backend-single-source-of-truth.md) 与 [ADR-004 Polling First](../adr/ADR-004-polling-first.md)；ADR-005 与 ADR-010 所涉及的 Location/GPS/CRS 不在本批次范围。
