import {
  createRouter,
  createWebHashHistory,
} from 'vue-router'
import routes from './routes'
import { useUserStore } from '../stores/user'

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta?.title) {
    document.title = to.meta.title
  }

  const userStore = useUserStore()
  if (to.name === 'Login' && userStore.isLoggedIn) {
    return userStore.userInfo.role === 'operator' ? '/operator' : true
  }
  if (to.meta?.requiresOperator) {
    if (!userStore.isLoggedIn) return '/login'
    if (userStore.userInfo.role !== 'operator') return '/login'
  }

  return true
})

export default router
