const API_BASE = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function createApiClient({ baseUrl, fetchImpl = (...args) => globalThis.fetch(...args) }) {
  let accessToken = ''
  let refreshPromise = null

  async function request(path, options = {}, retry = true) {
    if (!baseUrl) throw new Error('API_DISABLED')
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`
    const response = await fetchImpl(`${baseUrl}${path}`, { ...options, headers, credentials: 'include' })
    if (response.status === 401 && retry && path !== '/auth/refresh') {
      try {
        await refreshSession()
        return request(path, options, false)
      } catch {
        // Preserve the original request failure when the shared refresh fails.
      }
    }
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload?.error?.message || payload?.message || payload?.detail || '请求失败')
    return Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload
  }

  async function performRefresh() {
    const data = await request('/auth/refresh', { method: 'POST' }, false)
    accessToken = data.access_token
    return data.user
  }

  function refreshSession() {
    if (!refreshPromise) {
      refreshPromise = performRefresh().finally(() => {
        refreshPromise = null
      })
    }
    return refreshPromise
  }

  async function loginRequest(username, password) {
    const data = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }, false)
    accessToken = data.access_token
    return data.user
  }

  async function logoutRequest() {
    try { await request('/auth/logout', { method: 'POST' }, false) } finally { accessToken = '' }
  }

  return { loginRequest, logoutRequest, refreshSession, request }
}

const apiClient = createApiClient({ baseUrl: API_BASE })
const request = apiClient.request

export async function loginRequest(username, password) {
  return apiClient.loginRequest(username, password)
}

export async function refreshSession() {
  return apiClient.refreshSession()
}

export async function logoutRequest() {
  return apiClient.logoutRequest()
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: 'DELETE' })
}

export const elderApi = {
  list: () => request('/elders'),
  detail: (elderId) => request(`/elders/${elderId}`),
  geofence: (elderId) => request(`/elders/${elderId}/geofence`),
  safety: (elderId) => request(`/elders/${elderId}/safety`),
  currentTrip: (elderId) => request(`/elders/${elderId}/current-trip`),
  alerts: (elderId, status) => request(`/elders/${elderId}/alerts${status ? `?status=${encodeURIComponent(status)}` : ''}`)
}

export const tripApi = {
  create: (destination) => request('/trips', { method: 'POST', body: JSON.stringify({ destination }) }),
  start: (tripId) => request(`/trips/${tripId}/start`, { method: 'POST' }),
  end: (tripId) => request(`/trips/${tripId}/end`, { method: 'POST' }),
  cancel: (tripId, reason) => request(`/trips/${tripId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) })
}

export const alertApi = {
  list: (params = '') => request(`/alerts${params ? `?${params}` : ''}`),
  accept: (alertId) => request(`/alerts/${alertId}/accept`, { method: 'PATCH' }),
  resolve: (alertId, resolution) => request(`/alerts/${alertId}/resolve`, { method: 'PATCH', body: JSON.stringify({ resolution }) }),
  sos: (tripId) => request('/alerts/sos', { method: 'POST', body: JSON.stringify({ trip_id: tripId }) })
}

export const aiApi = {
  chat: (message, elderId, elderName) => request('/ai/chat', { method: 'POST', body: JSON.stringify({ message, elder_id: elderId, elder_name: elderName }) })
}

export const locationApi = {
  latest: (tripId) => request(`/trips/${tripId}/locations/latest`),
  track: (tripId, limit = 500) => request(`/trips/${tripId}/locations?limit=${limit}`),
  upload: (tripId, payload) => request(`/trips/${tripId}/locations`, { method: 'POST', body: JSON.stringify(payload) })
}

export const isApiConfigured = () => Boolean(API_BASE)
