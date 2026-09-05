'use strict'

const { configureApi } = require('./services/api')
const config = require('./config')

App({
  onLaunch() {
    configureApi({ baseUrl: config.apiBaseUrl })
  }
})
