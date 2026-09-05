# 银龄安全系统（Silver Safe Platform）
# Phase 4 外部志愿者测试部署详细设计说明书

## 1. 云服务器系统准备规范

### 1.1 硬件选型与系统基线
* **云厂商推荐**：阿里云/腾讯云轻量应用服务器（Lighthouse）或华为云耀云服务器。
* **推荐规格**：2 核 CPU / 2GB 或 4GB 内存 / 50GB SSD 磁盘 / 峰值带宽 3~5Mbps。
* **操作系统**：Ubuntu 22.04 LTS x86_64 或 Ubuntu 24.04 LTS。
* **公网 IP**：需分配固定公网 IPv4 地址。

### 1.2 系统用户与目录权限规范
严禁用 `root` 账户直接运行 Python 进程。
```bash
# 1. 创建专用低权限系统用户
sudo useradd -r -s /bin/false -d /opt/silver-safe silver-safe

# 2. 创建核心工程与配置目录
sudo mkdir -p /opt/silver-safe/app        # 代码与虚拟环境目录
sudo mkdir -p /var/lib/silver-safe        # 数据库与运行时数据目录
sudo mkdir -p /etc/silver-safe            # 生产/测试环境变量目录
sudo mkdir -p /var/log/silver-safe        # 日志归档目录

# 3. 赋予权限
sudo chown -R silver-safe:silver-safe /opt/silver-safe
sudo chown -R silver-safe:silver-safe /var/lib/silver-safe
sudo chown -R silver-safe:silver-safe /var/log/silver-safe
sudo chmod 700 /var/lib/silver-safe
```

---

## 2. 环境变量与配置文件模板

### 2.1 测试环境变量文件：`/etc/silver-safe/testing.env`
```ini
APP_ENV=testing
DATABASE_URL=sqlite:////var/lib/silver-safe/testing.db
SECRET_KEY=testing-secure-random-secret-key-32chars-min
ACCESS_TOKEN_EXPIRE_MINUTES=1440
TEST_ACCOUNT_PASSWORD=SafeVolunteer2026!
FIELD_ENCRYPTION_KEY=testing-encryption-key-for-elder-health-must-be-32bytes=
LOG_LEVEL=INFO
GEOFENCE_TRIGGER_COUNT=3
LOCATION_STALE_AFTER_SECONDS=120
GEOFENCE_MAX_ACCURACY_METERS=100.0
```
*保护该配置文件：*
```bash
sudo chown root:silver-safe /etc/silver-safe/testing.env
sudo chmod 640 /etc/silver-safe/testing.env
```

---

## 3. 服务托管与反向代理详细配置

### 3.1 Caddy 2 配置：`/etc/caddy/Caddyfile`
Caddy 默认自动管理 Let's Encrypt 证书签发与 HTTP 80 端口到 443 的重定向。

```caddy
# 替换为实际申请并解析的二级域名
silver-test.example.com {
    # 强制启用严格传输安全 HSTS
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }

    # 反向代理到本地单 Worker Uvicorn 后端
    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto https
    }
}
```

