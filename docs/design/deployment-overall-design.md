# 银龄安全系统志愿者测试部署总体设计


## 1. 系统架构


```

```
                微信用户

                   |
                   |

          微信小程序体验版

                   |

              HTTPS Request

                   |

          Reverse Proxy

             (Nginx)

                   |

            FastAPI Backend

                   |

         Testing Database

             SQLite/PostgreSQL
```

```


---

# 2. 部署组件


## 2.1 Mini Program

职责：

- 用户交互
- GPS采集
- 数据上传
- 状态展示


不负责：

- 风险计算
- Freshness计算
- 围栏判断


---

## 2.2 Backend


职责：

- 用户认证
- 权限控制
- 行程管理
- 定位存储
- Safety计算


Backend保持唯一事实来源。


---

## 2.3 Reverse Proxy


职责：

- HTTPS终止
- 转发API请求
- 隐藏Backend端口


推荐：

Nginx


---

## 2.4 Database


测试阶段：

推荐：

单实例数据库。


要求：

独立testing数据库。


---

# 3. 环境划分


## Development


用途：

开发者本地调试。


特点：

```

localhost
DEBUG=true

```



## Testing


用途：

志愿者测试。


特点：

```

公网HTTPS
DEBUG=false
独立数据库

```


---

# 4. 数据流


## 定位上传


```

老人手机

wx.getLocation()

↓

Mini Program

↓

POST /locations

↓

Backend

↓

Database

```


---

## 家属查看


```

Family Mini Program

↓

GET /safety

↓

Backend计算结果

↓

展示状态

```


---

# 5. 安全原则


## Backend Authority

所有：

- 风险
- 新鲜度
- 安全状态

必须Backend计算。


客户端只能：

- 展示
- 采集


---

# 6. 部署策略


第一阶段：

单服务器部署。


原因：

- 测试人数少
- 成本低
- 易维护


未来：

迁移：

```

SQLite

↓

PostgreSQL

↓

Container deployment

```