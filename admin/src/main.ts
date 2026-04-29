import { createApp } from 'vue'

import App from './App.vue'
import { pinia } from './app/pinia'
import { VueQueryPlugin, vueQueryPluginOptions } from './app/query'
import { router } from './app/router'
import { registerAuthGuards } from './features/auth/guards'
import { useAuthStore } from './features/auth/store'
import { fetchMe } from './features/auth/api'
import './style.css'

const app = createApp(App)

app.use(pinia)

// Boot-time: 先把 session 還原到 store，再 install router。
// 如果先 install router、再 await fetchMe，guard 在初次 navigation
// 時讀到的 auth.isAuthenticated 仍是 false，會把 protected route 踢回登入頁。
;(async () => {
  const auth = useAuthStore()

  if (import.meta.env.DEV && import.meta.env.VITE_DEV_BYPASS_AUTH === 'true') {
    console.warn('[DEV] Auth bypass active — using fake admin user')
    auth.setUser({
      id: 'dev-admin',
      name: '易木 Dev',
      email: 'yizn.min@gmail.com',
      role: 'admin',
      pending_email: null,
      gender: null,
      birthday: null,
    })
  } else {
    try {
      const me = await fetchMe()
      auth.setUser(me)
    } catch {
      // 401 / network — leave user null; guard will redirect to /admin/login
    }
  }

  app.use(router)
  app.use(VueQueryPlugin, vueQueryPluginOptions)
  registerAuthGuards(router)
  await router.isReady()
  app.mount('#app')
})()
