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
      {
        path: 'orders/:id',
        name: 'admin-orders-detail',
        component: () => import('@/features/orders/pages/OrderDetailPage.vue'),
      },
      {
        path: 'custom-requests',
        name: 'admin-custom-requests',
        component: () => import('@/features/custom_requests/pages/CustomRequestsListPage.vue'),
      },
      {
        path: 'custom-requests/:id',
        name: 'admin-custom-requests-detail',
        component: () => import('@/features/custom_requests/pages/CustomRequestDetailPage.vue'),
      },
      {
        path: 'production',
        name: 'admin-production',
        component: () => import('@/features/production/pages/ProductionListPage.vue'),
      },
      {
        path: 'production/new',
        name: 'admin-production-new',
        component: () => import('@/features/production/pages/ProductionNewPage.vue'),
      },
      {
        path: 'production/:jobId',
        name: 'admin-production-detail',
        component: () => import('@/features/production/pages/ProductionJobDetailPage.vue'),
      },
      {
        path: 'discounts',
        name: 'admin-discounts',
        component: () => import('@/features/discounts/pages/DiscountsPage.vue'),
      },
      {
        path: 'discounts/configs/:id/stats',
        name: 'admin-discounts-stats',
        component: () => import('@/features/discounts/pages/CouponConfigStatsPage.vue'),
      },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('@/features/admin_users/pages/UsersListPage.vue'),
      },
      {
        path: 'users/:id',
        name: 'admin-users-detail',
        component: () => import('@/features/admin_users/pages/UserDetailPage.vue'),
      },
      {
        path: 'content',
        name: 'admin-content',
        component: () => import('@/features/content/pages/ContentPage.vue'),
      },
      {
        path: 'reports',
        name: 'admin-reports',
        component: () => import('@/features/reports/pages/ReportsPage.vue'),
      },
      {
        path: 'colors',
        name: 'admin-colors',
        component: () => import('@/features/colors/pages/ColorsListPage.vue'),
      },
      {
        path: 'colors/mapping/:jobId',
        name: 'admin-colors-mapping',
        component: () => import('@/features/colors/pages/PaletteMappingPage.vue'),
      },
      {
        path: 'print-batches',
        name: 'admin-print-batches',
        component: () => import('@/features/print_batches/pages/PrintBatchesListPage.vue'),
      },
      {
        path: 'print-batches/new',
        name: 'admin-print-batches-new',
        component: () => import('@/features/print_batches/pages/PrintBatchNewPage.vue'),
      },
      {
        path: 'print-batches/:id',
        name: 'admin-print-batches-detail',
        component: () => import('@/features/print_batches/pages/PrintBatchDetailPage.vue'),
      },
      {
        path: 'notifications',
        name: 'admin-notifications',
        component: () => import('@/features/notifications/pages/NotificationsPage.vue'),
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
