# 银龄安全系统志愿者测试部署详细设计


# 1. 部署环境


## Server

最低配置：

```

CPU:
2核

RAM:
4GB

Storage:
40GB

```


操作系统：

```

Ubuntu 22.04+

```


---

# 2. Backend部署


目录：

```

/srv/silver-safe/

backend/

data/

logs/

```


启动：

```

python -m uvicorn app.main:app 
--host 127.0.0.1 
--port 8000 
--workers 1

```


---

# 3. 环境变量


示例：

```

APP_ENV=testing

DEBUG=false

DATABASE_URL=<testing database>

SECRET_KEY=<random>

HEALTH_INFO_ENCRYPTION_KEY=<random>

TEST_ACCOUNT_PASSWORD=<secret>

```


禁止：

- 写入代码
- 提交Git


---

# 4. HTTPS配置


Nginx:

```

443 HTTPS

↓

127.0.0.1:8000

```


要求：

- TLS证书
- 自动续期
- HTTP跳转HTTPS


---

# 5. 微信配置


微信公众平台：


配置：

```

开发管理

↓

服务器域名

↓

request合法域名

```


加入：

```

[https://api.example.com](https://api.example.com)

```


---

# 6. 测试账号


生成：

```

elder_test_01

family_test_01

elder_test_02

family_test_02

```


每组拥有：

- 独立用户
- 独立老人
- 独立trip


---

# 7. 发布流程


## Backend


1. 拉取代码

2. 创建环境变量

3. 初始化数据库

4. 启动服务


---

## Mini Program


1. 修改testing API URL

2. 微信开发者工具上传

3. 设置体验成员

4. 发布体验版


---

# 8. 验收测试


## 老人端


检查：

- 登录成功
- 定位授权成功
- GPS上传


## 家属端


检查：

- 登录成功
- 查看老人
- Safety状态显示


---

# 9. 回滚


保留：

- 上一版本代码
- 数据库备份
- 小程序旧体验版


出现问题：

立即停止测试。
```