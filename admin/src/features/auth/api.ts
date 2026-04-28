/**
 * Auth API wrappers.
 *
 * Note: 暫時用 plain fetch（cookie credentials 自動帶）。
 * 後端 OpenAPI 接通後，遷移到 `@/api/client` 的 openapi-fetch 客戶端，
 * 自動拿到 schema-driven 型別。
 */

import type { MeUser } from './store'

const API = '/api/v1'

interface ApiError {
  message: string
  code?: string
  status: number
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
    ...init,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err: ApiError = {
      message: body.message || body.detail || `HTTP ${res.status}`,
      code: body.code,
      status: res.status,
    }
    throw err
  }

  return res.json()
}

// ── Admin auth endpoints ─────────────────────────────────────────────

export interface LoginPayload {
  email: string
  password: string
}

export interface LoginResponse {
  id: string
  name: string
  role: string
}

export function adminLogin(payload: LoginPayload) {
  return request<LoginResponse>('/admin/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function adminLogout() {
  return request<{ message: string }>('/admin/auth/logout', {
    method: 'POST',
  })
}

export function adminForgotPassword(email: string) {
  return request<{ message: string }>('/admin/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

// ── Shared (admin uses customer endpoints for me + reset) ────────────

export function fetchMe() {
  return request<MeUser>('/auth/me', { method: 'GET' })
}

export function resetPassword(token: string, newPassword: string) {
  return request<{ message: string }>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}
