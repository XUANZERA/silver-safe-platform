import {
  createRouter,
  createWebHashHistory,
} from 'vue-router'
import routes from './routes'

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  // 设置页面标题
  if (to.meta?.title) {
    document.title = to.meta.title
  }
  next()
})

export default router
