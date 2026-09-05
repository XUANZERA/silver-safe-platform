'use strict'

const api = require('../../services/api')
const config = require('../../config')
const { createLocationService, LOCATION_STATUS } = require('../../services/location')

const STATUS_TEXT = Object.freeze({
  [LOCATION_STATUS.IDLE]: '未开启',
  [LOCATION_STATUS.REQUESTING]: '正在请求定位',
  [LOCATION_STATUS.TRACKING]: '定位守护中',
  [LOCATION_STATUS.DEGRADED]: '定位不可用，正在重试',
  [LOCATION_STATUS.PERMISSION_DENIED]: '定位权限已拒绝'
})

function errorMessage(error, fallback) {
  return error?.message || error?.errMsg || fallback
}

Page({
  data: {
    username: config.demo?.elder?.username || '',
    password: config.demo?.elder?.password || '',
    loggedIn: false,
    user: null,
    loggingIn: false,
    loadingTrip: false,
    currentTrip: null,
    hasActiveTrip: false,
    locationStatus: LOCATION_STATUS.IDLE,
    locationStatusText: STATUS_TEXT[LOCATION_STATUS.IDLE],
    guardRunning: false,
    errorText: ''
  },

  onLoad() {
    this.destroyed = false
    this.locationService = createLocationService({
      wxApi: wx,
      uploadLocation: api.uploadLocation,
      intervalMs: config.locationIntervalMs,
      onStatusChange: (status) => {
        if (this.destroyed) return
        this.setData({
          locationStatus: status,
          locationStatusText: STATUS_TEXT[status],
          guardRunning: this.locationService?.isRunning() || false
        })
      },
      onError: ({ phase, permissionDenied }) => {
        if (this.destroyed) return
        const message = permissionDenied
          ? '定位权限被拒绝，请在小程序设置中允许位置信息后重新开启。'
          : phase === 'upload'
            ? '位置上传失败，守护会继续重试。'
            : '暂时无法取得位置，守护会继续重试。'
        this.setData({ errorText: message })
      }
    })

    // 页面创建时服务仅处于 IDLE；恢复登录不会启动 wx.getLocation。
    if (api.hasAccessToken()) void this.restoreSession()
  },

  onHide() {
    this.stopLocationGuard()
  },

  onUnload() {
    this.destroyed = true
    this.locationService?.stop()
  },

  async onPullDownRefresh() {
    this.stopLocationGuard()
    try {
      if (this.data.loggedIn) await this.loadCurrentTrip()
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
    this.stopLocationGuard()
    this.setData({ loggingIn: true, errorText: '' })
    try {
      const user = await api.login(this.data.username.trim(), this.data.password)
      if (user.role !== 'elder') {
        api.clearAccessToken()
        throw new Error('请使用老人账号登录此页面')
      }
      this.setData({ loggedIn: true, user })
      await this.loadCurrentTrip()
    } catch (error) {
      this.setData({
        loggedIn: false,
        user: null,
        currentTrip: null,
        hasActiveTrip: false,
        errorText: errorMessage(error, '登录失败')
      })
    } finally {
      this.setData({ loggingIn: false })
    }
  },

  async restoreSession() {
    try {
      const user = await api.getMe()
      if (user.role !== 'elder') {
        api.clearAccessToken()
        return
      }
      this.setData({ loggedIn: true, user })
      await this.loadCurrentTrip()
    } catch (error) {
      api.clearAccessToken()
      this.setData({
        loggedIn: false,
        errorText: errorMessage(error, '登录状态已失效，请重新登录')
      })
    }
  },

  async loadCurrentTrip() {
    if (this.data.loadingTrip) return
    this.setData({ loadingTrip: true, errorText: '' })
    try {
      const elderList = await api.listElders()
      const elder = elderList?.items?.[0]
      if (!elder?.id) throw new Error('Backend 未返回可访问的老人资料')
      const trip = await api.getCurrentTrip(elder.id)
      const hasActiveTrip = trip?.status === 'active'

      if (
        this.locationService?.isRunning() &&
        (!hasActiveTrip || trip.id !== this.data.currentTrip?.id)
      ) {
        this.stopLocationGuard()
      }
      this.setData({ currentTrip: trip, hasActiveTrip })
    } catch (error) {
      this.stopLocationGuard()
      this.setData({
        currentTrip: null,
        hasActiveTrip: false,
        errorText: errorMessage(error, '当前行程加载失败')
      })
      if (error?.status === 401) this.setData({ loggedIn: false, user: null })
    } finally {
      this.setData({ loadingTrip: false })
    }
  },

  handleStartGuard() {
    if (!this.data.hasActiveTrip) {
      this.setData({ errorText: 'Backend 当前没有 active trip，无法开启定位守护。' })
      return
    }
    this.setData({ errorText: '' })
    try {
      this.locationService.start(this.data.currentTrip)
      this.setData({ guardRunning: this.locationService.isRunning() })
    } catch (error) {
      this.setData({ errorText: errorMessage(error, '定位守护启动失败') })
    }
  },

  handleStopGuard() {
    this.stopLocationGuard()
  },

  stopLocationGuard() {
    this.locationService?.stop()
  },

  handleOpenSetting() {
    if (typeof wx?.openSetting !== 'function') return
    return new Promise((resolve) => {
      wx.openSetting({
        success: (res) => {
          if (res?.authSetting?.['scope.userLocation']) {
            this.setData({ errorText: '' })
          }
          resolve(res)
        },
        fail: (error) => {
          this.setData({ errorText: errorMessage(error, '打开设置失败') })
          resolve(null)
        }
      })
    })
  },

  handleLogout() {
    this.stopLocationGuard()
    api.clearAccessToken()
    this.setData({
      loggedIn: false,
      user: null,
      currentTrip: null,
      hasActiveTrip: false,
      errorText: ''
    })
  }
})
