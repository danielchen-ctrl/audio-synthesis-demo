import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/pages/Login.vue'), meta: { public: true } },
    { path: '/register', component: () => import('@/pages/Register.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', redirect: '/home' },
        { path: 'home', component: () => import('@/pages/Home.vue') },
        { path: 'myaudio', component: () => import('@/pages/MyAudio.vue') },
        { path: 'tasks', component: () => import('@/pages/Tasks.vue') },
        { path: 'trash', component: () => import('@/pages/Trash.vue') },
        { path: 'detail/:id', component: () => import('@/pages/Detail.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) return '/login'
  if ((to.path === '/login' || to.path === '/register') && auth.token) return '/home'
})

export default router
