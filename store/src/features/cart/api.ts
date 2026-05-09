// Cart + Checkout API
// Source: backend/orders/router.py:48-100, backend/orders/schemas/response.py

const API_BASE = '/api/v1'

// ── Types ────────────────────────────────────────────────────────────────────

export interface VariantSpec {
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: string | null
  detail: string | null
  color_count: number | null
}

export interface CartItem {
  id: string
  /** true = 客製作品（綁 custom_request_id 而非 product_variant） */
  is_custom: boolean
  variant_id: string | null
  product_id?: string | null
  product_title: string
  product_image_url?: string | null
  variant_image_url?: string | null
  thumb_url?: string | null
  variant_spec: VariantSpec | Record<string, never>
  /** 客製：對應的 custom_request id（非客製為 null）*/
  custom_request_id?: string | null
  /** 客製：admin 在 QuoteDialog 選定的 production_job */
  production_job_id?: string | null
  /** 客製：報價狀態 */
  quote_status?: string | null
  /** 客製：報價過期時間 */
  quote_expires_at?: string | null
  /** 客製：報價是否已過期（前端結帳前需警告） */
  quote_expired?: boolean
  unit_price: number
  quantity: number
  fulfilled_units: number
  preorder_units: number
  is_active: boolean
}

export interface CartResponse {
  items: CartItem[]
  subtotal: number
}

export interface CartItemMutationResponse {
  id: string
  variant_id?: string
  quantity?: number
  deleted?: boolean
}

export interface CheckoutPreviewSplitItem {
  cart_item_id: string
  fulfilled_units: number
  preorder_units: number
}

export interface CheckoutPreviewResponse {
  subtotal: number
  /** 一般商品 subtotal（免運門檻計算用，排除客製） */
  non_custom_subtotal?: number
  /** 一般商品總件數（免運門檻計算用） */
  non_custom_qty?: number
  /** cart 內過期的客製 line 數量（>0 → 結帳前需提醒移除/重新申請） */
  expired_custom_count?: number
  discount_amount: number
  discount_source: string | null
  shipping_fee: number
  total: number
  /** 'amount' / 'quantity' / 'coupon'（免運券）/ null */
  free_shipping_reason: string | null
  has_preorder: boolean
  split_items: CheckoutPreviewSplitItem[]
}

export type ShippingType = 'home' | 'convenience'
// 對應 backend ShippingPreferenceEnum：'together'（合併出貨）/ 'separate'（分開出貨）
export type ShippingPreference = 'together' | 'separate'

export interface CheckoutPreviewRequest {
  shipping_type: ShippingType
  user_coupon_id?: string | null
  promo_code?: string | null
}

export interface CreateOrderRequest {
  shipping_profile_id: string
  shipping_preference?: ShippingPreference | null
  user_coupon_id?: string | null
  promo_code?: string | null
  customer_notes?: string | null
}

export interface CreateOrderResponse {
  order_id: string
  order_number: string
  total: number
  payment_deadline: string  // ISO
  payment_info: {
    bank_name?: string
    account_no?: string
    account_name?: string
    note?: string
    [key: string]: string | undefined
  }
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

// ── Endpoints ────────────────────────────────────────────────────────────────

/** GET /cart — 取得購物車（需登入） */
export async function getCart(): Promise<CartResponse> {
  return jsonRequest<CartResponse>('/cart')
}

/** POST /cart/items — 加入商品到購物車 */
export async function addCartItem(variantId: string, quantity: number): Promise<CartItemMutationResponse> {
  return jsonRequest<CartItemMutationResponse>('/cart/items', {
    method: 'POST',
    body: JSON.stringify({ variant_id: variantId, quantity }),
  })
}

/** PATCH /cart/items/:id — 更新數量；quantity=0 等同刪除 */
export async function updateCartItem(itemId: string, quantity: number): Promise<CartItemMutationResponse> {
  return jsonRequest<CartItemMutationResponse>(`/cart/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify({ quantity }),
  })
}

/** DELETE /cart/items/:id — 刪除單筆 */
export async function deleteCartItem(itemId: string): Promise<void> {
  await jsonRequest<void>(`/cart/items/${itemId}`, {
    method: 'DELETE',
  })
}

/** POST /cart/checkout-preview — 結帳預覽（不開單，算稅／運費／折扣） */
export async function checkoutPreview(body: CheckoutPreviewRequest): Promise<CheckoutPreviewResponse> {
  return jsonRequest<CheckoutPreviewResponse>('/cart/checkout-preview', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** POST /orders — 建立訂單 */
export async function createOrder(body: CreateOrderRequest): Promise<CreateOrderResponse> {
  return jsonRequest<CreateOrderResponse>('/orders', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
