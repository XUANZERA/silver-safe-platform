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

接口时间字段统一使用 snake_case，例如 `created_at`、`started_at` 和
`ended_at`。后端以 UTC 存储并返回 RFC 3339 格式（例如
`2026-08-05T02:00:00Z`）；前端仅在展示时转换为用户所在时区。
