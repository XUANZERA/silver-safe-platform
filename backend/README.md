## 已提供接口

统一前缀：`/api/v1`

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/auth/login` | 登录并创建会话 |
| GET | `/auth/me` | 获取当前用户 |
| POST | `/auth/refresh` | 轮换刷新令牌 |
| POST | `/auth/logout` | 撤销当前会话 |
| GET | `/elders` | 按当前角色列出可访问的老人资料 |
| GET | `/elders/{elder_id}` | 获取老人详情 |
| GET | `/elders/{elder_id}/geofence` | 获取老人的圆形安全围栏 |
| POST | `/trips` | 创建出游任务 |
| GET | `/trips/{trip_id}` | 获取出游任务 |
| POST | `/trips/{trip_id}/start` | 开始出游 |
| POST | `/trips/{trip_id}/end` | 结束出游 |
| POST | `/trips/{trip_id}/cancel` | 取消尚未开始的出游 |
| GET | `/elders/{elder_id}/current-trip` | 获取老人当前未完成的出游 |
| POST | `/trips/{trip_id}/locations` | 幂等上传定位并检测连续越界 |
| GET | `/trips/{trip_id}/locations/latest` | 获取最新定位 |
| GET | `/trips/{trip_id}/locations` | 获取最近一段有序轨迹 |

完整请求和响应示例见 [`docs/auth-api.md`](../docs/auth-api.md)。

## 环境要求

- Python 3.12
- Node.js 20 或更高版本（仅前端需要）

## 后端启动

在仓库根目录执行：

虚拟环境用conda也可以

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

可访问：

- Swagger：<http://127.0.0.1:8000/api/v1/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

终端窗口必须保持运行。关闭终端后，访问接口会出现
`ERR_CONNECTION_REFUSED`。

## 演示账号

三个账号的密码均为 `demo123`。

| 用户名 | 角色 |
|---|---|
| `elder01` | 老人 |
| `family01` | 子女 |
| `operator01` | 运营人员 |

## 前端联调

本地后端地址：

```text
http://127.0.0.1:8000/api/v1
```

登录成功后，将响应中的 `access_token` 加入后续请求：

```http
Authorization: Bearer <access_token>
```

刷新令牌保存在 HttpOnly Cookie 中，前端不应读取或存入
`localStorage`。Axios 请求需要允许携带 Cookie：

```js
import axios from "axios"

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
  withCredentials: true,
})
```

默认允许以下前端开发地址：

- `http://localhost:5173`
- `http://127.0.0.1:5173`

### 定位模拟器适配

A 同学的地图模拟器继续使用前端字段 `recordedAt`，API 使用 snake_case。调用
上传接口时应在服务层完成映射，不要在地图组件内混用两套字段：

```js
const payload = {
  client_location_id: `sim-${tripId}-${point.id}`,
  latitude: point.latitude,
  longitude: point.longitude,
  speed_mps: null,
  accuracy_meters: 8,
  source: "simulation",
  recorded_at: new Date().toISOString(),
}

const mapPoint = {
  ...apiPoint,
  recordedAt: new Date(apiPoint.recorded_at).toLocaleString("zh-CN"),
}
```

演示围栏与前端模拟器统一使用 GCJ-02 广州坐标和 300 米半径。`simulation` 来源
只允许开发/演示环境；生产环境返回 `403 SIMULATION_NOT_ALLOWED`。真实 H5 定位
使用 `source: "h5"`，并将浏览器的 `coords.accuracy` 映射到
`accuracy_meters`。精度超过阈值的点可以保存和展示，但不会参与越界确认，避免
弱 GPS 信号造成误报。

轨迹接口返回最新 `limit` 个点，并按时间正序排列；可使用带时区的 `from_time`
和 `to_time` 过滤。定位响应带有 `Cache-Control: no-store`，前端不应持久缓存精确
轨迹。

## 运行测试

```powershell
python -m pip install -r backend\requirements-dev.txt
python -m pytest
python -m ruff check backend
python -m ruff format --check backend
```

## 环境配置

配置示例位于 [`.env.example`](../.env.example)。生产环境必须替换
`SECRET_KEY` 和 `HEALTH_INFO_ENCRYPTION_KEY`，两者至少 32 个字符且不能相同，
并通过 HTTPS 部署以启用安全 Cookie。生产环境启用 `DEBUG` 会导致启动失败。
健康信息在数据库中加密保存；老人及其绑定家属可读取，运营人员默认只能查看脱敏结果。

登录失败默认在 300 秒窗口内按账号限制 5 次、按来源 IP 限制 20 次，可通过
`LOGIN_FAILURE_*` 环境变量调整。默认不信任 `X-Real-IP`；只有后端确实位于可信
反向代理之后，才应通过 `TRUSTED_PROXY_NETWORKS` 配置代理网段。

定位上传默认每个出游 60 秒最多 120 个新点；幂等重试不重复保存，超过频率返回
`429 LOCATION_RATE_LIMITED` 和 `Retry-After`。生产接入真实老人数据前，仍需完成
HTTPS、定位数据静态加密、细粒度运营权限和集中审计建设。

接口时间字段统一使用 snake_case，例如 `created_at`、`started_at` 和
`ended_at`。后端以 UTC 存储并返回 RFC 3339 格式（例如
`2026-08-05T02:00:00Z`）；前端仅在展示时转换为用户所在时区。
