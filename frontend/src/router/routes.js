const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: () => import('../views/login.vue'), meta: { title: '登录 · 银发独游' } },
  { path: '/elder', name: 'ElderHome', component: () => import('../views/elder/ElderHome.vue'), meta: { title: '老人端 · 银发独游', allowedRoles: ['elder'] } },
  { path: '/child', name: 'ChildHome', component: () => import('../views/child/ChildHome.vue'), meta: { title: '家人守护 · 银发独游', allowedRoles: ['family'] } },
  { path: '/operator', name: 'OperatorDashboard', component: () => import('../views/operator/OperatorDashboard.vue'), meta: { title: '运营工作台 · 银发独游', requiresOperator: true } },
  { path: '/elder/profile', name: 'ElderProfile', component: () => import('../views/elder/ElderProfile.vue'), meta: { title: '老人个人信息', allowedRoles: ['elder'] } },
  { path: '/child/profile', name: 'ChildProfile', component: () => import('../views/child/ChildProfile.vue'), meta: { title: '子女个人信息', allowedRoles: ['family'] } },
  { path: '/operator/profile', name: 'OperatorProfile', component: () => import('../views/operator/OperatorProfile.vue'), meta: { title: '运营端个人信息', requiresOperator: true } },
  { path: '/schedule', name: 'Schedule', component: () => import('../views/schedule/schedule.vue'), meta: { title: '旅游行程单', allowedRoles: ['elder', 'family'] } },
  // FIX START: 恢复 PR 前被 App.vue 直接挂载、PR 后却失去入口的仿真页面。
  { path: '/simulation', name: 'Simulation', component: () => import('../components/map/MapCanvas.vue'), meta: { title: '定位仿真 · 银发独游', allowedRoles: ['elder'], demoOnly: true } },
  // FIX END: 恢复仿真页面入口。
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/404.vue'), meta: { title: '页面未找到', noCache: true } },
]

export default routes
