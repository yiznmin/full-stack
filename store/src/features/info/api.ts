// Static info pages — backend route GET /pages/{slug} (content/router.py)
// Spec: docs/requirements/store/store_info.md

const API_BASE = '/api/v1'

export type InfoSlug =
  | 'size_guide'
  | 'shipping'
  | 'custom_process'
  | 'pricing_reference'
  | 'refund_policy'

export interface PageResponse {
  slug: string
  title: string
  content: string
  updated_at: string
}

export async function fetchPage(slug: InfoSlug): Promise<PageResponse> {
  const r = await fetch(`${API_BASE}/pages/${slug}`, { credentials: 'include' })
  if (!r.ok) {
    throw new Error(`Failed to fetch page ${slug}: HTTP ${r.status}`)
  }
  return r.json()
}
