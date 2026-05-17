/**
 * Production API wrappers — F06-A 製作系統（admin）。
 *
 * F06-A 範圍：建立任務 / 列表 / 結果預覽 / approve / unapprove / 匯出 PDF / 從客製申請選照片
 * F06-B（未實作）：SAM 遮罩繪圖 / 後處理工具（合併色塊 / 消邊界）
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

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
export type Detail = 'rough' | 'standard' | 'detailed' | 'premium'
export type Difficulty = 'beginner' | 'elementary' | 'intermediate' | 'advanced'
export type Mode = 'standard' | 'sam_refine' | 'sam_weighted'

export interface PaletteColor {
  template_id: number
  rgb: [number, number, number]
  hex: string
  pixels?: number
  percent?: number
}

export interface JobListItem {
  id: string
  batch_id: string | null
  image_id: string | null
  custom_request_id: string | null
  status: JobStatus
  approved: boolean
  detail: Detail
  difficulty: Difficulty
  mode: Mode
  canvas_w_cm: number
  canvas_h_cm: number
  filled_template_url: string | null
  /** 等待中/失敗/處理中 job 的原圖縮圖 URL — 給 fallback 預覽用 */
  image_preview_url: string | null
  num_colors_used: number | null
  created_at: string
  approved_at: string | null
}

export interface JobsListResponse {
  items: JobListItem[]
  total: number
  page: number
  page_size: number
}

export interface JobsListParams {
  status?: JobStatus | ''
  approved?: boolean | ''
  batch_id?: string
  image_id?: string
  custom_request_id?: string
  page?: number
  page_size?: number
}

export interface JobDetail extends JobListItem {
  svg_url: string | null
  snapped_rgb_url: string | null
  palette_json: PaletteColor[] | null
  notes: string | null
  /** Finalize 後產出的「實體色版最終模板」SVG（並存於 svg_url）；NULL = 尚未 finalize */
  template_final_url: string | null
  /** Finalize 後產出的色號對照表 JSON；給 PDF legend 與 admin 預覽用 */
  palette_final_url: string | null
  /** Finalize 後產出的「實體色版」filled preview PNG（pixel-replaced from snapped_rgb）；
   *  vs filled_template_url 是演算法量化色，這版是真實塗色後效果 */
  filled_template_final_url: string | null
  finalized_at: string | null
  // F06-B 用：palette_mappings、sam_points、polygons、mask_url 等暫不入型別
}

export interface CreateJobsRequest {
  image_id?: string | null
  custom_request_id?: string | null
  jobs: {
    detail: Detail
    difficulty: Difficulty
    mode: Mode
    canvas_w_cm: number
    canvas_h_cm: number
    min_brush_diam_cm?: number
    num_colors?: number | null
    /** sam_refine 必填：>0；其餘 mode 忽略 */
    extra_colors?: number | null
    /** sam_weighted 必填：0.5-0.8；其餘 mode 忽略 */
    weight_ratio?: number | null
  }[]
}

export interface CreateJobsResponse {
  batch_id: string | null
  job_ids: string[]
}

export interface SignedUrlResponse {
  url: string | null
}

export interface CanvasSizeSuggestion {
  w: number
  h: number
  ratio_match: number
}

export interface SuggestCanvasSizesResponse {
  items: CanvasSizeSuggestion[]
}

export interface UploadProductionImageRequest {
  filename: string
  content_type: 'image/jpeg' | 'image/png'
  size: number
}

export interface UploadProductionImageResponse {
  upload_url: string
  public_url: string
  expires_at: string
}

export interface CreateImageRequest {
  original_url: string
  filename: string
  width: number
  height: number
}

export interface ImageResponse {
  id: string
  original_url: string
  filename: string
  width: number
  height: number
  created_at: string
}

// ── Endpoints ─────────────────────────────────────────────────────────

export function listJobs(params: JobsListParams = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.approved !== undefined && params.approved !== '') {
    q.set('approved', String(params.approved))
  }
  if (params.batch_id) q.set('batch_id', params.batch_id)
  if (params.image_id) q.set('image_id', params.image_id)
  if (params.custom_request_id) q.set('custom_request_id', params.custom_request_id)
  q.set('page', String(params.page ?? 1))
  q.set('page_size', String(params.page_size ?? 20))
  return request<JobsListResponse>(`/admin/production/jobs?${q.toString()}`)
}

