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
