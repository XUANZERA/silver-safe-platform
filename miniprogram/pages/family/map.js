'use strict'

const api = require('../../services/api')
const config = require('../../config')
const { presentSafetyView } = require('../../services/map')

function errorMessage(error, fallback) {
  return error?.message || error?.errMsg || fallback
}

const EMPTY_SAFETY_VIEW = Object.freeze({
  locationHealth: '--',
  recordedAt: '--',
  sourceCrs: '--',
  latitude: null,
  longitude: null,
  hasLocation: false,
  mapLatitude: 0,
  mapLongitude: 0,
  circles: []
})

Page({
  data: {
    username: config.demo?.family?.username || '',
    password: config.demo?.family?.password || '',
    loggedIn: false,
    user: null,
    loggingIn: false,
    loadingSafety: false,
    elder: null,
    safetyView: null,
    ...EMPTY_SAFETY_VIEW,
    errorText: ''
  },

  onLoad() {
    if (api.hasAccessToken()) void this.restoreSession()
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
      await this.loadSafety()
    } catch (error) {
      this.setData({
        loggedIn: false,
        user: null,
        elder: null,
        safetyView: null,
        ...EMPTY_SAFETY_VIEW,
        errorText: errorMessage(error, '登录失败')
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
    } catch (error) {
      api.clearAccessToken()
      this.setData({
        loggedIn: false,
        errorText: errorMessage(error, '登录状态已失效，请重新登录')
      })
    }
  },

  async loadSafety() {
    if (this.data.loadingSafety) return
    this.setData({ loadingSafety: true, errorText: '' })
    try {
      const elderList = await api.listElders()
      const elder = elderList?.items?.[0]
      if (!elder?.id) throw new Error('Backend 未返回可访问的老人资料')
      const safetyView = await api.getSafetyView(elder.id)
      this.setData({
        elder,
        safetyView,
        ...presentSafetyView(safetyView)
      })
    } catch (error) {
      this.setData({
        elder: null,
        safetyView: null,
        ...EMPTY_SAFETY_VIEW,
        errorText: errorMessage(error, 'Safety View 加载失败')
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
      ...EMPTY_SAFETY_VIEW,
      errorText: ''
    })
  }
})
