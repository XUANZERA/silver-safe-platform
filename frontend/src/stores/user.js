import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({})
  const isLoggedIn = ref(false)

  const setUserInfo = (info) => {
    userInfo.value = info
    isLoggedIn.value = true
    localStorage.setItem('userInfo', JSON.stringify(info))
  }

  const getUserInfo = () => {
    const info = localStorage.getItem('userInfo')
    if (info) {
      userInfo.value = JSON.parse(info)
      isLoggedIn.value = true
    }
    return userInfo.value
  }

  const logout = () => {
    userInfo.value = {}
    isLoggedIn.value = false
    localStorage.removeItem('userInfo')
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