/**
 * Content API wrappers — F10 內容管理。
 * 涵蓋 6 個子模組：static_pages / system_settings / photo_prices / photo_surcharges / custom_cases / case_categories
 *
 * 注意：canvas_sizes endpoint 後端尚未實作（F06-A 留 backlog 中），
 * 前端 CANVAS_SIZES hardcode 17 種尺寸沿用。
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

export type Difficulty = 'beginner' | 'elementary' | 'intermediate' | 'advanced'

export interface StaticPage {
  id: string
  slug: string
  title: string
  content: string
  updated_at: string
}

export interface SystemSetting {
  key: string
  value: string
  updated_at: string
}

export interface CustomPhotoPrice {
  id: string
  canvas_w: number
  canvas_h: number
  difficulty: Difficulty
  price: number
}

export interface CustomPhotoSurcharge {
  id: string
  category: string
  label: string
  amount: number
  is_active: boolean
  created_at: string
}

export interface CaseCategory {
  id: string
  name: string
  created_at: string
}

export interface CaseImageItem {
  id: string
  image_url: string
  sort_order: number
}

export interface CustomCase {
  id: string
  image_url: string  // 主圖（= images[0].image_url，前端 list 縮圖讀此欄位）
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

/** 寫入 payload：images 為陣列（順序即 sort_order，service 會重新編號） */
export interface CustomCaseWritePayload {
  image_url?: string | null
  title: string
  description: string | null
  category_id: string | null
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: Difficulty | null
  is_published: boolean
  images?: { image_url: string }[]
}

// ── Endpoints ─────────────────────────────────────────────────────────

// static_pages
export function listPages() {
  return request<{ items: StaticPage[] }>('/admin/pages')
}
export function upsertPage(slug: string, payload: { title: string; content: string }) {
  return request<StaticPage>(`/admin/pages/${slug}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

// system_settings
export function listSettings() {
  return request<{ items: SystemSetting[] }>('/admin/system-settings')
}
export function upsertSetting(payload: { key: string; value: string }) {
  return request<SystemSetting>('/admin/system-settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

// photo_prices
export function listPhotoPrices() {
  return request<{ items: CustomPhotoPrice[] }>('/admin/custom-photo-prices')
}
export function updatePhotoPrice(id: string, price: number) {
  return request<CustomPhotoPrice>(`/admin/custom-photo-prices/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ price }),
  })
}

