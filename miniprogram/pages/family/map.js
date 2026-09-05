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

Page({
  data: {
    username: '',
    password: '',
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
      this.setData({ password: '' })
      await this.loadSafety()
    } catch (error) {
      this.setData({
        loggedIn: false,
        user: null,
        elder: null,
        safetyView: null,
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
      ...EMPTY_SAFETY_VIEW,
      password: '',
      errorText: ''
    })
  }
})
