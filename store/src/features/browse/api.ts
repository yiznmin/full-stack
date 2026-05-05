// Public Store - Browse API (themes / series / tags / products)
// Source: backend/product/router.py:108-148, schemas/response.py PublicTagBrief / PublicSeriesBrief

const API_BASE = '/api/v1'

// ── Themes ───────────────────────────────────────────────────────────────────

export interface ThemeListItem {
  id: string
  name: string
  description: string | null
  cover_image_url: string | null
  sort_order: number
  series_count: number
  product_count: number
}

export interface ThemeListResponse {
  items: ThemeListItem[]
}

/** GET /themes — 所有主題（依 sort_order 排）含 series_count + product_count */
export async function listThemes(): Promise<ThemeListResponse> {
  const res = await fetch(`${API_BASE}/themes`, { credentials: 'include' })
  if (!res.ok) throw new Error(`listThemes failed: ${res.status} ${res.statusText}`)
  return (await res.json()) as ThemeListResponse
}

// ── Series ───────────────────────────────────────────────────────────────────

export interface SeriesListItem {
  id: string
  name: string
  description: string | null
  theme_id: string | null
  theme_name: string | null
  is_featured: boolean
  product_count: number
}

export interface SeriesListResponse {
  items: SeriesListItem[]
}

/** GET /series — 所有系列；可帶 ?theme_id 過濾主題、?featured=true|false 過濾精選 */
export async function listSeries(
  themeId?: string,
  featured?: boolean,
): Promise<SeriesListResponse> {
  const params = new URLSearchParams()
  if (themeId) params.set('theme_id', themeId)
  if (featured !== undefined) params.set('featured', String(featured))
  const qs = params.toString()
  const url = qs ? `${API_BASE}/series?${qs}` : `${API_BASE}/series`
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(`listSeries failed: ${res.status} ${res.statusText}`)
  return (await res.json()) as SeriesListResponse
}

// ── Tags ─────────────────────────────────────────────────────────────────────

export interface TagListItem {
  id: string
  name: string
}

export interface TagListResponse {
  items: TagListItem[]
}

/** GET /tags — 所有公開標籤 */
export async function listTags(): Promise<TagListResponse> {
  const res = await fetch(`${API_BASE}/tags`, { credentials: 'include' })
  if (!res.ok) throw new Error(`listTags failed: ${res.status} ${res.statusText}`)
  return (await res.json()) as TagListResponse
}
