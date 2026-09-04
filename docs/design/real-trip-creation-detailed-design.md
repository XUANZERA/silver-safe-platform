# REAL 模式老人端创建真实 Trip 工程实现与测试规范

## 1. 预计改动文件
优先控制在：
* `frontend/src/views/elder/ElderHome.vue`
* `frontend/src/services/api.js`（增加最小结构化 `ApiError`，不更换 fetch）
* `frontend/src/services/tripCreation.js`（新增薄的 create/start orchestration）
* `frontend/tests/tripCreation.test.js`
* `backend/app/schemas/trip.py`（只修改 request validation）
* `backend/tests/test_trips.py`

后端不修改 Trip model/database schema，不新增 migration，也不重构现有事务。

---

## 2. `tripCreation.js`
建议不要再把 Trip 逻辑塞进 `modeBoundary.js`。`modeBoundary.js` 管的是 `REAL / DEMO boundary`，不是 Trip domain。

可以新增：
```ts
export function normalizeDestination(value) {
  return String(value ?? '').trim()
}

export function isValidDestination(value) {
  const destination = normalizeDestination(value)

  return Boolean(
    destination &&
    destination.length <= 200 &&
    destination !== '暂无行程' &&
    destination !== '暂无真实行程'
  )
}
```
> **注意：** 最大 200 字来自 backend 已有 `max_length=200` contract。不要擅自增加最少 2 字、字符类型、HTML-like 字符等额外规则。

backend `TripCreateRequest` 在 field constraints 之前 trim，再拒绝 empty、`暂无行程`、`暂无真实行程`；因此 trim 后 200 字有效、201 字无效。这只是 request validation。Vant field 初始值为空，`maxlength=200`，不预填 `天坛`、`广州塔` 或 `永庆坊`。

可以再有一个非常薄的 orchestration：
```ts
export async function createTripAndRefresh({
  destination,
  createTrip,
  refreshTrip,
}) {
  ...
}
```
目的不是搞“架构模式”，而是让这几个行为可测试：
* `create success` $\rightarrow$ `refresh`
* `create failure` $\rightarrow$ `no fake success`
* `409` $\rightarrow$ `refresh`
* `network/5xx uncertain` $\rightarrow$ `refresh first`
* `start success/409/network/5xx` $\rightarrow$ `refresh`

orchestration 必须在第一个 `await` 前检查并设置 pending，以抵御同步双击。它返回明确 result type（包括 `CREATE_CONFIRMED`、`CREATE_RECONCILED`、`CREATE_REJECTED`、`CREATE_UNKNOWN`），但 Trip 值只能取自 `refreshTrip`，不能取自 POST response。

---

## 3. `ElderHome` 状态
新增的前端临时状态：
```ts
const destinationInput = ref('')
const createTripVisible = ref(false)
const creatingTrip = ref(false)
const startingTrip = ref(false)
const createState = ref(CREATE_STATE.READY)
const refreshingUnknownTrip = ref(false)
```

不要新增：
```ts
const localTrip = ...
```
Trip 仍然使用当前的 `currentTrip`。

---

## 4. 创建入口显示条件
概念上：
> `realMode && tripDataAvailable && currentTrip === null && createState !== CREATE_UNKNOWN`

才显示：**设置目的地 / 创建安心行程**。

如果 `backend unavailable`，不能显示可以创建的正常表单，而应该提示：
> `无法获取真实行程状态，请稍后重试。`

因为在无法确认是否已经存在 Trip 的情况下继续 `POST` 有重复创建风险。这个设计非常重要。

`CREATE_UNKNOWN` 显示“行程请求结果暂时无法确认”，只提供“刷新行程状态”；不提供创建按钮、失败重试文案或自动 POST。

---

## 5. 创建 Handler
实际 API 已确认：`tripApi.create(destination)` 序列化为 `{ "destination": destination }`；身份来自认证用户，不发送或信任 `elder_id`。

Handler 与 orchestration 均有同步 pending guard。创建按钮同时 disabled。POST 只调用一次：

* POST 201 后 GET Trip：关闭 popup、清空输入、显示成功；
* POST 201 后 GET 失败/null：`CREATE_UNKNOWN`；
* POST 409：GET 对账，backend existing Trip wins；
* POST network/5xx：GET 对账，若没有取得 Trip 仍为 `CREATE_UNKNOWN`；
* POST 400/401/403/422：`CREATE_REJECTED`，保留 backend message。

手动刷新 unknown 时，GET Trip 使用 backend Trip 并关闭 popup；GET 明确 null 恢复 `CREATE_READY`；GET 失败保持 unknown。任何分支都不自动再次 POST。

---

## 6. Start Handler
必须满足：
> `currentTrip.id` + valid real destination + `currentTrip.status === "created"`

