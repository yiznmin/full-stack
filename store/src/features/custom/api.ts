// Custom (客製化服務) API
// Source: backend/custom/router.py + backend/custom/schemas/response.py
// Spec: docs/api.md L1016-L1124

const API_BASE = '/api/v1'

// ── Enums ────────────────────────────────────────────────────────────────────

export type RequestType = 'custom_photo' | 'custom_spec'

export type RequestStatus =
  | 'quote_pending'      // 收到，等 admin 回報價
  | 'negotiating'        // admin 已標記洽談中
  | 'quote_sent'         // 報價已送出，客戶可確認 / 拒絕 / 要求修改 / 延長
  | 'draft_revision'     // 客戶要求修改，回到 admin 端重做
  | 'quote_confirmed'    // 客戶已確認，已開單
  | 'quote_rejected'     // 客戶拒絕報價
  | 'quote_expired'      // 24h 內未確認，自動逾期

export type Difficulty = 'beginner' | 'elementary' | 'intermediate' | 'advanced'
export type Detail = 'rough' | 'standard' | 'detailed' | 'premium'
export type SenderType = 'admin' | 'customer'

// ── Types ────────────────────────────────────────────────────────────────────

export interface CustomMessage {
  id: string
  request_id: string
  sender_type: SenderType
  message: string
  image_url: string | null
  created_at: string
}

export interface CustomRequestSummary {
  id: string
  request_type: RequestType
  status: RequestStatus
  quoted_price: number | null
  quote_expires_at: string | null
  is_extended: boolean
  revision_count: number
  order_id: string | null
  created_at: string
}

export interface CustomRequestListResponse {
  items: CustomRequestSummary[]
  total: number
  page: number
  page_size: number
}

export interface CustomRequestDetail {
  id: string
  user_id: string
  request_type: RequestType
  status: RequestStatus
  photo_url: string | null
  ref_product_id: string | null
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: Difficulty | null
  detail: Detail | null
  customer_notes: string | null
  quoted_price: number | null
  quote_expires_at: string | null
  is_extended: boolean
  revision_count: number
  parent_request_id: string | null
  order_id: string | null
  created_at: string
  quoted_at: string | null
  rejected_at: string | null
  messages: CustomMessage[]
}

export interface CreateCustomRequestPayload {
  request_type: RequestType
  photo_url?: string | null
  ref_product_id?: string | null
  canvas_w_cm?: number | null
  canvas_h_cm?: number | null
  difficulty?: Difficulty | null
  detail?: Detail | null
  customer_notes?: string | null
  parent_request_id?: string | null
}

export interface CreateCustomRequestResponse {
  id: string
  request_type: RequestType
  status: RequestStatus
  created_at: string
}

export interface UpdatePhotoResponse {
  id: string
  photo_url: string
  updated_at: string
}

// ── Quote viewer ─────────────────────────────────────────────────────────────

export interface QuoteSummaryResponse {
  custom_request_id: string
  spec_summary: {
    canvas_w_cm: number | null
    canvas_h_cm: number | null
    difficulty: Difficulty | null
    detail: Detail | null
    photo_url: string | null
    customer_notes: string | null
  }
  quoted_price: number
  quote_expires_at: string
  is_extended: boolean
  revision_count: number
  messages: CustomMessage[]
  preview_available: boolean
  view_count: number
  max_views: number
}

export interface ConfirmQuoteResponse {
  order_id: string
  order_number: string
  total: number
  payment_deadline: string
  payment_info: {
    bank_account_number?: string
    bank_name?: string
    bank_account_name?: string
    [key: string]: string | undefined
  }
}

export interface RejectQuoteResponse {
  id: string
  status: RequestStatus
  rejected_at: string
}

export interface ExtendQuoteResponse {
  id: string
  quote_expires_at: string
  is_extended: boolean
}

export interface RequestRevisionResponse {
  id: string
  status: RequestStatus
  revision_count: number
}

// ── HTTP helper（共用 cart 那邊的 ApiError 形狀）──────────────────────────────

