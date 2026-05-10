// User profile + shipping profile API
// Source: backend/users/router.py + backend/discount/router.py (coupons)

const API_BASE = '/api/v1'

// ── User profile types ───────────────────────────────────────────────────────

export type Gender = 'female' | 'male' | 'other'

export interface UserProfile {
  id: string
  name: string
  email: string
  pending_email: string | null
  role: string
  gender: Gender | null
  birthday: string | null  // 'YYYY-MM-DD'
}

export interface UpdateProfilePayload {
  name?: string
  gender?: Gender | null
  birthday?: string | null
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

// ── Coupon types ─────────────────────────────────────────────────────────────

export type CouponType = 'new_user' | 'promo' | 'shipping' | 'reward'
export type DiscountType = 'fixed_amount' | 'percentage' | 'free_shipping'

export interface UserCoupon {
  id: string
  coupon_type: CouponType | null
  discount_type: DiscountType
  discount_value: number
  min_purchase: number | null
  expires_at: string | null
}

export interface UserCouponsListResponse {
  available: UserCoupon[]
  used: UserCoupon[]
  expired: UserCoupon[]
}

export type ShippingType = 'home' | 'seven_eleven' | 'family_mart'

export interface ShippingProfile {
  id: string
  shipping_type: ShippingType
  recipient_name: string
  phone: string
  email: string | null
  city: string | null
  district: string | null
  address_detail: string | null
  store_id: string | null
  store_name: string | null
  is_default: boolean
}

export interface ShippingProfileInput {
  shipping_type: ShippingType
  recipient_name: string
  phone: string
  email?: string | null
  city?: string | null
  district?: string | null
  address_detail?: string | null
  store_id?: string | null
  store_name?: string | null
  is_default?: boolean
}

export interface ApiError extends Error {
  status: number
  detail: string
}

async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b?.detail ?? b?.message ?? `${res.status}`)
      .catch(() => `${res.status}`)
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)) as ApiError
    err.status = res.status
    err.detail = typeof detail === 'string' ? detail : JSON.stringify(detail)
    throw err
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function listShippingProfiles(): Promise<ShippingProfile[]> {
  return jsonRequest<ShippingProfile[]>('/users/me/shipping-profiles')
}

export async function createShippingProfile(data: ShippingProfileInput): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>('/users/me/shipping-profiles', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateShippingProfile(
  id: string,
  data: ShippingProfileInput,
): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>(`/users/me/shipping-profiles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteShippingProfile(id: string): Promise<void> {
  await jsonRequest<void>(`/users/me/shipping-profiles/${id}`, {
    method: 'DELETE',
  })
}

export async function setDefaultShippingProfile(id: string): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>(
    `/users/me/shipping-profiles/${id}/set-default`,
    { method: 'PATCH' },
  )
}

// ── Personal profile ─────────────────────────────────────────────────────────

export async function fetchProfile(): Promise<UserProfile> {
  // /auth/me 已存在於 auth store；這個 wrapper 給 ProfilePage 直接用，避免依賴 store
  return jsonRequest<UserProfile>('/auth/me')
}

export async function updateProfile(data: UpdateProfilePayload): Promise<UserProfile> {
  return jsonRequest<UserProfile>('/users/me', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function changePassword(data: ChangePasswordPayload): Promise<void> {
  await jsonRequest<void>('/users/me/change-password', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function requestEmailChange(new_email: string): Promise<{ message: string }> {
  return jsonRequest<{ message: string }>('/users/me/request-email-change', {
    method: 'POST',
    body: JSON.stringify({ new_email }),
  })
}

export async function resendEmailChangeVerification(): Promise<{ message: string }> {
  return jsonRequest<{ message: string }>(
    '/users/me/resend-email-change-verification',
    { method: 'POST' },
  )
}

// ── Coupons ──────────────────────────────────────────────────────────────────

export async function listUserCoupons(): Promise<UserCouponsListResponse> {
  return jsonRequest<UserCouponsListResponse>('/users/me/coupons')
}

// ── Member dashboard stats ──────────────────────────────────────────────────

export interface MemberStats {
  orders_total: number
  orders_completed: number
  orders_pending_payment: number
  available_coupons: number
  custom_quote_pending: number
}

export async function fetchMemberStats(): Promise<MemberStats> {
  return jsonRequest<MemberStats>('/users/me/stats')
}
