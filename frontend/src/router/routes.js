
const routes = [
  
  {
    // 首页路由
    path: '/',
    name: 'Home',
    component: () => import('@/App.vue'), 
  },
  {
    // 登录路由
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login.vue'),
    meta: { title: '登录' }
  },
  {
    // 地图页面路由
    path: '/',
    name: 'Home',
    component: () => import('@/components/map/MapCanvas.vue'), 
  },


  {
    // 404 页面路由
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/404.vue'),
    meta: {
      title: '页面未找到',
      noCache: true,
    }
  },

  // 老人个人信息页面
  {
    path: '/elder/profile',
    name: 'ElderProfile',
    component: () => import('@/views/elder/ElderProfile.vue'), 
    meta: {
      title: '老人个人信息' 
    }
  },

  // 子女个人信息页面
  {
    path: '/child/profile',
    name: 'ChildProfile',
    component: () => import('@/views/child/ChildProfile.vue'),
    meta: {
      title: '子女个人信息' 
    }
  },

  // 运营端个人信息页面
  {
    path: '/operator/profile',
    name: 'OperatorProfile',
    component: () => import('@/views/operator/OperatorProfile.vue'),
    meta: {
      title: '运营端个人信息'
    }
  },

  // 行程单页面
  {
    path: '/schedule',
    name: 'Schedule',
    component: () => import('@/views/schedule/schedule.vue'),
    meta: {
      title: '旅游行程单'
    }
  }

]

export default routes