// photo_surcharges
export function listSurcharges() {
  return request<{ items: CustomPhotoSurcharge[] }>('/admin/custom-photo-surcharges')
}
export function createSurcharge(payload: {
  category: string
  label: string
  amount: number
  is_active: boolean
}) {
  return request<CustomPhotoSurcharge>('/admin/custom-photo-surcharges', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function updateSurcharge(
  id: string,
  payload: { category: string; label: string; amount: number; is_active: boolean },
) {
  return request<CustomPhotoSurcharge>(`/admin/custom-photo-surcharges/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function toggleSurchargeActive(id: string) {
  return request<CustomPhotoSurcharge>(`/admin/custom-photo-surcharges/${id}/toggle-active`, {
    method: 'PATCH',
  })
}
export function deleteSurcharge(id: string) {
  return request<void>(`/admin/custom-photo-surcharges/${id}`, { method: 'DELETE' })
}

// case_categories
export function listCaseCategories() {
  return request<{ items: CaseCategory[] }>('/admin/case-categories')
}
export function createCaseCategory(name: string) {
  return request<CaseCategory>('/admin/case-categories', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}
export function updateCaseCategory(id: string, name: string) {
  return request<CaseCategory>(`/admin/case-categories/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  })
}
export function deleteCaseCategory(id: string) {
  return request<void>(`/admin/case-categories/${id}`, { method: 'DELETE' })
}

// custom_cases
export function listCustomCases(params: { page?: number; page_size?: number } = {}) {
  const q = new URLSearchParams()
  q.set('page', String(params.page ?? 1))
  q.set('page_size', String(params.page_size ?? 50))
  return request<{ items: CustomCase[]; total: number; page: number; page_size: number }>(
    `/admin/custom-cases?${q.toString()}`,
  )
}
export function createCustomCase(payload: CustomCaseWritePayload) {
  return request<CustomCase>('/admin/custom-cases', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function updateCustomCase(id: string, payload: CustomCaseWritePayload) {
  return request<CustomCase>(`/admin/custom-cases/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function toggleCustomCasePublish(id: string) {
  return request<CustomCase>(`/admin/custom-cases/${id}/toggle-publish`, { method: 'PATCH' })
}
export function deleteCustomCase(id: string) {
  return request<void>(`/admin/custom-cases/${id}`, { method: 'DELETE' })
}

// ── Case image upload (Firebase signed URL → 公開 case_images/) ───────

interface PublicSignedUrl {
  upload_url: string
  public_url: string
  expires_at: string
}

export async function uploadCaseImage(file: File): Promise<string> {
  const contentType: 'image/png' | 'image/jpeg' =
    file.type === 'image/png' ? 'image/png' : 'image/jpeg'
  const signed = await request<PublicSignedUrl>('/upload/case-image', {
    method: 'POST',
    body: JSON.stringify({
      filename: file.name,
      content_type: contentType,
      size: file.size,
    }),
  })
  let putRes: Response
  try {
    putRes = await fetch(signed.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: file,
    })
  } catch (e) {
    throw new Error(
      'PUT Firebase 失敗（多半是 CORS）— 請 admin 用「系統 → Firebase CORS 修正」按鈕設定。' +
        ` 原始錯誤：${(e as Error).message}`,
    )
  }
  if (!putRes.ok && !signed.upload_url.startsWith('https://stub.firebase')) {
    throw new Error(`Firebase 拒絕上傳：HTTP ${putRes.status}`)
  }

  // 驗證上傳後的 URL 是否真的可讀（防 Firebase eventual-consistency 或 storage rules 沒開）
  // 重試最多 3 次，間隔 600ms（Firebase 寫入後通常 1-2 秒內可讀）
  if (!signed.public_url.startsWith('https://stub.firebase')) {
    let lastStatus = 0
    for (let attempt = 0; attempt < 3; attempt++) {
      await new Promise((r) => setTimeout(r, attempt === 0 ? 100 : 600))
      try {
        const verify = await fetch(signed.public_url, { method: 'HEAD' })
        lastStatus = verify.status
        if (verify.ok) return signed.public_url
      } catch {
        // 網路錯誤 → 下一輪再試
      }
    }
    throw new Error(
      `上傳成功但 URL 無法公開讀取（最後一次驗證 HTTP ${lastStatus}）。請聯絡管理員檢查 Firebase Storage 規則是否允許 case_images/** 公開讀。\n` +
      `URL：${signed.public_url}`,
    )
  }
  return signed.public_url
}

// ── 從 production_job 帶入規格 + 封面圖（重用既有 endpoint） ──────────

export interface AvailableJob {
  id: string
  image_id: string | null
  detail: string
  difficulty: string
  canvas_w_cm: number
  canvas_h_cm: number
  num_colors_used: number
  price_formula_base: number
  preview_url: string | null  // 15-min signed for thumbnail
  cover_url: string | null    // 永久 download URL，寫入 case.image_url
}

export function listAvailableJobsForCase() {
  // 不傳 product_id → 列出所有 approved + 有 cover 的 job 候選
  return request<{ items: AvailableJob[] }>('/admin/production/jobs/available-for-variant')
}

// ── Labels ────────────────────────────────────────────────────────────

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: '入門',
  elementary: '初級',
  intermediate: '中級',
  advanced: '進階',
}

export interface SettingMeta {
  label: string
  type: 'text' | 'textarea' | 'number'
  hint?: string
  group: 'payment' | 'ecpay_sender' | 'product_info' | 'paint' | 'custom' | 'misc'
}

export const SETTING_LABEL: Record<string, SettingMeta> = {
  // 付款資訊（給客戶看的匯款帳號）
  bank_account_number: { label: '銀行帳號', type: 'text', group: 'payment' },
  bank_name: { label: '銀行名稱', type: 'text', group: 'payment' },
  bank_account_name: { label: '匯款戶名', type: 'text', group: 'payment' },
  payment_absolute_deadline_hours: { label: '付款絕對期限（小時）', type: 'number', group: 'payment' },

  // 客服聯絡（顯示給客戶用）
  admin_contact_email: {
    label: '客服 Email',
    type: 'text',
    hint: '客戶在訂單頁需修改地址但不在 pending_payment 階段時，會看到「請寄信至此」',
    group: 'payment',
  },

  // ECpay 寄件人資訊（建立物流訂單用，必填）
  ecpay_sender_name: {
    label: 'ECpay 寄件人姓名',
    type: 'text',
    hint: '4-10 字、禁數字與特殊符號（ECpay 規範）',
    group: 'ecpay_sender',
  },
  ecpay_sender_phone: {
    label: 'ECpay 寄件人手機',
    type: 'text',
    hint: '09 開頭 10 碼純數字',
    group: 'ecpay_sender',
  },
  ecpay_sender_zip_code: {
    label: 'ECpay 寄件人郵遞區號',
    type: 'text',
    hint: '3-5 碼數字（如 100、24501）',
    group: 'ecpay_sender',
  },
  ecpay_sender_address: {
    label: 'ECpay 寄件人地址',
    type: 'text',
    hint: '完整地址（縣市+行政區+巷弄號樓），長度需 > 6 字',
    group: 'ecpay_sender',
  },

  // 商品資訊（store 商品說明區塊）
  product_info_tools: { label: '畫具內容物說明', type: 'textarea', group: 'product_info' },
  product_info_material: { label: '畫布材質說明', type: 'textarea', group: 'product_info' },
  product_info_tips: { label: '使用建議', type: 'textarea', group: 'product_info' },
  product_info_notes: { label: '注意事項', type: 'textarea', group: 'product_info' },

  // 顏料計算
  paint_ml_per_cm2: { label: '顏料塗佈係數（ml/cm²）', type: 'number', group: 'paint' },
  paint_min_ml: { label: '顏料最低配給量（ml）', type: 'number', group: 'paint' },
  paint_buffer_ratio: { label: '顏料緩衝係數', type: 'number', group: 'paint' },

  // 客製設定
  quote_reply_days: { label: '客製預計回覆天數', type: 'number', group: 'custom' },
  custom_photo_price_multiplier: { label: '客製服務費率倍數', type: 'number', group: 'custom' },
}

export const SETTING_GROUP_LABEL: Record<SettingMeta['group'], string> = {
  payment: '付款資訊（顯示給客戶）',
  ecpay_sender: 'ECpay 寄件人資訊（建立物流訂單必填）',
  product_info: '商品資訊（store 顯示）',
  paint: '顏料計算',
  custom: '客製設定',
  misc: '其他',
}

export const PAGE_LABEL: Record<string, string> = {
  size_guide: '尺寸指南',
  shipping: '出貨流程',
  custom_process: '訂製流程',
  pricing_reference: '報價參考',
  refund_policy: '退款退貨政策',
}
