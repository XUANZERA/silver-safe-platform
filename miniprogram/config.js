'use strict'

const API_BASE_URL = Object.freeze({
  development: 'http://127.0.0.1:8000/api/v1',
  // 发布志愿者体验版前，将域名替换为已加入微信 request 合法域名的 HTTPS 地址。
  testing: 'https://test-domain/api/v1'
})

const ENVIRONMENT_BY_VERSION = Object.freeze({
  develop: 'development',
  trial: 'testing',
  release: 'testing'
})

function resolveEnvironment(wxApi) {
  try {
    const envVersion = wxApi?.getAccountInfoSync?.()?.miniProgram?.envVersion
    return ENVIRONMENT_BY_VERSION[envVersion] || 'development'
  } catch {
    return 'development'
  }
}

function resolveConfig(wxApi) {
  const environment = resolveEnvironment(wxApi)
  return Object.freeze({
    environment,
    apiBaseUrl: API_BASE_URL[environment],
    locationIntervalMs: 10000
  })
}

module.exports = Object.freeze({
  API_BASE_URL,
  resolveEnvironment,
  resolveConfig,
  ...resolveConfig(typeof wx === 'undefined' ? null : wx)
})
