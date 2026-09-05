# 银龄安全系统志愿者测试版本详细设计


# 1. 小程序老人端


## 登录模块


输入：

username

password


调用：

POST /auth/login


保存：

access token



---

## 定位模块


状态机：

```
IDLE

REQUESTING

TRACKING

DEGRADED

PERMISSION_DENIED
```


流程：

用户点击按钮

↓

申请微信权限

↓

获取WGS84坐标

↓

上传Backend


---

# 2. 家属端


流程：

登录

↓

查询绑定老人

↓

请求Safety View

↓

展示地图


---

# 3. Backend接口


主要接口：

## 登录

```
POST /api/v1/auth/login
```


## 当前任务

```
GET /api/v1/trips/current
```


## 上传位置

```
POST /api/v1/location
```


## 安全视图

```
GET /api/v1/safety/view
```


---

# 4. 测试数据设计


测试用户：

elder_test_01

family_test_01


测试任务：

```
status=active

destination=测试公园
```


---

# 5. 异常处理


定位拒绝：

进入：

PERMISSION_DENIED


网络异常：

提示用户稍后重试。


---

# 6. 测试流程


1.

老人登录


2.

查看任务


3.

开启定位


4.

检查位置上传


5.

家属查看地图


完成闭环。