/**
 * Palette Mappings API — F07-B 顏色對應工作台。
 */

const API = '/api/v1'

interface ApiError {
  message: string
  status: number
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  })
  if (res.status === 204) return null as unknown as T
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw {
      message: body.message || body.detail || `HTTP ${res.status}`,
      status: res.status,
    } as ApiError
  }
  return body
}

export interface PhysicalColorBrief {
  id: string
  code: string
  name: string
  rgb: [number, number, number]
  stock_ml: number
}

export interface PaletteMapping {
  template_id: number
  algorithm_rgb: [number, number, number]
  physical_color: PhysicalColorBrief | null
  required_ml: number | null
  mapped_by: 'system' | 'manual'
}

export interface CompleteResponse {
  all_stocked: boolean
  shortage_colors: { template_id: number; physical_color_id: string; code: string; name: string }[]
}

export function listPaletteMappings(jobId: string) {
  return request<{ mappings: PaletteMapping[] }>(`/admin/production/jobs/${jobId}/palette-mappings`)
}

export function updatePaletteMapping(jobId: string, templateId: number, physicalColorId: string) {
  return request<PaletteMapping>(
    `/admin/production/jobs/${jobId}/palette-mappings/${templateId}`,
    {
      method: 'PUT',
      body: JSON.stringify({ physical_color_id: physicalColorId }),
    },
  )
}

export function copyMappingsFromJob(jobId: string, sourceJobId: string) {
  return request<{ mappings: PaletteMapping[] }>(
    `/admin/production/jobs/${jobId}/palette-mappings/copy-from/${sourceJobId}`,
    { method: 'POST' },
  )
}

export interface CopyCandidate {
  job_id: string
  detail: string
  difficulty: string
  canvas_w_cm: number
  canvas_h_cm: number
  num_colors_used: number | null
  filled_template_url: string | null
  relation: 'same_batch' | 'same_image'
  created_at: string
}

export function listCopyCandidates(jobId: string) {
  return request<{ items: CopyCandidate[] }>(
    `/admin/production/jobs/${jobId}/palette-mappings/copy-candidates`,
  )
}

export function completePaletteMappings(jobId: string) {
  return request<CompleteResponse>(
    `/admin/production/jobs/${jobId}/palette-mappings/complete`,
    { method: 'POST' },
  )
}

// ── LAB distance (client-side auto-recommend) ─────────────────────────

function rgbToLab(r: number, g: number, b: number): [number, number, number] {
  // sRGB → linear
  const toLin = (c: number) => {
    const cs = c / 255
    return cs <= 0.04045 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4)
  }
  const rl = toLin(r)
  const gl = toLin(g)
  const bl = toLin(b)
  // linear → XYZ (D65)
  const x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047
  const y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
  const z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883
  // XYZ → LAB
  const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116)
  const fx = f(x)
  const fy = f(y)
  const fz = f(z)
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)]
}

export function labDistance(
  rgbA: [number, number, number],
  rgbB: [number, number, number],
): number {
  const [la, aa, ba] = rgbToLab(...rgbA)
  const [lb, ab, bb] = rgbToLab(...rgbB)
  return Math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)
}