才执行：
> `tripApi.start(currentTrip.id)`

然后：
> `await loadCurrentTrip()`

Start handler 和 orchestration 都使用同步 `startingTrip` guard。POST success、409、network failure、5xx 均 GET 对账，最终页面状态只取 GET，不采用 Start POST response。

---

## 7. Error Model
frontend API layer 使用最小 `ApiError extends Error`，保留 `message/status/code/hasResponse`。network/CORS fetch rejection 的 `hasResponse = false`；HTTP error response 的 `hasResponse = true`。不得改变 cookie、401 refresh single-flight、retry once、refresh failure 或 logout cleanup。

UI 至少区分四类：

### 1. Validation Error
* 提示：`请输入真实目的地`

### 2. Backend Rejection
* 例如：当前已有行程、无权限、参数错误。
* 提示：显示后端可安全展示的信息。

### 3. Backend Unavailable
* network failure 或 `5xx` 先 GET 对账；无法确认时进入 `CREATE_UNKNOWN`。
* 不能显示：`创建失败，您可以再创建一次`（因为第一次 `POST` 可能已经成功）。

### 4. Confirmation Failure
* 提示：`行程请求结果暂时无法确认`
* 只提供：**刷新行程状态** 按钮，不自动重试 `POST`。

---

## 8. Accessibility / Elder UX
* 按钮文字不要写 `Submit`、`Create`、`Confirm`，而是明确：
  * **设置目的地**
  * **创建安心行程**
  * **开始出游**
* 错误信息也不要只是 `Error 422`，而应该提示 `目的地不能为空`。但详细技术错误可以进 Console，严禁暴露 token。

---

## 9. 自动测试设计
至少应该包含以下测试用例（Test Cases）：

* **TC-TRIP-001**：`REAL + current-trip null` $\rightarrow$ 允许创建 Trip。
* **TC-TRIP-002**：`destination = ""` 或 `"   "` $\rightarrow$ `0 POST`。
* **TC-TRIP-003**：两个 reserved sentinel $\rightarrow$ frontend `0 POST`、backend `422`。
* **TC-TRIP-004**：trim 后有效 destination $\rightarrow$ `POST once`，之后 GET，GET 为最终 truth。
* **TC-TRIP-005**：快速双击创建 $\rightarrow$ `POST once`。
* **TC-TRIP-006**：`POST 500` $\rightarrow$ GET 对账，无第二次 POST，无 fake success。
* **TC-TRIP-007**：`POST 409` $\rightarrow$ GET，backend existing Trip wins。
* **TC-TRIP-008**：`created/active Trip` 已存在 $\rightarrow$ 不展示创建表单。
* **TC-TRIP-009**：Start 仅 created 可用；双击只 POST 一次；随后 GET authoritative result。
* **TC-TRIP-010**：`DEMO` 模式 $\rightarrow$ 原行为不回归且不调用真实 POST。
* **TC-TRIP-011**：POST success + GET failure $\rightarrow$ `CREATE_UNKNOWN`。
* **TC-TRIP-012**：network error + GET null $\rightarrow$ unknown 且不自动重试。
* **TC-TRIP-013**：unknown 手动刷新 null $\rightarrow$ `CREATE_READY`。
* **TC-TRIP-014**：POST destination A、GET destination B $\rightarrow$ 使用 B。

backend validation 还覆盖 empty、spaces、两个保留值、valid、200/201 字符，并验证 body 注入 `elder_id` 不能改变 owner。真实两个 session 的 regression test 验证 concurrent Create 最多一个 unfinished Trip，以及 concurrent Start 只有一个 transition 成功且最终 `active`。

---

## 10. 人工验收
最终通过 F12 亲自验证：
1. `GET current-trip` $\rightarrow$ `200`，`data = null`。
2. 输入 `永庆坊`，点击创建。
3. Network 观察：
   * `POST /api/v1/trips` $\rightarrow$ `201`
   * 随后必须紧跟：`GET /current-trip` $\rightarrow$ `200`
4. 页面显示：`永庆坊` / `待出发`。
5. 点击开始出游：
   * `POST /api/v1/trips/{id}/start` $\rightarrow$ `200`
   * 随后再次触发 `GET current-trip`。
6. 页面最终显示：`出游中` / `正在前往：永庆坊`。

> 到这里，Trip 业务才算真正形成完美闭环。

本设计遵循 [ADR-001 Backend Single Source of Truth](../adr/ADR-001-backend-single-source-of-truth.md) 与 [ADR-004 Polling First](../adr/ADR-004-polling-first.md)。ADR-005/ADR-010 的 Location、GPS、CRS 内容保持不变且不在本批次实现范围。
