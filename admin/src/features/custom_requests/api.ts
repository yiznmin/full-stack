/**
 * Custom Requests API wrappers — F05 客製訂單管理（admin）。
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

export type CustomStatus =
  | 'quote_pending'
  | 'negotiating'
  | 'quote_sent'
  | 'draft_revision'
  | 'quote_confirmed'
  | 'quote_rejected'
  | 'quote_expired'

export type RequestType = 'custom_photo' | 'custom_spec'

export type Difficulty = 'beginner' | 'elementary' | 'intermediate' | 'advanced'

export type Detail = 'rough' | 'standard' | 'detailed' | 'premium'

export type MessageSender = 'admin' | 'customer'

export interface CustomRequestMessage {
  id: string
  request_id: string
  sender_type: MessageSender
  message: string
  created_at: string
}

export interface CustomRequestSummary {
  id: string
  request_type: RequestType
  status: CustomStatus
  user_id: string
  user_name: string
  user_email: string
  quoted_price: number | null
  quote_expires_at: string | null
  revision_count: number
  created_at: string
}

export interface CustomRequestsListResponse {
  items: CustomRequestSummary[]
  total: number
  page: number
  page_size: number
}

export interface CustomRequestsListParams {
  status?: CustomStatus | ''
  request_type?: RequestType | ''
  page?: number
  page_size?: number
}

export interface CustomRequestDetail {
  id: string
  user_id: string
  user_name: string
  user_email: string
  request_type: RequestType
  status: CustomStatus
  photo_url: string | null
  ref_product_id: string | null
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: Difficulty | null
  detail: Detail | null
  customer_notes: string | null
  admin_notes: string | null
  quoted_price: number | null
  quote_expires_at: string | null
  is_extended: boolean
  revision_count: number
  parent_request_id: string | null
  order_id: string | null
  created_at: string
  quoted_at: string | null
  rejected_at: string | null
  messages: CustomRequestMessage[]
}

export interface PhotoSignedUrlResponse {
  url: string
  expires_at: string
}

export interface QuotePayload {
  quoted_price: number
  detail: Detail
  surcharge_ids: string[]
  quote_note?: string | null
}

export interface QuoteResponse {
  quote_expires_at: string
}

export interface MessagePayload {
  message: string
}

// 加費 / 基礎價格表（admin 端報價試算用）
export interface CustomPhotoPrice {
  id: string
  canvas_w: number
  canvas_h: number
  difficulty: Difficulty
  price: number
}

export interface CustomPhotoPriceListResponse {
  items: CustomPhotoPrice[]
}

export interface CustomPhotoSurcharge {
  id: string
  category: string
  label: string
  amount: number
  is_active: boolean
  created_at: string
}

export interface CustomPhotoSurchargeListResponse {
  items: CustomPhotoSurcharge[]
}

// ── List ──────────────────────────────────────────────────────────────

export function listCustomRequests(params: CustomRequestsListParams = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.request_type) q.set('request_type', params.request_type)
  q.set('page', String(params.page ?? 1))
  q.set('page_size', String(params.page_size ?? 20))
  return request<CustomRequestsListResponse>(`/admin/custom-requests?${q.toString()}`)
}

// ── Detail ────────────────────────────────────────────────────────────

export function getCustomRequest(id: string) {
  return request<CustomRequestDetail>(`/admin/custom-requests/${id}`)
}

export function getPhotoSignedUrl(id: string) {
  return request<PhotoSignedUrlResponse>(`/admin/custom-requests/${id}/photo-signed-url`)
}

export function markNegotiating(id: string) {
  return request<CustomRequestDetail>(`/admin/custom-requests/${id}/mark-negotiating`, {
    method: 'PATCH',
  })
}

export function postMessage(id: string, payload: MessagePayload) {
  return request<CustomRequestMessage>(`/admin/custom-requests/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function postQuote(id: string, payload: QuotePayload) {
  return request<QuoteResponse>(`/admin/custom-requests/${id}/quote`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Quote 試算用：基礎價格 + 加費表 ──────────────────────────────────

export function listCustomPhotoPrices() {
  return request<CustomPhotoPriceListResponse>('/admin/custom-photo-prices')
}

export function listCustomPhotoSurcharges() {
  return request<CustomPhotoSurchargeListResponse>('/admin/custom-photo-surcharges')
}
