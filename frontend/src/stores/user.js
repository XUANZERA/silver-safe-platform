import { defineStore } from 'pinia'
import { ref } from 'vue'
import { isApiConfigured, refreshSession } from '../services/api'
import { homePathForRole, modeName, sessionMatchesMode } from '../services/modeBoundary'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({})
  const isLoggedIn = ref(false)
  const authReady = ref(!isApiConfigured())
  const authError = ref(null)
  let authBootstrapPromise = null

  const setUserInfo = (info) => {
    userInfo.value = info
    isLoggedIn.value = true
    authReady.value = true
    authError.value = null
    sessionStorage.setItem('userInfo', JSON.stringify(info))
  }

  const getUserInfo = () => {
    const info = sessionStorage.getItem('userInfo')
    if (info) {
      try {
        const parsed = JSON.parse(info)
        if (!sessionMatchesMode(parsed, isApiConfigured())) {
          sessionStorage.removeItem('userInfo')
          return userInfo.value
        }
        userInfo.value = parsed
        isLoggedIn.value = true
        authReady.value = !isApiConfigured()
      } catch {
        sessionStorage.removeItem('userInfo')
      }
    }
    return userInfo.value
  }

  const logout = () => {
    userInfo.value = {}
    isLoggedIn.value = false
    authReady.value = !isApiConfigured()
    sessionStorage.removeItem('userInfo')
  }

  const ensureAuthReady = () => {
    if (!isApiConfigured() || authReady.value) return Promise.resolve(userInfo.value)
    if (!isLoggedIn.value) return Promise.reject(new Error('没有可恢复的登录会话'))
    if (authBootstrapPromise) return authBootstrapPromise

    authBootstrapPromise = refreshSession()
      .then((user) => {
        const session = {
          ...user,
          displayName: user.displayName || user.username,
          path: homePathForRole(user.role),
          mode: modeName(true)
        }
        setUserInfo(session)
        return session
      })
      .catch((error) => {
        logout()
        authError.value = error
        throw error
      })
      .finally(() => {
        authBootstrapPromise = null
      })
    return authBootstrapPromise
  }

  getUserInfo()

  return {
    userInfo,
    isLoggedIn,
    authReady,
    authError,
    setUserInfo,
    getUserInfo,
    ensureAuthReady,
    logout
  }
})
