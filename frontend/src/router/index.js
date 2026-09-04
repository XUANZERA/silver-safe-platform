import {
  createRouter,
  createWebHashHistory,
} from 'vue-router'
import routes from './routes'
import { useUserStore } from '../stores/user'
import { isApiConfigured } from '../services/api'
import { demoOnlyRedirect, homePathForRole } from '../services/modeBoundary'

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta?.title) {
    document.title = to.meta.title
  }

  const userStore = useUserStore()
  if (to.meta?.demoOnly) {
    const redirect = demoOnlyRedirect(isApiConfigured(), userStore.isLoggedIn ? userStore.userInfo : null)
    if (redirect) return redirect
  }
  if (to.name === 'Login' && userStore.isLoggedIn) {
    return homePathForRole(userStore.userInfo.role)
  }
  if (to.meta?.requiresOperator) {
    if (!userStore.isLoggedIn) return '/login'
    if (userStore.userInfo.role !== 'operator') return '/login'
  }
  if (to.meta?.allowedRoles) {
    if (!userStore.isLoggedIn) return '/login'
    if (!to.meta.allowedRoles.includes(userStore.userInfo.role)) {
      return homePathForRole(userStore.userInfo.role)
    }
  }

  return true
})

export default router
