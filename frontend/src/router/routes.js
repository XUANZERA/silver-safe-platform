
const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/App.vue'), // 首页组件
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login.vue'),// 登录组件
    meta: { title: '登录' }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/components/map/MapCanvas.vue'), // 直接使用地图组件
  },

  // 404 页面
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/404.vue'),
    meta: {
      title: '页面未找到',
      noCache: true,
    },
  }
]

export default routes
