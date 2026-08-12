import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({})
  const isLoggedIn = ref(false)

  const setUserInfo = (info) => {
    userInfo.value = info
    isLoggedIn.value = true
    sessionStorage.setItem('userInfo', JSON.stringify(info))
  }

  const getUserInfo = () => {
    const info = sessionStorage.getItem('userInfo')
    if (info) {
      try {
        userInfo.value = JSON.parse(info)
        isLoggedIn.value = true
      } catch {
        sessionStorage.removeItem('userInfo')
      }
    }
    return userInfo.value
  }

  const logout = () => {
    userInfo.value = {}
    isLoggedIn.value = false
    sessionStorage.removeItem('userInfo')
  }

  getUserInfo()

  return {
    userInfo,
    isLoggedIn,
    setUserInfo,
    getUserInfo,
    logout
  }
})
