import { createRouter, createWebHistory } from 'vue-router'
import { authGuard } from '@/features/auth/guards'

import HomePage from '@/features/home/pages/HomePage.vue'
import ProductListPage from '@/features/products/pages/ProductListPage.vue'
import ProductDetailPage from '@/features/products/pages/ProductDetailPage.vue'
import SearchPage from '@/features/search/pages/SearchPage.vue'
import CartPage from '@/features/cart/pages/CartPage.vue'
import CheckoutPage from '@/features/checkout/pages/CheckoutPage.vue'
import CheckoutCompletePage from '@/features/checkout/pages/CheckoutCompletePage.vue'
import OrderListPage from '@/features/orders/pages/OrderListPage.vue'
import OrderDetailPage from '@/features/orders/pages/OrderDetailPage.vue'
import CustomPage from '@/features/custom/pages/CustomPage.vue'
import CustomAboutPage from '@/features/custom/pages/CustomAboutPage.vue'
import CustomCasesPage from '@/features/custom/pages/CustomCasesPage.vue'
import CustomApplyPage from '@/features/custom/pages/CustomApplyPage.vue'
import CustomRequestListPage from '@/features/custom/pages/CustomRequestListPage.vue'
import CustomRequestDetailPage from '@/features/custom/pages/CustomRequestDetailPage.vue'
import QuotePage from '@/features/custom/pages/QuotePage.vue'
import ProfilePage from '@/features/profile/pages/ProfilePage.vue'
import ShippingProfilesPage from '@/features/profile/pages/ShippingProfilesPage.vue'
import CouponsPage from '@/features/profile/pages/CouponsPage.vue'
import RegisterPage from '@/features/auth/pages/RegisterPage.vue'
import LoginPage from '@/features/auth/pages/LoginPage.vue'
import ForgotPasswordPage from '@/features/auth/pages/ForgotPasswordPage.vue'
import ResetPasswordPage from '@/features/auth/pages/ResetPasswordPage.vue'
import VerifyEmailPage from '@/features/auth/pages/VerifyEmailPage.vue'
import ThemeListPage from '@/features/themes/pages/ThemeListPage.vue'
import ThemeDetailPage from '@/features/themes/pages/ThemeDetailPage.vue'
import SeriesDetailPage from '@/features/themes/pages/SeriesDetailPage.vue'
import SizeGuidePage from '@/features/pages/SizeGuidePage.vue'
import ShippingInfoPage from '@/features/pages/ShippingInfoPage.vue'
import CustomProcessPage from '@/features/pages/CustomProcessPage.vue'
import PricingPage from '@/features/pages/PricingPage.vue'
import RefundPolicyPage from '@/features/pages/RefundPolicyPage.vue'
import NotFoundPage from '@/shared/components/NotFoundPage.vue'
import PaletteDebugPage from '@/features/dev/pages/PaletteDebugPage.vue'
import BandPickerPage from '@/features/dev/pages/BandPickerPage.vue'
import LayoutPickerPage from '@/features/dev/pages/LayoutPickerPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
  routes: [
    // ── Public — DefaultLayout ──────────────────────────────────────────
    { path: '/', name: 'home', component: HomePage, meta: { layout: 'default' } },
    { path: '/products', name: 'product-list', component: ProductListPage, meta: { layout: 'default' } },
    { path: '/products/:id', name: 'product-detail', component: ProductDetailPage, meta: { layout: 'default' } },
    { path: '/search', name: 'search', component: SearchPage, meta: { layout: 'default' } },
    { path: '/themes', name: 'theme-list', component: ThemeListPage, meta: { layout: 'default' } },
    { path: '/themes/:id', name: 'theme-detail', component: ThemeDetailPage, meta: { layout: 'default' } },
    { path: '/series/:id', name: 'series-detail', component: SeriesDetailPage, meta: { layout: 'default' } },
    { path: '/custom', name: 'custom', component: CustomPage, meta: { layout: 'default' } },
    { path: '/custom/about', name: 'custom-about', component: CustomAboutPage, meta: { layout: 'default' } },
    { path: '/custom/cases', name: 'custom-cases', component: CustomCasesPage, meta: { layout: 'default' } },
    { path: '/custom/apply', name: 'custom-apply', component: CustomApplyPage, meta: { layout: 'default' } },
    { path: '/size-guide', name: 'size-guide', component: SizeGuidePage, meta: { layout: 'default' } },
    { path: '/shipping-info', name: 'shipping-info', component: ShippingInfoPage, meta: { layout: 'default' } },
    { path: '/custom-process', name: 'custom-process', component: CustomProcessPage, meta: { layout: 'default' } },
    { path: '/pricing', name: 'pricing', component: PricingPage, meta: { layout: 'default' } },
    { path: '/refund-policy', name: 'refund-policy', component: RefundPolicyPage, meta: { layout: 'default' } },

    // ── Auth required — DefaultLayout ────────────────────────────────────
    { path: '/cart', name: 'cart', component: CartPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/checkout', name: 'checkout', component: CheckoutPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/checkout/complete', name: 'checkout-complete', component: CheckoutCompletePage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/orders', name: 'order-list', component: OrderListPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/orders/:id', name: 'order-detail', component: OrderDetailPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/custom/requests', name: 'custom-request-list', component: CustomRequestListPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/custom/requests/:id', name: 'custom-request-detail', component: CustomRequestDetailPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/profile', name: 'profile', component: ProfilePage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/profile/shipping', name: 'profile-shipping', component: ShippingProfilesPage, meta: { layout: 'default', requiresAuth: true } },
    { path: '/profile/coupons', name: 'profile-coupons', component: CouponsPage, meta: { layout: 'default', requiresAuth: true } },

    // ── Quote token (公開、不需登入) — MinimalLayout ─────────────────────
    { path: '/custom/quote/:token', name: 'quote', component: QuotePage, meta: { layout: 'minimal' } },

    // ── Auth pages — AuthLayout ─────────────────────────────────────────
    { path: '/register', name: 'register', component: RegisterPage, meta: { layout: 'auth', guestOnly: true } },
    { path: '/login', name: 'login', component: LoginPage, meta: { layout: 'auth', guestOnly: true } },
    { path: '/forgot-password', name: 'forgot-password', component: ForgotPasswordPage, meta: { layout: 'auth', guestOnly: true } },
    { path: '/reset-password/:token', name: 'reset-password', component: ResetPasswordPage, meta: { layout: 'auth' } },
    { path: '/reset-password', name: 'reset-password-query', component: ResetPasswordPage, meta: { layout: 'auth' } },
    { path: '/verify-email/:token', name: 'verify-email', component: VerifyEmailPage, meta: { layout: 'auth' } },
    { path: '/verify-email', name: 'verify-email-query', component: VerifyEmailPage, meta: { layout: 'auth' } },

    // ── Dev palette overview ─────────────────────────────────────────────
    { path: '/_palette', name: 'palette', component: PaletteDebugPage, meta: { layout: 'minimal' } },
    { path: '/_band-picker', name: 'band-picker', component: BandPickerPage, meta: { layout: 'minimal' } },
    { path: '/_layout-picker', name: 'layout-picker', component: LayoutPickerPage, meta: { layout: 'default' } },

    // ── 404 catch-all ────────────────────────────────────────────────────
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundPage, meta: { layout: 'default' } },
  ],
})

router.beforeEach(authGuard)
