# 微信小程序详细设计


# 1. 项目结构


````

miniprogram/

app.js

app.json

pages/

utils/

services/

```

---

# 2. request设计


services/api.js


接口：

request(config)


自动添加：

Authorization


---

# 3. 登录流程


启动：

↓

输入测试账号

↓

调用：

POST /auth/login


↓

保存token


↓

进入主页


---

# 4. 老人定位流程


点击按钮：

开启定位守护


状态：

IDLE

↓

REQUESTING

↓

wx.getLocation

↓

TRACKING


上传：

POST

/api/v1/trips/{id}/locations


payload:

{

latitude,

longitude,

accuracy,

source_crs:"WGS84"

}


---

# 5. 家属流程


页面加载：

GET safety


返回：

SafetyView


展示：


location_health


latest_location


recorded_at



---

# 6. 错误处理


定位失败：

显示：

定位不可用


权限拒绝：

提示用户开启权限


网络失败：

显示：

数据不可用


---

# 7. 测试设计


TC-WX-001

老人开启定位成功


TC-WX-002

拒绝定位权限


TC-WX-003

上传失败


TC-WX-004

家属查看位置


TC-WX-005

刷新后不会自动定位