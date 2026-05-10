/**
 * Admin Dashboard API — 後台首頁聚合資料
 */

const API = '/api/v1'

interface ApiError {
  message: string
  code?: string
  status: number
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: 'include' })
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

export interface TrendInfo {
  direction: 'up' | 'down' | 'flat'
  delta: string
}

export interface DashboardSummary {
  stats: {
    orders_this_month: {
      value: number
      trend: TrendInfo
      meta: string
    }
    revenue_this_month: {
      value: number
      trend: TrendInfo
      meta: string
    }
    custom_pending: {
      value: number
      breakdown: {
        quote_pending: number
        negotiating: number
        quote_sent: number
      }
    }
    production_in_progress: {
      value: number
    }
    unhandled_notifications: {
      value: number
    }
  }
  production_pipeline: {
    pending: number
    processing: number
    completed: number
    failed: number
  }
  recent_activities: Array<{
    kind: 'order' | 'custom'
    id: string
    title: string
    status: string
    created_at: string | null
  }>
}

export function getDashboardSummary() {
  return request<DashboardSummary>('/admin/dashboard/summary')
}
