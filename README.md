# 银发独游协同平台

当前 `starreslzx` 分支提供可独立运行的后端基础设施和安全认证模块，供前端优先完成
登录、身份恢复、令牌刷新、退出登录与角色跳转。

## 已提供接口

统一前缀：`/api/v1`

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/auth/login` | 登录并创建会话 |
| GET | `/auth/me` | 获取当前用户 |
| POST | `/auth/refresh` | 轮换刷新令牌 |
| POST | `/auth/logout` | 撤销当前会话 |

完整请求和响应示例见 [`docs/auth-api.md`](docs/auth-api.md)。

## 环境要求

- Python 3.12
- Node.js 20 或更高版本（仅前端需要）

Docker 不是当前登录联调的必要条件。

## 后端启动

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

出现以下提示表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete
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

演示密码仅用于本地开发，不得用于生产环境。

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

认证测试覆盖登录、密码哈希、JWT、身份恢复、刷新令牌轮换、旧令牌复用撤销、
退出登录、HttpOnly Cookie、生产密钥检查和前端 CORS。

## 环境配置

配置示例位于 [`.env.example`](.env.example)。生产环境必须替换
`SECRET_KEY`，并通过 HTTPS 部署以启用安全 Cookie。

