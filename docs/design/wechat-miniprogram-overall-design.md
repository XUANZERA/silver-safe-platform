# 微信小程序总体设计


# 1. 总体架构


```

```
微信小程序

     |
     |
 wx.request
 wx.getLocation

     |

 FastAPI Backend

     |

 Database

```

---

# 2. 设计原则

## Backend Authority

所有业务状态由Backend决定。

小程序只负责：

* 用户交互
* GPS采集
* 数据展示

---

# 3. 模块设计

## pages

```
pages/

 elder/

   index
   location


 family/

   index
   map

```

---

# 4. 网络层

封装：

utils/request.js

负责：

* token
* header
* error

---

# 5. Location模块

location/

LocationManager.js

职责：

管理：

IDLE

TRACKING

调用：

wx.getLocation

上传：

backend API

---

# 6. 地图模块

使用：

微信map组件

数据来源：

Safety View

流程：

Backend WGS84

↓

前端展示转换

↓

map

---

# 7. 安全边界

禁止：

前端计算freshness

禁止：

本地生成风险

禁止：

Demo fallback
