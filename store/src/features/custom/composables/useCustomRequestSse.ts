// SSE composable — 訂閱單一 custom_request 的事件流
//
// 使用：
//   const { connected } = useCustomRequestSse(requestId, {
//     onMessage: (msg) => { ... },
//     onStatusChanged: (data) => { ... },
//     onQuoteSent: (data) => { ... },
//   })
//
// 設計：
// - EventSource 自動帶 httpOnly cookie（同 origin → vite proxy /api）
// - 斷線時瀏覽器自動重連（後端 stream 開頭已送 retry: 5000）
// - onUnmounted 自動 close 連線

import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { customRequestSseUrl } from '../api'
import { useQueryClient } from '@tanstack/vue-query'
import { customQueryKeys } from '../queries'

export interface SseEventHandlers {
  /** new_message：admin 回覆訊息（payload.sender_type 區分） */
  onMessage?: (data: SseMessagePayload) => void
  /** status_changed：申請狀態變化（quote_pending → negotiating → ...） */
  onStatusChanged?: (data: SseStatusPayload) => void
  /** quote_sent：admin 送出報價（含金額 + 過期時間） */
  onQuoteSent?: (data: SseQuoteSentPayload) => void
  /** error：連線錯誤（會自動重連，僅 log 用途） */
  onError?: (e: Event) => void
}

export interface SseMessagePayload {
  request_id: string
  message_id: string
  sender_type: 'admin' | 'customer'
  message: string
  image_url: string | null
  created_at: string
}

export interface SseStatusPayload {
  request_id: string
  status: string
  order_id?: string
  revision_count?: number
}

export interface SseQuoteSentPayload {
  request_id: string
  status: string
  quoted_price: number
  quote_expires_at: string
}

export function useCustomRequestSse(
  requestId: Ref<string | null | undefined> | string | null | undefined,
  handlers: SseEventHandlers = {},
) {
  const connected = ref(false)
  const queryClient = useQueryClient()
  let es: EventSource | null = null

  function close() {
    if (es) {
      es.close()
      es = null
      connected.value = false
    }
  }

  function open(rid: string) {
    close()
    es = new EventSource(customRequestSseUrl(rid))

    es.onopen = () => {
      connected.value = true
    }

    es.onerror = (e) => {
      // EventSource 會自動重連（retry: 5000） — 不主動 close
      connected.value = false
      handlers.onError?.(e)
    }

    // SSE 自訂 event type 用 addEventListener('event_type', ...)
    es.addEventListener('new_message', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as SseMessagePayload
        handlers.onMessage?.(data)
        queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(rid) })
      } catch {
        /* ignore parse errors */
      }
    })

    es.addEventListener('status_changed', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as SseStatusPayload
        handlers.onStatusChanged?.(data)
        queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(rid) })
        queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
      } catch {
        /* ignore */
      }
    })

    es.addEventListener('quote_sent', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as SseQuoteSentPayload
        handlers.onQuoteSent?.(data)
        queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(rid) })
        queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
      } catch {
        /* ignore */
      }
    })
  }

  // 支援 ref 形式：requestId 變化時自動切換訂閱
  if (typeof requestId === 'string') {
    open(requestId)
  } else if (requestId && 'value' in requestId) {
    watch(
      () => requestId.value,
      (rid) => {
        if (rid) open(rid)
        else close()
      },
      { immediate: true },
    )
  }

  onBeforeUnmount(close)

  return { connected, close }
}