### 3.2 systemd 服务文件：`/etc/systemd/system/silver-safe-testing.service`
```ini
[Unit]
Description=Silver Safe Platform FastAPI Backend (Volunteer Testing)
After=network.target

[Service]
Type=simple
User=silver-safe
Group=silver-safe
WorkingDirectory=/opt/silver-safe/app
EnvironmentFile=/etc/silver-safe/testing.env

# 启动单 Worker Uvicorn 进程，保障 SQLite 单写安全
ExecStart=/opt/silver-safe/app/venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --access-log \
    --proxy-headers

Restart=always
RestartSec=5s
KillMode=process

# 安全沙箱加固
ProtectSystem=strict
ReadWritePaths=/var/lib/silver-safe /var/log/silver-safe
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

---

## 4. 多组隔离测试账号与预置围栏算法规范

### 4.1 账号矩阵生成规范（10 组）
在测试环境下，通过 `seed_volunteer_test_data` 批量构建 10 组完全隔离的家庭闭环：

| 组别编号 | 老人账号 | 家属账号 | 预置老人姓名 | 行程目的地 | 预置围栏状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `elder_test_01` | `family_test_01` | 测试老人01 | 测试公园A区 | 启用 (半径500m) |
| **02** | `elder_test_02` | `family_test_02` | 测试老人02 | 测试公园B区 | 启用 (半径500m) |
| ... | ... | ... | ... | ... | ... |
| **10** | `elder_test_10` | `family_test_10` | 测试老人10 | 测试公园J区 | 启用 (半径500m) |

### 4.2 电子围栏（Geofence）预置数据规则
为确保老人上报测试点位后，后端能立即完成风险判决并产生 `SAFE` 状态，必须为每位测试老人预置一条有效电子围栏记录：
* `elder_id`：对应的测试老人 ID；
* `center_latitude`：`23.119990`（测试基准纬度，可按实际城市调整）；
* `center_longitude`：`113.324520`（测试基准经度）；
* `radius_meters`：`500`（500米半径）；
* `enabled`：`True`（启用）；
* `crs`：`"WGS84"`（符合国家标准与微信定位原生坐标系）。

### 4.3 活跃出游任务（Active Trip）初始化
* 自动为每个测试老人创建一条 `Trip` 记录。
* 状态必须显式置为 `active`，并填入 `started_at` 时间戳。
* 只有在 `trip.status == "active"` 且存在启用的围栏时，老人上传点位才会由 [backend/app/services/safety.py](file:///d:/code/contest_code/backend/app/services/safety.py) 判定出实时 `risk_status`，家属端首页即可立即显示绿色安全状态。

---

## 5. 独立测试环境一键重置工具设计 (`scripts/reset_testing.py`)

### 5.1 执行逻辑与安全门禁
1. **安全校验（Safety Guard）**：
   * 检查 `APP_ENV` 是否等于 `testing`。若当前连接到生产或本地开发库 `silver_safe.db`，直接中断并报错退出。
2. **自动备份**：
   * 在清空前将当前的 `testing.db` 备份至 `/var/lib/silver-safe/backups/testing-before-reset-{TIMESTAMP}.db`。
3. **数据清空与重建**：
   * 开启数据库事务，清空或物理重建所有业务表（`locations`, `alerts`, `alert_logs`, `trips`, `elder_family_bindings`, `geofences`, `elders`, `users`）。
4. **重新播种**：
   * 调用扩展后的种子逻辑，在 1 秒内完整重建 10 组全新、干净的基线测试数据。

---

## 6. 发布前自动化预检脚本设计 (`scripts/verify_testing_readiness.py`)

在执行正式微信小程序体验版上传与邀请测试前，运行预检脚本执行全覆盖检查：

```
[PASS] 1. Python 依赖项检查与环境完整性
[PASS] 2. 核心后端自动化测试集回归 (94/94 passed)
[PASS] 3. 小程序前端单元测试回归 (27/27 passed)
[PASS] 4. 小程序配置检查: API_BASE_URL.testing 不得包含 'test-domain' 或 '127.0.0.1'
[PASS] 5. 数据库隔离检查: DATABASE_URL 绝非本地开发数据库 silver_safe.db
[PASS] 6. 10 组测试账号与绑定关系完整性校验 (elder_test_01~10 & family_test_01~10)
[PASS] 7. 预置电子围栏 (Geofence) 覆盖率检查 (10/10 enabled)
[PASS] 8. 活跃行程 (Active Trip) 覆盖率检查 (10/10 active)
[PASS] 9. 越权隔离校验: family_test_01 读取 elder_test_02 强制返回 403
[PASS] 10. SQLite WAL 模式已启用 (PRAGMA journal_mode=wal)
```
任何一项 `FAIL` 即终止发布，退出码返回非 0。

---

## 7. 真机端到端验收矩阵与执行手册

| 步骤 | 角色与设备 | 执行动作 | 预期系统表现 | 判定标准 |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | 老人端 (手机A) | 扫码打开微信体验版，输入 `elder_test_01` 与密码登录 | 成功进入老人端主页，显示“今日出游：测试公园A区” | 登录成功，Token 注入 |
| **Step 2** | 老人端 (手机A) | 点击“开启定位守护”，微信弹出位置授权并点击允许 | 提示“守护已开启”，后台/前台开始周期上报位置 | 接口返回 201，点位落库 |
| **Step 3** | 家属端 (手机B) | 扫码打开微信体验版，输入 `family_test_01` 与密码登录 | 进入家属首页，卡片显示绑定老人“测试老人01” | 绑定关系展示正确 |
| **Step 4** | 家属端 (手机B) | 观察主界面状态卡片 | 状态显示为：**安全** (SAFE)；定位时效显示为：**正常** (FRESH) | 状态准确，无“暂无” |
| **Step 5** | 家属端 (手机B) | 点击进入“查看位置/轨迹地图” | 地图准确打点并平滑绘制当前点位，轨迹无跳变瞬移 | 渲染平稳，无漂移 |
| **Step 6** | 越权测试 (接口) | 使用 `family_test_01` 的 Token 请求 `elder_test_02` 详情 | 后端直接拦截并抛出错误 | HTTP 403 禁止访问 |
