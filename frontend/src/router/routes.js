const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: () => import('../views/login.vue'), meta: { title: '登录 · 银发独游' } },
  { path: '/operator', name: 'OperatorDashboard', component: () => import('../views/operator/OperatorDashboard.vue'), meta: { title: '运营工作台 · 银发独游', requiresOperator: true } },
  { path: '/elder/profile', name: 'ElderProfile', component: () => import('../views/elder/ElderProfile.vue'), meta: { title: '老人个人信息' } },
  { path: '/child/profile', name: 'ChildProfile', component: () => import('../views/child/ChildProfile.vue'), meta: { title: '子女个人信息' } },
  { path: '/operator/profile', name: 'OperatorProfile', component: () => import('../views/operator/OperatorProfile.vue'), meta: { title: '运营端个人信息', requiresOperator: true } },
  { path: '/schedule', name: 'Schedule', component: () => import('../views/schedule/schedule.vue'), meta: { title: '旅游行程单' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/404.vue'), meta: { title: '页面未找到', noCache: true } },
]

export default routes
