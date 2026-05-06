// User profile + shipping profile API
// Source: backend/users/router.py

const API_BASE = '/api/v1'

export type ShippingType = 'home' | 'seven_eleven' | 'family_mart'

export interface ShippingProfile {
  id: string
  shipping_type: ShippingType
  recipient_name: string
  phone: string
  email: string | null
  city: string | null
  district: string | null
  address_detail: string | null
  store_id: string | null
  store_name: string | null
  is_default: boolean
}

export interface ShippingProfileInput {
  shipping_type: ShippingType
  recipient_name: string
  phone: string
  email?: string | null
  city?: string | null
  district?: string | null
  address_detail?: string | null
  store_id?: string | null
  store_name?: string | null
  is_default?: boolean
}

export interface ApiError extends Error {
  status: number
  detail: string
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
    const detail = await res
      .json()
      .then((b) => b?.detail ?? b?.message ?? `${res.status}`)
      .catch(() => `${res.status}`)
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)) as ApiError
    err.status = res.status
    err.detail = typeof detail === 'string' ? detail : JSON.stringify(detail)
    throw err
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function listShippingProfiles(): Promise<ShippingProfile[]> {
  return jsonRequest<ShippingProfile[]>('/users/me/shipping-profiles')
}

export async function createShippingProfile(data: ShippingProfileInput): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>('/users/me/shipping-profiles', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateShippingProfile(
  id: string,
  data: ShippingProfileInput,
): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>(`/users/me/shipping-profiles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteShippingProfile(id: string): Promise<void> {
  await jsonRequest<void>(`/users/me/shipping-profiles/${id}`, {
    method: 'DELETE',
  })
}

export async function setDefaultShippingProfile(id: string): Promise<ShippingProfile> {
  return jsonRequest<ShippingProfile>(
    `/users/me/shipping-profiles/${id}/set-default`,
    { method: 'PATCH' },
  )
}
