import type { Router } from 'vue-router'
import { useAuthStore } from './store'

const PUBLIC_PATHS = [
  '/admin/login',
  '/admin/forgot-password',
  '/admin/reset-password',
]

function isPublic(path: string): boolean {
  return PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + '?'))
}

/**
 * Register router guards for admin auth.
 * Must be called AFTER pinia is installed on the app.
 */
export function registerAuthGuards(router: Router) {
  router.beforeEach((to) => {
    const auth = useAuthStore()

    // 已登入但訪問 login / forgot / reset → 直接送回 dashboard
    if (auth.isAuthenticated && isPublic(to.path)) {
      return { path: '/admin/dashboard' }
    }

    // 未登入訪問 protected route → 送 login，記住 next
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return {
        path: '/admin/login',
        query: { next: to.fullPath },
      }
    }

    // 已登入但角色錯誤（不是 admin）→ 強制登出 + flash
    if (auth.isAuthenticated && !auth.isAdmin && to.meta.requiresAuth) {
      auth.clear()
      sessionStorage.setItem('auth_flash', '此帳號非管理員')
      return { path: '/admin/login' }
    }

    return true
  })
}
