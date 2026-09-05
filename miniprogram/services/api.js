'use strict'

const TOKEN_STORAGE_KEY = 'silver_safe_access_token'

class ApiError extends Error {
  constructor(message, { status = null, code = null, cause = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.cause = cause
  }
}

function runtimeWx() {
  return typeof wx === 'undefined' ? null : wx
}

function normalizeBaseUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function normalizePath(value) {
  const path = String(value || '')
  return path.startsWith('/') ? path : `/${path}`
}

function readStoredToken(storage) {
  try {
    return String(storage?.getStorageSync?.(TOKEN_STORAGE_KEY) || '')
  } catch {
    return ''
  }
}

function createApiClient({ baseUrl = '', wxApi = null, storage = null } = {}) {
  let configuredBaseUrl = normalizeBaseUrl(baseUrl)
  let accessToken = readStoredToken(storage || wxApi || runtimeWx())

  function resolveWxApi() {
    return wxApi || runtimeWx()
  }

  function resolveStorage() {
    return storage || resolveWxApi()
  }

  function configure({ baseUrl: nextBaseUrl } = {}) {
    configuredBaseUrl = normalizeBaseUrl(nextBaseUrl)
  }

  function setAccessToken(token) {
    accessToken = String(token || '')
    const storageApi = resolveStorage()
    try {
      if (accessToken) storageApi?.setStorageSync?.(TOKEN_STORAGE_KEY, accessToken)
      else storageApi?.removeStorageSync?.(TOKEN_STORAGE_KEY)
    } catch {
      // 内存中的 Backend token 仍可用于本次小程序会话。
    }
  }

  function clearAccessToken() {
    setAccessToken('')
  }

  function hasAccessToken() {
    return Boolean(accessToken)
  }

  function request(path, { method = 'GET', data, header = {}, authenticated = true } = {}) {
    const wxRuntime = resolveWxApi()
    if (!configuredBaseUrl) {
      return Promise.reject(new ApiError('未配置 Backend API 地址', { code: 'API_DISABLED' }))
    }
    if (!wxRuntime || typeof wxRuntime.request !== 'function') {
      return Promise.reject(new ApiError('当前环境不支持 wx.request', { code: 'REQUEST_UNSUPPORTED' }))
    }

    const requestHeader = {
      'content-type': 'application/json',
      ...header
    }
    if (authenticated && accessToken) {
      requestHeader.Authorization = `Bearer ${accessToken}`
    }

    return new Promise((resolve, reject) => {
      wxRuntime.request({
        url: `${configuredBaseUrl}${normalizePath(path)}`,
        method,
        data,
        header: requestHeader,
        success(response) {
          const status = Number(response?.statusCode)
          const payload = response?.data || {}
          if (status >= 200 && status < 300) {
            const hasData = Object.prototype.hasOwnProperty.call(payload, 'data')
            resolve(hasData ? payload.data : payload)
            return
          }

          if (status === 401 && authenticated) clearAccessToken()
          reject(new ApiError(
            payload?.error?.message || payload?.message || payload?.detail || 'Backend 请求失败',
            {
              status: Number.isFinite(status) ? status : null,
              code: payload?.error?.code || payload?.code || null
            }
          ))
        },
        fail(error) {
          reject(new ApiError(error?.errMsg || '网络请求失败', {
            code: 'NETWORK_ERROR',
            cause: error
          }))
        }
      })
    })
  }

  async function login(username, password) {
    const data = await request('/auth/login', {
      method: 'POST',
      data: { username, password },
      authenticated: false
    })
    if (!data?.access_token || !data?.user) {
      throw new ApiError('Backend 登录响应缺少必要字段', { code: 'INVALID_LOGIN_RESPONSE' })
    }
    setAccessToken(data.access_token)
    return data.user
  }

  return {
    configure,
    request,
    login,
    clearAccessToken,
    hasAccessToken,
    getMe: () => request('/auth/me'),
    listElders: () => request('/elders'),
    getCurrentTrip: (elderId) => request(`/elders/${elderId}/current-trip`),
    uploadLocation: (tripId, payload) => request(`/trips/${tripId}/locations`, {
      method: 'POST',
      data: payload
    }),
    getSafetyView: (elderId) => request(`/elders/${elderId}/safety`)
  }
}

const apiClient = createApiClient()

module.exports = {
  ApiError,
  TOKEN_STORAGE_KEY,
  createApiClient,
  configureApi: (options) => apiClient.configure(options),
  login: (username, password) => apiClient.login(username, password),
  clearAccessToken: () => apiClient.clearAccessToken(),
  hasAccessToken: () => apiClient.hasAccessToken(),
  getMe: () => apiClient.getMe(),
  listElders: () => apiClient.listElders(),
  getCurrentTrip: (elderId) => apiClient.getCurrentTrip(elderId),
  uploadLocation: (tripId, payload) => apiClient.uploadLocation(tripId, payload),
  getSafetyView: (elderId) => apiClient.getSafetyView(elderId)
}
