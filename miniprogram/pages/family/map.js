'use strict'

const api = require('../../services/api')
const { presentSafetyView } = require('../../services/map')
const { userFacingError } = require('../../services/userMessage')

const EMPTY_SAFETY_VIEW = Object.freeze({
  locationHealth: null,
  locationHealthText: '暂无定位信息',
  riskStatus: null,
  riskStatusText: '暂无安全状态',
  recordedAt: '--',
  recordedAtText: '暂无更新时间',
  sourceCrs: '--',
  latitude: null,
  longitude: null,
  hasLocation: false,
  mapLatitude: 0,
  mapLongitude: 0,
  circles: []
})

function compareAlertsByNewest(left, right) {
  const leftTime = Date.parse(left?.occurred_at || '') || 0
  const rightTime = Date.parse(right?.occurred_at || '') || 0
  if (leftTime !== rightTime) return rightTime - leftTime
  return (Number(right?.id) || 0) - (Number(left?.id) || 0)
}

function selectPrimaryAlert(alerts) {
  const ordered = alerts.filter((alert) => alert && typeof alert === 'object').slice().sort(compareAlertsByNewest)
  const openSos = ordered.filter((alert) =>
    alert.type === 'emergency' && ['new', 'processing'].includes(alert.status)
  )
  if (openSos.length) return openSos[0]

  const geofenceAlert = ordered.find((alert) => alert.type === 'geofence_exit')
  return geofenceAlert || ordered[0] || null
}

function presentAlert(alert) {
  if (!alert) return null
  return {
    ...alert,
    title: alert.type === 'emergency'
      ? '老人发起紧急求助'
      : alert.type === 'geofence_exit'
        ? '安全区域告警'
        : '安全告警',
    statusText: alert.status === 'new'
      ? '待处理'
      : alert.status === 'processing'
        ? '处理中'
        : String(alert.status || '状态未知')
  }
}

function readAlerts(response) {
  if (Array.isArray(response)) return response
  if (Array.isArray(response?.items)) return response.items
  throw new Error('invalid alerts response')
}

Page({
  data: {
    username: '',
    password: '',
    loggedIn: false,
    user: null,
    loggingIn: false,
    loadingSafety: false,
    sessionReady: false,
    elder: null,
    safetyView: null,
    alerts: [],
    alertsEmpty: false,
    alertLoadFailed: false,
    primaryAlert: null,
    ...EMPTY_SAFETY_VIEW,
    errorText: ''
  },

  onLoad() {
    if (api.hasAccessToken()) return this.restoreSession()
    this.setData({ sessionReady: true })
  },

  onShow() {
    if (!this.data.loggedIn || !this.data.sessionReady) return
    return this.loadSafety()
  },

  async onPullDownRefresh() {
    try {
      if (this.data.loggedIn) await this.loadSafety()
    } finally {
      wx.stopPullDownRefresh()
    }
  },

  onUsernameInput(event) {
    this.setData({ username: event.detail.value })
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value })
  },

  async handleLogin() {
    if (this.data.loggingIn) return
    this.setData({ loggingIn: true, errorText: '' })
    try {
      const user = await api.login(this.data.username.trim(), this.data.password)
      if (user.role !== 'family') {
        api.clearAccessToken()
        throw new Error('请使用家属账号登录此页面')
      }
      this.setData({ loggedIn: true, user })
      this.setData({ password: '' })
      await this.loadSafety()
      this.setData({ sessionReady: true })
    } catch (error) {
      this.setData({
        loggedIn: false,
        user: null,
        elder: null,
        safetyView: null,
        alerts: [],
        alertsEmpty: false,
        alertLoadFailed: false,
        primaryAlert: null,
        ...EMPTY_SAFETY_VIEW,
        errorText: userFacingError(error, '登录失败，请检查账号和密码')
      })
    } finally {
      this.setData({ loggingIn: false })
    }
  },

  async restoreSession() {
    try {
      const user = await api.getMe()
      if (user.role !== 'family') {
        api.clearAccessToken()
        return
      }
      this.setData({ loggedIn: true, user })
      await this.loadSafety()
      this.setData({ sessionReady: true })
    } catch (error) {
      api.clearAccessToken()
      this.setData({
        loggedIn: false,
        errorText: userFacingError(error, '登录状态已失效，请重新登录')
      })
    }
  },

  async loadSafety() {
    if (this.data.loadingSafety) return
    this.setData({ loadingSafety: true, errorText: '' })
    try {
      const elderList = await api.listElders()
      const elder = elderList?.items?.[0]
      if (!elder?.id) throw new Error('missing elder')

      this.setData({ elder })
      const safetyRequest = api.getSafetyView(elder.id).then(
        (value) => ({ succeeded: true, value }),
        (error) => ({ succeeded: false, error })
      )
      const alertsRequest = api.getElderAlerts(elder.id).then(
        (value) => ({ succeeded: true, value }),
        (error) => ({ succeeded: false, error })
      )
      const [safetyResult, alertsResult] = await Promise.all([safetyRequest, alertsRequest])

      if (safetyResult.succeeded) {
        this.setData({
          safetyView: safetyResult.value,
          ...presentSafetyView(safetyResult.value)
        })
      } else {
        this.setData({
          safetyView: null,
          ...EMPTY_SAFETY_VIEW,
          errorText: userFacingError(safetyResult.error, '安全信息加载失败，请稍后重试')
        })
        if (safetyResult.error?.status === 401) this.setData({ loggedIn: false, user: null })
      }

      if (alertsResult.succeeded) {
        try {
          const alerts = readAlerts(alertsResult.value)
          this.setData({
            alerts,
            alertsEmpty: alerts.length === 0,
            alertLoadFailed: false,
            primaryAlert: presentAlert(selectPrimaryAlert(alerts))
          })
        } catch {
          this.setData({ alerts: [], alertsEmpty: false, alertLoadFailed: true, primaryAlert: null })
        }
      } else {
        this.setData({ alerts: [], alertsEmpty: false, alertLoadFailed: true, primaryAlert: null })
        if (alertsResult.error?.status === 401) this.setData({ loggedIn: false, user: null })
      }
    } catch (error) {
      this.setData({
        elder: null,
        safetyView: null,
        alerts: [],
        alertsEmpty: false,
        alertLoadFailed: true,
        primaryAlert: null,
        ...EMPTY_SAFETY_VIEW,
        errorText: userFacingError(error, '安全信息加载失败，请稍后重试')
      })
      if (error?.status === 401) this.setData({ loggedIn: false, user: null })
    } finally {
      this.setData({ loadingSafety: false })
    }
  },

  handleLogout() {
    api.clearAccessToken()
    this.setData({
      loggedIn: false,
      user: null,
      elder: null,
      safetyView: null,
      alerts: [],
      alertsEmpty: false,
      alertLoadFailed: false,
      primaryAlert: null,
      ...EMPTY_SAFETY_VIEW,
      password: '',
      errorText: ''
    })
  }
})
