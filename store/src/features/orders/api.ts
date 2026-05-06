// Orders API
// Source: backend/orders/router.py:103-208 (customer endpoints)

const API_BASE = '/api/v1'

export type OrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'in_production'
  | 'shipping'
  | 'delivered'
  | 'completed'
  | 'cancelled'
  | 'refunded'

export interface OrderListItem {
  id: string
  order_number: string
  status: OrderStatus
  total: number
  item_count: number
  created_at: string
}

export interface OrderListResponse {
  items: OrderListItem[]
  total: number
  page: number
  page_size: number
}

export interface ProductionProgress {
  id: string
  order_item_id: string
  status: string
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
  shipment_type: string
  status: string
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

export interface OrderDetail {
  id: string
  order_number: string
  status: OrderStatus
  subtotal: number
  discount_amount: number
  discount_source: string | null
  shipping_fee: number
  total: number
  shipping_type: 'home' | 'convenience'
  shipping_preference: 'merge' | 'split' | null
  shipping_snapshot: {
    recipient_name?: string
    phone?: string
    city?: string
    district?: string
    address_detail?: string
    store_id?: string
    store_name?: string
    [k: string]: string | undefined
  }
  payment_deadline: string | null
  paid_at: string | null
  completed_at: string | null
  cancel_reason_code: string | null
  cancel_reason_note: string | null
  refund_amount: number | null
  refunded_at: string | null
  refund_confirmed_at: string | null
  customer_notes: string | null
  items: OrderItem[]
  shipments: Shipment[]
  payment_submissions: PaymentSubmission[]
  can_cancel: boolean
  can_confirm_received: boolean
  created_at: string
}

// 建單時 payment_info 格式（來自 service.py 的 system_settings）
export interface PaymentInfo {
  bank_name?: string
  account_no?: string
  account_name?: string
  branch?: string
  note?: string
  [k: string]: string | undefined
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

export async function listOrders(
  status?: string,
  page = 1,
  pageSize = 20,
): Promise<OrderListResponse> {
  const q = new URLSearchParams()
  if (status) q.set('status', status)
  q.set('page', String(page))
  q.set('page_size', String(pageSize))
  return jsonRequest<OrderListResponse>(`/orders?${q.toString()}`)
}

export async function getOrder(id: string): Promise<OrderDetail> {
  return jsonRequest<OrderDetail>(`/orders/${id}`)
}

// ── Payment / Cancel / Confirm Received ─────────────────────────

export interface PaymentSubmissionInput {
  transfer_amount: number
  transfer_date: string  // YYYY-MM-DD
  transfer_time: string  // HH:MM:SS or HH:MM
  account_last5: string
  notes?: string | null
}

export async function submitPayment(
  orderId: string,
  data: PaymentSubmissionInput,
): Promise<PaymentSubmission> {
  return jsonRequest<PaymentSubmission>(`/orders/${orderId}/payment-submission`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface ConfirmReceivedResponse {
  id: string
  order_number: string
  status: OrderStatus
  completed_at: string | null
}

export async function confirmReceived(orderId: string): Promise<ConfirmReceivedResponse> {
  return jsonRequest<ConfirmReceivedResponse>(`/orders/${orderId}/confirm-received`, {
    method: 'POST',
  })
}

export interface CancelOrderResponse {
  id: string
  order_number: string
  status: OrderStatus
  cancel_reason_code: string | null
  cancel_reason_note: string | null
  refund_amount: number | null
  refunded_at: string | null
}

export async function cancelOrder(
  orderId: string,
  cancelReason: string,
): Promise<CancelOrderResponse> {
  return jsonRequest<CancelOrderResponse>(`/orders/${orderId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ cancel_reason: cancelReason }),
  })
}
