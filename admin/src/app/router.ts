import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/admin/dashboard',
  },
  // ── Auth pages — public, AuthLayout
  {
    path: '/admin',
    component: () => import('@/shared/layouts/AuthLayout.vue'),
    children: [
      {
        path: 'login',
        name: 'admin-login',
        component: () => import('@/features/auth/pages/LoginPage.vue'),
      },
      {
        path: 'forgot-password',
        name: 'admin-forgot-password',
        component: () => import('@/features/auth/pages/ForgotPasswordPage.vue'),
      },
      {
        path: 'reset-password',
        name: 'admin-reset-password',
        component: () => import('@/features/auth/pages/ResetPasswordPage.vue'),
      },
    ],
  },
  // ── Admin pages — auth-required, AdminLayout (sidebar + header)
  {
    path: '/admin',
    component: () => import('@/shared/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/admin/dashboard',
      },
      {
        path: 'dashboard',
        name: 'admin-dashboard',
        component: () => import('@/features/dashboard/pages/DashboardHome.vue'),
      },
      {
        path: 'products',
        name: 'admin-products',
        component: () => import('@/features/products/pages/ProductsListPage.vue'),
      },
      {
        path: 'products/new',
        name: 'admin-products-new',
        component: () => import('@/features/products/pages/ProductFormPage.vue'),
      },
      {
        path: 'products/themes',
        name: 'admin-products-themes',
        component: () => import('@/features/products/pages/ThemesAdminPage.vue'),
      },
      {
        path: 'products/series',
        name: 'admin-products-series',
        component: () => import('@/features/products/pages/SeriesAdminPage.vue'),
      },
      {
        path: 'products/tags',
        name: 'admin-products-tags',
        component: () => import('@/features/products/pages/TagsAdminPage.vue'),
      },
      {
        path: 'products/:id',
        name: 'admin-products-edit',
        component: () => import('@/features/products/pages/ProductFormPage.vue'),
      },
      {
        path: 'orders',
        name: 'admin-orders',
        component: () => import('@/features/orders/pages/OrdersListPage.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/features/dashboard/pages/NotFoundPage.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
