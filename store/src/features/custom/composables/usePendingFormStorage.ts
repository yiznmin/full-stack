// Pending form draft — 跨 session 暫存客製申請表單
//
// 流程：
//   1. 未登入用戶填表 → 點「送出申請」
//   2. save() → sessionStorage + redirect /login?redirect=/custom
//   3. 登入後回 /custom → load() 取出，呼叫 createCustomRequest，clear()
//
// 用 sessionStorage（不留跨分頁長期殘留）；只存表單欄位，不存照片 base64
// （照片 url 已上傳到 Firebase，url 文字保留即可）。

import type { CreateCustomRequestPayload } from '../api'

const KEY = 'pending_custom_request'

export function usePendingFormStorage() {
  function save(payload: CreateCustomRequestPayload): void {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(payload))
    } catch {
      // quota / private mode → 靜默 fallback（最壞案例：用戶得重填）
    }
  }

  function load(): CreateCustomRequestPayload | null {
    try {
      const raw = sessionStorage.getItem(KEY)
      if (!raw) return null
      return JSON.parse(raw) as CreateCustomRequestPayload
    } catch {
      return null
    }
  }

  function clear(): void {
    try {
      sessionStorage.removeItem(KEY)
    } catch {
      /* ignore */
    }
  }

  function exists(): boolean {
    try {
      return sessionStorage.getItem(KEY) !== null
    } catch {
      return false
    }
  }

  return { save, load, clear, exists }
}
