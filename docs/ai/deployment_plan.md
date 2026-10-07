# Silver Safe Platform - Phase 5 公网部署执行方案

## 1. 基本信息

| 项目 | 内容 |
| :--- | :--- |
| **当前阶段** | Phase 5：Public Cloud Deployment（公网部署） |
| **基线 Commit** | `3194e47db767ca361a0ecacd58a84b32dce97ce8` (test: pass volunteer smoke test) |
| **执行目标** | 完成系统在公网 Linux 服务器的部署与配置，使微信小程序体验版真机可安全访问 |
| **约束条件** | 严格禁止修改业务逻辑；严格保持 Backend Authority 原则 |

---

## 2. 部署拓扑与边界

```text
微信真机小程序 (体验版)
         │
         ▼  (HTTPS / TLS 1.2+ / 端口 443)
公网 IP / 域名 (如 silver-test.yourdomain.com)
         │
         ▼
Caddy 2 反向代理 (Let's Encrypt 自动证书 / TLS 终结)
         │
         ▼  (HTTP / 本地回环 127.0.0.1:8000)
systemd (silver-safe-testing.service)
         │
         ▼
FastAPI 后端 (Uvicorn 单 Worker 进程，PID 独立，无并发锁)
         │
         ▼
SQLite 持久化 (/var/lib/silver-safe/testing.db, WAL 模式)
```

---

## 3. 部署资产清单

本项目已在 `deploy/` 与 `scripts/` 提供全套自动化部署与运维资产：

* `deploy/Caddyfile`: Caddy 2 反向代理与 TLS/HSTS 响应头配置。
* `deploy/silver-safe-testing.service`: systemd 守护进程托管配置（支持开机自启、崩溃重启、沙箱加固）。
* `deploy/setup_server.sh`: Linux 云服务器一键环境初始化与目录基线安装脚本。
* `scripts/reset_testing.py`: 测试数据库一键清空与 10 组账号/围栏数据重置工具。
* `scripts/verify_testing_readiness.py`: 8 项准入全自动预检脚本。

---

## 4. 详细执行流程（Step-by-Step）

### Step 4.1 云主机与网络准备
1. 申请一台 Ubuntu 22.04 LTS 云服务器（2C 2G/4G，固定公网 IP）。
2. 安全组入方向仅开放：`22` (SSH), `80` (HTTP), `443` (HTTPS)；严禁开放 `8000`。
3. 将二级域名（如 `silver-test.yourdomain.com`）解析至该公网 IP。

### Step 4.2 代码检出与运行环境安装
```bash
# 登录云服务器后执行
cd /opt
sudo git clone https://github.com/XUANZERA/silver-safe-platform.git silver-safe/app
cd /opt/silver-safe/app
sudo git checkout deploy/testing-environment

# 执行初始化脚本
chmod +x deploy/setup_server.sh
sudo ./deploy/setup_server.sh
```

### Step 4.3 环境变量注入
创建 `/etc/silver-safe/testing.env`：
```ini
APP_ENV=testing
DEBUG=false
DATABASE_URL=sqlite:////var/lib/silver-safe/testing.db
SECRET_KEY=silver-safe-prod-secret-testing-key-2026-secure-32chars
FIELD_ENCRYPTION_KEY=testing-encryption-key-for-elder-health-must-be-32bytes=
ACCESS_TOKEN_EXPIRE_MINUTES=1440
SECURE_COOKIES=true
TEST_ACCOUNT_PASSWORD=volunteer_test_pwd_123
LOCATION_STALE_AFTER_SECONDS=120
GEOFENCE_MAX_ACCURACY_METERS=100.0
GEOFENCE_TRIGGER_COUNT=3
```
锁定权限：
```bash
sudo chown root:silver-safe /etc/silver-safe/testing.env
sudo chmod 640 /etc/silver-safe/testing.env
```

### Step 4.4 启动服务与反向代理
```bash
# 启动 FastAPI 后端服务
sudo systemctl restart silver-safe-testing
sudo systemctl status silver-safe-testing --no-pager

# 启动 Caddy 自动申请 TLS 证书
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
```

### Step 4.5 数据库基线初始化与准入自检
```bash
cd /opt/silver-safe/app
sudo -u silver-safe bash -c '
    set -a; source /etc/silver-safe/testing.env; set +a
    /opt/silver-safe/app/venv/bin/python scripts/reset_testing.py
    /opt/silver-safe/app/venv/bin/python scripts/verify_testing_readiness.py
'
```
*必须确认输出包含 `[GO]`。*

### Step 4.6 微信小程序端接入
1. 登录微信公众平台后台：【开发管理】->【开发设置】->【服务器域名】的 `request合法域名` 添加 `https://silver-test.yourdomain.com`。
2. 更新 `miniprogram/config.js` 中的 `API_BASE_URL.testing` 为该 HTTPS 域名。
3. 在微信开发者工具上传代码，选定为【体验版】并绑定志愿者微信账号。

---

## 5. 验收准则（Go / No-Go Criteria）

- [ ] 公网终端通过 `curl -i https://silver-test.yourdomain.com/api/v1/health` 返回 200 与 `{"status":"ok"}`。
- [ ] 老人手机 A 登录 `elder_test_01` 成功开启定位守护，上报真实 GPS。
- [ ] 家属手机 B 登录 `family_test_01` 实时看到 `SAFE`（安全）与 `FRESH`（正常）。
- [ ] 跨家庭账号访问触发 404 或 403，无横向越权。
- [ ] 运行 `python scripts/reset_testing.py` 可在 10 秒内恢复基线数据。

