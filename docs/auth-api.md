# 登录模块接口说明

统一前缀：`/api/v1`

## 前端调用约定

- 登录成功后，将响应中的 `access_token` 放入后续请求头：
  `Authorization: Bearer <access_token>`。
- 刷新令牌只保存在 `silver_safe_refresh` HttpOnly Cookie 中，前端不可读取。
- 登录、刷新和退出请求统一启用 Axios `withCredentials: true`。
- 本地前端允许使用 `http://localhost:5173` 或 `http://127.0.0.1:5173`。

## POST `/api/v1/auth/login`

请求：

```json
{
  "username": "elder01",
  "password": "demo123"
}
```

成功响应：

```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 7200,
    "refresh_expires_in": 2592000,
    "user": {
      "id": 1,
      "username": "elder01",
      "role": "elder",
      "phone": "13800000001"
    }
  },
  "message": "登录成功"
}
```

演示账号的统一密码为 `demo123`：

- `elder01`：老人
- `family01`：子女
- `operator01`：运营人员

## GET `/api/v1/auth/me`

需要 Bearer Token，返回当前登录用户。

## POST `/api/v1/auth/refresh`

无请求体。浏览器携带刷新 Cookie，后端轮换刷新令牌并返回新的访问令牌。

```js
axios.post("/api/v1/auth/refresh", null, {
  withCredentials: true,
})
```

## POST `/api/v1/auth/logout`

需要 Bearer Token 和刷新 Cookie。后端撤销当前登录会话并清除 Cookie。

```js
axios.post("/api/v1/auth/logout", null, {
  withCredentials: true,
})
```

## 常用错误码

- `INVALID_CREDENTIALS`：用户名或密码错误。
- `UNAUTHORIZED`：没有提供访问令牌。
- `TOKEN_EXPIRED`：访问令牌已过期。
- `INVALID_TOKEN`：访问令牌无效。
- `INVALID_REFRESH_TOKEN`：刷新 Cookie 缺失或无效。
- `REFRESH_TOKEN_REUSED`：旧刷新令牌被再次使用，会话已撤销。
- `SESSION_REVOKED`：登录会话已撤销或过期。
