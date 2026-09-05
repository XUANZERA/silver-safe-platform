'use strict'

const { configureApi } = require('./services/api')
const config = require('./config')

App({
  onLaunch() {
    const runtimeConfig = config.resolveConfig(wx)
    configureApi({ baseUrl: runtimeConfig.apiBaseUrl })
  }
})
