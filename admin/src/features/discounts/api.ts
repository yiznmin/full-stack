/**
 * Discounts API wrappers — F08 折扣管理（admin）。
 */

const API = '/api/v1'

interface ApiError {
  message: string
  code?: string
  status: number
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
    ...init,
  })

  if (res.status === 204) return null as unknown as T

  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err: ApiError = {
      message: body.message || body.detail || `HTTP ${res.status}`,
      code: body.code,
      status: res.status,
    }
    throw err
  }
  return body
}

// ── Types ─────────────────────────────────────────────────────────────

export type CouponType =
  | 'new_user'
  | 'spend_reward'
  | 'returning_loyal'
  | 'manual'
  | 'auto_checkout'

export type DiscountType = 'percentage' | 'fixed'

export interface CouponConfig {
  id: string
  coupon_type: CouponType
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  is_active: boolean
  params: Record<string, unknown>
  updated_at: string
}

export interface CouponConfigListResponse {
  items: CouponConfig[]
}

export interface PatchCouponConfigPayload {
  is_active?: boolean | null
  discount_type?: DiscountType | null
  discount_value?: number | null
  min_purchase?: number | null
  params?: Record<string, unknown> | null
}

export interface CreateAutoCheckoutPayload {
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  params: {
    trigger_threshold?: number
    start_at?: string | null
    end_at?: string | null
    [k: string]: unknown
  }
}

export interface CouponConfigUsageStats {
  total_issued: number
  total_used: number
  total_discount_amount: number
  usage_by_month: { month: string; issued: number; used: number; discount_amount: number }[]
}

export interface PromoCode {
  id: string
  code: string
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  start_at: string | null
  end_at: string | null
  max_total_uses: number | null
  max_per_user: number
  total_used: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PromoCodeListResponse {
  items: PromoCode[]
}

export interface CreatePromoCodePayload {
  code: string
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  start_at: string | null
  end_at: string | null
  max_total_uses: number | null
  max_per_user: number
}

export interface UpdatePromoCodePayload {
  code?: string | null
  discount_type?: DiscountType | null
  discount_value?: number | null
  min_purchase?: number | null
  start_at?: string | null
  end_at?: string | null
  max_total_uses?: number | null
  max_per_user?: number | null
  is_active?: boolean | null
}

export interface AdminUserCoupon {
  id: string
  user_id: string
  coupon_type: CouponType | null
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  expires_at: string | null
  is_used: boolean
  used_at: string | null
  created_at: string
}

export interface AdminUserCouponListResponse {
  items: AdminUserCoupon[]
}

export interface UserCouponsParams {
  user_id?: string
  coupon_type?: CouponType
  is_used?: boolean
}

export interface IssueCouponsPayload {
  user_ids: string[]
  coupon_config_id: string
}

export interface IssueCouponsResponse {
  issued_count: number
  coupon_config_id: string
  coupon_type: string
  discount_type: string
  discount_value: number
  expires_at: string | null
  user_ids: string[]
}

// ── Endpoints ─────────────────────────────────────────────────────────

export function listCouponConfigs() {
  return request<CouponConfigListResponse>('/admin/coupon-configs')
}

export function patchCouponConfig(id: string, payload: PatchCouponConfigPayload) {
  return request<CouponConfig>(`/admin/coupon-configs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createAutoCheckout(payload: CreateAutoCheckoutPayload) {
  return request<CouponConfig>('/admin/coupon-configs/auto-checkout', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteCouponConfig(id: string) {
  return request<void>(`/admin/coupon-configs/${id}`, { method: 'DELETE' })
}

export function getCouponConfigStats(id: string) {
  return request<CouponConfigUsageStats>(`/admin/coupon-configs/${id}/usage-stats`)
}

export function listPromoCodes() {
  return request<PromoCodeListResponse>('/admin/promo-codes')
}

export function createPromoCode(payload: CreatePromoCodePayload) {
  return request<PromoCode>('/admin/promo-codes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePromoCode(id: string, payload: UpdatePromoCodePayload) {
  return request<PromoCode>(`/admin/promo-codes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deletePromoCode(id: string) {
  return request<void>(`/admin/promo-codes/${id}`, { method: 'DELETE' })
}

export function listUserCoupons(params: UserCouponsParams = {}) {
  const q = new URLSearchParams()
  if (params.user_id) q.set('user_id', params.user_id)
  if (params.coupon_type) q.set('coupon_type', params.coupon_type)
  if (params.is_used !== undefined) q.set('is_used', String(params.is_used))
  const qs = q.toString()
  return request<AdminUserCouponListResponse>(`/admin/user-coupons${qs ? '?' + qs : ''}`)
}

export function issueCoupons(payload: IssueCouponsPayload) {
  return request<IssueCouponsResponse>('/admin/users/issue-coupons', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Labels ────────────────────────────────────────────────────────────

export const COUPON_TYPE_LABEL: Record<CouponType, string> = {
  new_user: '新用戶歡迎券',
  spend_reward: '滿額回饋券',
  returning_loyal: '回頭客忠誠券',
  manual: '手動發放',
  auto_checkout: '結帳自動促銷',
}

export const DISCOUNT_TYPE_LABEL: Record<DiscountType, string> = {
  percentage: '百分比',
  fixed: '固定金額',
}

export function formatDiscount(type: DiscountType, value: number): string {
  if (type === 'percentage') {
    // discount_value 為 10 表示打 9 折（折扣 10%）
    return `折扣 ${value}%`
  }
  return `折 NT$ ${Number(value).toLocaleString('zh-TW')}`
}
