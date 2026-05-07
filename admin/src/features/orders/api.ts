/**
 * Orders API wrappers — F04 訂單管理（admin）。
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

export type OrderStatus =
  | 'pending_payment'
  | 'payment_expired'
  | 'paid'
  | 'processing'
  | 'shipped'
  | 'completed'
  | 'cancelled'
  | 'refund_processing'
  | 'refunded'
  | 'partially_refunded'

export type OrderTypeFilter = 'regular' | 'custom'

export interface OrderListItem {
  id: string
  order_number: string
  user_id: string
  user_name: string
  user_email: string
  status: OrderStatus
  total: number
  item_count: number
  created_at: string
}

export interface OrdersListResponse {
  items: OrderListItem[]
  total: number
  page: number
  page_size: number
}

export interface OrdersListParams {
  search?: string
  status?: OrderStatus | ''
  date_from?: string
  date_to?: string
  order_type?: OrderTypeFilter | ''
  page?: number
  page_size?: number
}

// ── Detail types ──────────────────────────────────────────────────────

export type ShipmentType = 'fulfilled' | 'preorder'
export type ShipmentStatus = 'pending' | 'shipped' | 'delivered'
export type ShippingType = 'home' | 'seven_eleven' | 'family_mart'
export type ShippingPreference = 'together' | 'separate'
export type ProductionProgressStatus =
  | 'pending'
  | 'in_production'
  | 'manufacturing'
  | 'packaging'
  | 'ready_to_ship'
  | 'shipped'
export type DiscountSource = 'coupon' | 'auto_checkout'
export type CancelReasonCode = 'payment_expired' | 'customer_cancelled' | 'admin_cancelled'

export interface ProductionProgress {
  id: string
  order_item_id: string
  status: ProductionProgressStatus
  notes: string | null
  updated_at: string
}

export interface OrderItem {
  id: string
  product_variant_id: string | null
  product_title_snapshot: string
  variant_spec_snapshot: Record<string, unknown>
  unit_price: number
  quantity: number
  fulfilled_qty: number
  preorder_qty: number
  is_returned: boolean
  production_progress: ProductionProgress | null
}

export interface Shipment {
  id: string
  shipment_type: ShipmentType
  status: ShipmentStatus
  tracking_number: string | null
  shipped_at: string | null
  delivered_at: string | null
}

export interface PaymentSubmission {
  id: string
  transfer_amount: number
  transfer_date: string
  transfer_time: string
  account_last5: string
  is_flagged: boolean
  notes: string | null
  created_at: string
}

export interface ShippingSnapshot {
  recipient_name: string
  phone: string
  notify_email: string | null
  city?: string
  district?: string
  address_detail?: string
  store_id?: string | null
  store_name?: string | null
  [k: string]: unknown
}

export interface OrderDetail {
  id: string
  order_number: string
  user_id: string
  user_name: string
  user_email: string
  status: OrderStatus
  subtotal: number
  discount_amount: number
  discount_source: DiscountSource | null
  auto_checkout_config_id: string | null
  shipping_fee: number
  total: number
  shipping_type: ShippingType
  shipping_preference: ShippingPreference | null
  shipping_snapshot: ShippingSnapshot
  shipping_locked: boolean
  payment_deadline: string | null
  paid_at: string | null
  completed_at: string | null
  cancel_reason_code: CancelReasonCode | null
  cancel_reason_note: string | null
  refund_amount: number | null
  refunded_at: string | null
  refund_confirmed_at: string | null
  customer_notes: string | null
  admin_notes: string | null
  items: OrderItem[]
  shipments: Shipment[]
  payment_submissions: PaymentSubmission[]
  created_at: string
}

// ── Request payloads ──────────────────────────────────────────────────

export interface UpdateOrderStatusPayload {
  status:
    | 'paid'
    | 'processing'
    | 'shipped'
    | 'completed'
    | 'refund_processing'
    | 'cancelled'
  admin_notes?: string | null
}

export interface CreateShipmentPayload {
  shipment_type: ShipmentType
}

export interface UpdateProductionProgressPayload {
  status: 'manufacturing' | 'packaging' | 'ready_to_ship'
  notes?: string | null
}

export interface FlagPaymentSubmissionPayload {
  is_flagged: true
  admin_note: string
}

export interface RefundOrderPayload {
  refund_amount: number
  returned_item_ids: string[]
  cancel_reason: string
}

export interface AdminNotesPayload {
  admin_notes: string
}

// ── List ──────────────────────────────────────────────────────────────

export function listOrders(params: OrdersListParams = {}) {
  const q = new URLSearchParams()
  if (params.search) q.set('search', params.search)
  if (params.status) q.set('status', params.status)
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to) q.set('date_to', params.date_to)
  if (params.order_type) q.set('order_type', params.order_type)
  q.set('page', String(params.page ?? 1))
  q.set('page_size', String(params.page_size ?? 20))
  return request<OrdersListResponse>(`/admin/orders?${q.toString()}`)
}

// ── Detail ────────────────────────────────────────────────────────────

export function getOrder(id: string) {
  return request<OrderDetail>(`/admin/orders/${id}`)
}

export function updateOrderStatus(id: string, payload: UpdateOrderStatusPayload) {
  return request<OrderDetail>(`/admin/orders/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createShipment(id: string, payload: CreateShipmentPayload) {
  return request<{ shipment_id: string; tracking_number: string; ecpay_logistics_id: string }>(
    `/admin/orders/${id}/shipments`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export interface BatchShipmentResultItem {
  order_id: string
  ok: boolean
  tracking_number: string | null
  ecpay_logistics_id: string | null
  error: string | null
}

export interface BatchCreateShipmentResponse {
  total: number
  success: number
  failed: number
  results: BatchShipmentResultItem[]
}

export interface BatchCreateShipmentPayload {
  order_ids: string[]
  shipment_type?: ShipmentType
}

export function batchCreateShipments(payload: BatchCreateShipmentPayload) {
  return request<BatchCreateShipmentResponse>(
    '/admin/shipments/batch-create',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export interface UpdateShippingPayload {
  recipient_name?: string
  phone?: string
  email?: string | null
  city?: string | null
  district?: string | null
  address_detail?: string | null
  store_id?: string | null
  store_name?: string | null
}

export function adminUpdateShipping(orderId: string, payload: UpdateShippingPayload) {
  return request<OrderDetail>(`/admin/orders/${orderId}/shipping`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function adminLockShipping(orderId: string) {
  return request<OrderDetail>(`/admin/orders/${orderId}/lock-shipping`, {
    method: 'POST',
  })
}

export function updateProductionProgress(
  orderId: string,
  progressId: string,
  payload: UpdateProductionProgressPayload,
) {
  return request<ProductionProgress>(
    `/admin/orders/${orderId}/production-progress/${progressId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function flagPaymentSubmission(
  orderId: string,
  submissionId: string,
  payload: FlagPaymentSubmissionPayload,
) {
  return request<{ payment_deadline: string }>(
    `/admin/orders/${orderId}/payment-submissions/${submissionId}/flag`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

export function refundOrder(id: string, payload: RefundOrderPayload) {
  return request<OrderDetail>(`/admin/orders/${id}/refund`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdminNotes(id: string, payload: AdminNotesPayload) {
  return request<OrderDetail>(`/admin/orders/${id}/admin-notes`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
