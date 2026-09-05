# 微信小程序客户端适配需求分析

## 1. 项目背景

当前银发安全出游系统已经完成：

- Elder Web端
- Family Web端
- Operator Web端
- FastAPI Backend
- REAL Location Pipeline

现需要增加微信小程序客户端，用于真实移动设备测试。

微信小程序不是替代已有Web系统，而是新增移动端客户端。

---

# 2. 建设目标

## 2.1 核心目标

实现微信环境下：

老人：

- 登录系统
- 查看当前出游状态
- 主动开启定位守护
- 持续上传真实GPS

家属：

- 查看老人当前位置
- 查看定位更新时间
- 查看安全状态


---

# 3. 非目标

本阶段不实现：

- 微信账号绑定体系
- 微信支付
- 微信订阅消息
- 后台持续定位
- 小程序正式发布
- 云开发


---

# 4. 用户角色

## Elder

功能：

- 当前行程查看
- 定位权限申请
- GPS上传


## Family

功能：

- 查看老人安全状态
- 查看地图位置
- 查看最后更新时间


---

# 5. 功能需求


## FR-WX-001 微信老人定位

用户点击：

开启定位守护


系统：

调用微信定位API：

wx.getLocation


获得：

latitude
longitude
accuracy


转换为：

WGS84 LocationSample


上传：

POST /locations


---

## FR-WX-002 定位生命周期

状态：

IDLE

REQUESTING

TRACKING

DEGRADED

PERMISSION_DENIED


刷新后：

必须恢复：

IDLE


禁止：

自动启动定位。


---

## FR-WX-003 家属地图

展示：

- 最新记录位置
- 最后更新时间
- 定位状态


禁止：

显示实时位置。


---

## FR-WX-004 后端复用

小程序必须调用现有API：

Auth

Trip

Safety

Location


禁止：

复制业务逻辑。


---

# 6. 验收标准


老人：

✓ 可以打开小程序

✓ 点击开启定位

✓ 手机允许定位

✓ 后端收到Location


家属：

✓ 可以看到老人位置

✓ 可以看到更新时间

✓ stale状态正确显示