export function getJob(id: string) {
  return request<JobDetail>(`/admin/production/jobs/${id}`)
}

export function getJobSignedUrl(
  id: string,
  file: 'svg' | 'snapped_rgb' | 'filled' | 'image' | 'mask',
) {
  return request<SignedUrlResponse>(`/admin/production/jobs/${id}/signed-url?file=${file}`)
}

export function createJobs(payload: CreateJobsRequest) {
  return request<CreateJobsResponse>('/admin/production/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function approveJob(id: string, notes?: string | null) {
  return request<JobDetail>(`/admin/production/jobs/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes ?? null }),
  })
}

export function unapproveJob(id: string) {
  return request<JobDetail>(`/admin/production/jobs/${id}/unapprove`, {
    method: 'POST',
  })
}

/**
 * 硬刪除 job — 連帶刪 palette_color_mappings 子資料 + Firebase svg/filled/snapped/mask 物件。
 * Backend 拒絕情況：status=processing（worker 在跑）或被 product/batch/order 引用。
 *
 * @param force 為 true 時繞過 processing 檢查，用於 worker 卡死的 zombie task
 *   （注意：產生的 Firebase 物件可能成 orphan，需手動清理）
 */
export function deleteJob(id: string, options: { force?: boolean } = {}) {
  const qs = options.force ? '?force=true' : ''
  return request<null>(`/admin/production/jobs/${id}${qs}`, {
    method: 'DELETE',
  })
}

export interface BatchDeleteJobResult {
  job_id: string
  ok: boolean
  error: string | null
}

export interface BatchDeleteJobsResponse {
  total: number
  success: number
  failed: number
  results: BatchDeleteJobResult[]
}

/**
 * 批次硬刪除製作任務（一次最多 50 筆）— 失敗筆獨立、不影響成功筆。
 * 每筆都會走單筆 deleteJob 的所有檢查（processing 拒絕 / 外部引用拒絕 /
 * Firebase prefix 清檔）。前端拿到 response 後可顯示成功/失敗清單。
 */
export function deleteJobsBatch(jobIds: string[], options: { force?: boolean } = {}) {
  return request<BatchDeleteJobsResponse>('/admin/production/jobs/batch-delete', {
    method: 'POST',
    body: JSON.stringify({ job_ids: jobIds, force: options.force ?? false }),
  })
}

export function requestUploadProductionImage(payload: UploadProductionImageRequest) {
  return request<UploadProductionImageResponse>('/upload/production-image', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createImage(payload: CreateImageRequest) {
  return request<ImageResponse>('/admin/images', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function recommendCanvasSizes(width: number, height: number, n = 3) {
  return request<SuggestCanvasSizesResponse>('/admin/production/canvas-sizes/recommend', {
    method: 'POST',
    body: JSON.stringify({ width, height, n }),
  })
}

// ── SAM mask + Batch start ─────────────────────────────────────────────

export interface SamPoint {
  x: number
  y: number
  /** 1 = foreground（保留 / 主體）；0 = background */
  label: 0 | 1
}

export interface SamMaskRequest {
  sam_points?: SamPoint[]
  polygons?: number[][][]
  mode: 'sam_refine' | 'sam_weighted'
}

export interface SamMaskResponse {
  mask_url: string | null
  mask_coverage: number | null
}

/** SAM 遮罩編輯：sam_points 觸發 SAM 推論（30-60s），polygons 即時生成 mask PNG。 */
export function updateSamMask(jobId: string, payload: SamMaskRequest) {
  return request<SamMaskResponse>(`/admin/production/jobs/${jobId}/sam-mask`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface BatchStartResponse {
  enqueued: number
  skipped: { job_id: string; reason: string }[]
}

/** 啟動 SAM batch — 把 batch 內所有有 mask 的 pending job 送進 Celery。 */
export function startBatch(batchId: string) {
  return request<BatchStartResponse>(`/admin/production/batches/${batchId}/start`, {
    method: 'POST',
  })
}

// ── F06-B Post-process（區域層級 — 用 polygon_id）───────────────────────

export interface MergeColorPayload {
  /** template.svg 中該格的 SVG `id="rN"` 屬性，admin 點選後從 DOM 取得 */
  polygon_id: string
  /** 目標色號（從 palette 任選） */
  target_template_id: number
}

export interface EliminateBorderPayload {
  /** 被吸收的那一格（會被改成 surviving 那格的顏色） */
  absorbed_polygon_id: string
  /** 存活的那一格（顏色不變） */
  surviving_polygon_id: string
}

// ── Batch post-process ─────────────────────────────────────────────────

export type BatchOperation =
  | ({ op: 'merge_color' } & MergeColorPayload)
  | ({ op: 'eliminate_border' } & EliminateBorderPayload)

export interface BatchPostProcessPayload {
  operations: BatchOperation[]
}

export function mergeColor(jobId: string, payload: MergeColorPayload) {
  return request<JobDetail>(`/admin/production/jobs/${jobId}/post-process/merge-color`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function eliminateBorder(jobId: string, payload: EliminateBorderPayload) {
  return request<JobDetail>(`/admin/production/jobs/${jobId}/post-process/eliminate-border`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Batch post-process：一次送出多個動作，後端只跑一次 SVG 重產 + 上傳。 */
export function batchPostProcess(jobId: string, payload: BatchPostProcessPayload) {
  return request<JobDetail>(`/admin/production/jobs/${jobId}/post-process/batch`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 直接觸發瀏覽器下載 PDF，無回傳值。 */
export async function downloadJobPdf(id: string) {
  const res = await fetch(`${API}/admin/production/jobs/${id}/export-pdf`, {
    credentials: 'include',
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw {
      message: body.detail || body.message || `HTTP ${res.status}`,
      status: res.status,
    } as ApiError
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `job-${id}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Hardcoded canvas sizes（⚠️2 backlog：等後端 GET /admin/canvas-sizes）─

export interface CanvasSize {
  w: number
  h: number
  label: string
}

// 與後端 _STANDARD_CANVAS_SIZES_CM 一致（17 種標準尺寸）
export const CANVAS_SIZES: CanvasSize[] = [
  // 正方形
  { w: 20, h: 20, label: '20 × 20 cm（正方）' },
  { w: 30, h: 30, label: '30 × 30 cm（正方）' },
  { w: 40, h: 40, label: '40 × 40 cm（正方）' },
  { w: 50, h: 50, label: '50 × 50 cm（正方）' },
  { w: 60, h: 60, label: '60 × 60 cm（正方）' },
  // 直幅
  { w: 30, h: 40, label: '30 × 40 cm（直幅）' },
  { w: 30, h: 50, label: '30 × 50 cm（直幅）' },
  { w: 30, h: 60, label: '30 × 60 cm（直幅）' },
  { w: 40, h: 50, label: '40 × 50 cm（直幅）' },
  { w: 40, h: 60, label: '40 × 60 cm（直幅）' },
  { w: 50, h: 60, label: '50 × 60 cm（直幅）' },
  // 橫幅
  { w: 40, h: 30, label: '40 × 30 cm（橫幅）' },
  { w: 50, h: 30, label: '50 × 30 cm（橫幅）' },
  { w: 60, h: 30, label: '60 × 30 cm（橫幅）' },
  { w: 50, h: 40, label: '50 × 40 cm（橫幅）' },
  { w: 60, h: 40, label: '60 × 40 cm（橫幅）' },
  { w: 60, h: 50, label: '60 × 50 cm（橫幅）' },
]

export const DETAIL_LABEL: Record<Detail, string> = {
  rough: '粗糙',
  standard: '標準',
  detailed: '細緻',
  premium: '高級',
}

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: '入門',
  elementary: '初級',
  intermediate: '中級',
  advanced: '進階',
}

export const STATUS_LABEL: Record<JobStatus, string> = {
  pending: '等待中',
  processing: '處理中',
  completed: '已完成',
  failed: '失敗',
  cancelled: '已取消',
}

export const MODE_LABEL: Record<Mode, string> = {
  standard: '標準',
  sam_refine: 'SAM 細化',
  sam_weighted: 'SAM 加權',
}