export interface ApiError extends Error {
  status: number
  detail: string
  code?: string
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
    let detailText = `${res.status}`
    let code: string | undefined
    try {
      const body = await res.json()
      // backend AppError → { detail: { message, code } }
      if (body?.detail && typeof body.detail === 'object') {
        detailText = body.detail.message ?? JSON.stringify(body.detail)
        code = body.detail.code
      } else if (typeof body?.detail === 'string') {
        detailText = body.detail
      } else if (typeof body?.message === 'string') {
        detailText = body.message
      }
    } catch {
      // fall through with default detailText
    }
    const err = new Error(detailText) as ApiError
    err.status = res.status
    err.detail = detailText
    if (code) err.code = code
    throw err
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ── Endpoints — customer ─────────────────────────────────────────────────────

/** POST /custom-requests — 建立客製申請 */
export async function createCustomRequest(
  body: CreateCustomRequestPayload,
): Promise<CreateCustomRequestResponse> {
  return jsonRequest<CreateCustomRequestResponse>('/custom-requests', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** GET /custom-requests — 我的申請清單 */
export async function listCustomRequests(params?: {
  status?: RequestStatus
  page?: number
  page_size?: number
}): Promise<CustomRequestListResponse> {
  const sp = new URLSearchParams()
  if (params?.status) sp.set('status', params.status)
  if (params?.page) sp.set('page', String(params.page))
  if (params?.page_size) sp.set('page_size', String(params.page_size))
  const qs = sp.toString()
  return jsonRequest<CustomRequestListResponse>(
    `/custom-requests${qs ? `?${qs}` : ''}`,
  )
}

/** GET /custom-requests/{id} — 申請詳情（含訊息） */
export async function getCustomRequest(id: string): Promise<CustomRequestDetail> {
  return jsonRequest<CustomRequestDetail>(`/custom-requests/${id}`)
}

/** GET /custom-requests/{id}/photo-signed-url — 短期讀取 signed URL（15 min）。
 *
 * DB 中 photo_url 為私密 firebase_path，不能直接給 <img>，需透過此端點重簽。
 */
export interface PhotoSignedUrlResponse {
  url: string
  expires_at: string
}
export async function getCustomPhotoSignedUrl(
  id: string,
): Promise<PhotoSignedUrlResponse> {
  return jsonRequest<PhotoSignedUrlResponse>(
    `/custom-requests/${id}/photo-signed-url`,
  )
}

/** POST /custom-requests/{id}/messages — 發送訊息 */
export async function postCustomMessage(
  id: string,
  message: string,
  image_url: string | null = null,
): Promise<CustomMessage> {
  return jsonRequest<CustomMessage>(`/custom-requests/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message, image_url }),
  })
}

/** PATCH /custom-requests/{id}/photo — 更換照片（quote_pending 才能） */
export async function updateCustomPhoto(
  id: string,
  photo_url: string,
): Promise<UpdatePhotoResponse> {
  return jsonRequest<UpdatePhotoResponse>(`/custom-requests/${id}/photo`, {
    method: 'PATCH',
    body: JSON.stringify({ photo_url }),
  })
}

/** PATCH /custom-requests/{id} — 改尺寸 / 難度 / 備註（quote_pending 才能） */
export interface UpdateRequestFieldsPayload {
  canvas_w_cm?: number | null
  canvas_h_cm?: number | null
  difficulty?: Difficulty | null
  customer_notes?: string | null
}
export async function updateCustomRequestFields(
  id: string,
  payload: UpdateRequestFieldsPayload,
): Promise<CustomRequestDetail> {
  return jsonRequest<CustomRequestDetail>(`/custom-requests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

// ── Endpoints — quote token ──────────────────────────────────────────────────

/** GET /custom/quote/{token} — 報價摘要 */
export async function getQuoteSummary(token: string): Promise<QuoteSummaryResponse> {
  return jsonRequest<QuoteSummaryResponse>(`/custom/quote/${token}`)
}

/** GET /custom/quote/{token}/preview — 浮水印預覽 PNG（直接用作 <img src>）*/
export function quotePreviewUrl(token: string): string {
  return `${API_BASE}/custom/quote/${token}/preview`
}

/** POST /custom/quote/{token}/confirm — 確認報價，建立訂單 */
export async function confirmQuote(
  token: string,
  shipping_profile_id: string,
): Promise<ConfirmQuoteResponse> {
  return jsonRequest<ConfirmQuoteResponse>(`/custom/quote/${token}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ shipping_profile_id }),
  })
}

/** POST /custom/quote/{token}/reject — 拒絕報價 */
export async function rejectQuote(
  token: string,
  reason: string | null = null,
): Promise<RejectQuoteResponse> {
  return jsonRequest<RejectQuoteResponse>(`/custom/quote/${token}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

/** POST /custom/quote/{token}/extend — 延長報價 24h（每筆限一次） */
export async function extendQuote(token: string): Promise<ExtendQuoteResponse> {
  return jsonRequest<ExtendQuoteResponse>(`/custom/quote/${token}/extend`, {
    method: 'POST',
  })
}

/** POST /custom/quote/{token}/request-revision — 要求修改（限 3 次） */
export async function requestRevision(
  token: string,
  reason: string,
): Promise<RequestRevisionResponse> {
  return jsonRequest<RequestRevisionResponse>(
    `/custom/quote/${token}/request-revision`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
    },
  )
}

// ── SSE URL helper（連線用 EventSource，不走 fetch）──────────────────────────

export function customRequestSseUrl(requestId: string): string {
  return `${API_BASE}/custom-requests/${requestId}/sse`
}

// ── Reference data — canvas sizes + photo prices ────────────────────────────

export interface CanvasSize {
  id: string
  canvas_w_cm: number
  canvas_h_cm: number
  display_name: string
}

export async function listCanvasSizes(): Promise<{ items: CanvasSize[] }> {
  return jsonRequest<{ items: CanvasSize[] }>('/canvas-sizes')
}

export interface PhotoPriceRow {
  id: string
  canvas_w: number
  canvas_h: number
  difficulty: Difficulty
  price: number | null
}

export async function listPhotoPrices(): Promise<{ items: PhotoPriceRow[] }> {
  return jsonRequest<{ items: PhotoPriceRow[] }>('/custom-photo-prices')
}

// ── Cases (inspiration gallery)──────────────────────────────────────────────
// Source: backend/content/router.py L103 — public_list_cases

export interface CaseImageItem {
  id: string
  image_url: string
  sort_order: number
}

export interface CustomCase {
  id: string
  image_url: string  // 主圖（封面）— 同 images[0].image_url
  title: string
  description: string | null
  category_id: string | null
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: Difficulty | null
  is_published: boolean
  created_at: string
  images?: CaseImageItem[]
}

export interface CustomCaseListResponse {
  items: CustomCase[]
  total: number
  page: number
  page_size: number
}

export async function listCustomCases(params?: {
  category_id?: string
  page?: number
  page_size?: number
}): Promise<CustomCaseListResponse> {
  const sp = new URLSearchParams()
  if (params?.category_id) sp.set('category_id', params.category_id)
  if (params?.page) sp.set('page', String(params.page))
  if (params?.page_size) sp.set('page_size', String(params.page_size))
  const qs = sp.toString()
  return jsonRequest<CustomCaseListResponse>(`/custom-cases${qs ? `?${qs}` : ''}`)
}

export interface CaseCategory {
  id: string
  name: string
}

export async function listCaseCategories(): Promise<{ items: CaseCategory[] }> {
  return jsonRequest<{ items: CaseCategory[] }>('/case-categories')
}

// ── Status / type display helpers ────────────────────────────────────────────

export const STATUS_LABEL: Record<RequestStatus, string> = {
  quote_pending: '等待報價',
  negotiating: '洽談中',
  quote_sent: '報價已送達',
  draft_revision: '修改中',
  quote_confirmed: '已確認',
  quote_rejected: '已拒絕',
  quote_expired: '已逾期',
}

export const REQUEST_TYPE_LABEL: Record<RequestType, string> = {
  custom_photo: '相片客製',
  custom_spec: '規格客製',
}

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: '入門',
  elementary: '初級',
  intermediate: '中級',
  advanced: '進階',
}

export const DETAIL_LABEL: Record<Detail, string> = {
  rough: '粗略',
  standard: '標準',
  detailed: '細緻',
  premium: '高級',
}
