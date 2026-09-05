'use strict'

module.exports = Object.freeze({
  // 真机调试时改为手机可访问且已加入微信 request 合法域名的 Backend 地址。
  apiBaseUrl: 'http://192.168.10.197:8000/api/v1',
  locationIntervalMs: 10000,
  demo: Object.freeze({
    elder: Object.freeze({
      username: 'elder01',
      password: 'demo123'
    }),
    family: Object.freeze({
      username: 'family01',
      password: 'demo123'
    })
  })
})

