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
app.use(router)
app.use(VueQueryPlugin, vueQueryPluginOptions)

// Register auth guards (must be after pinia/router installed)
registerAuthGuards(router)

// Boot-time: try to restore session via /auth/me before mounting.
// If successful, isAuthenticated=true; guards then let admin paths through.
//
// DEV bypass: 後端尚未串接時，import.meta.env.VITE_DEV_BYPASS_AUTH=true
// 會直接塞一個 fake admin user，跳過 fetchMe，讓 admin layout 可以逛。
// 這是 dev-only — production build 會 strip 這段。
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
    app.mount('#app')
    return
  }

  try {
    const me = await fetchMe()
    auth.setUser(me)
  } catch {
    // 401 / network — leave user null; guard will redirect to /admin/login
  }
  app.mount('#app')
})()
