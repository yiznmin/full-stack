import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import * as customApi from './api'
import { useAuthStore } from '@/features/auth/store'

// 快取多久算 fresh
const STALE_15S = 15 * 1000

// ── Query keys ───────────────────────────────────────────────────────────────

export const customQueryKeys = {
  all: ['custom'] as const,
  list: (filters?: { status?: customApi.RequestStatus; page?: number }) =>
    ['custom', 'list', filters ?? {}] as const,
  detail: (id: string) => ['custom', 'detail', id] as const,
  quote: (token: string) => ['custom', 'quote', token] as const,
}

// ── Customer queries ─────────────────────────────────────────────────────────

/** GET /custom-requests — 我的申請清單（需登入） */
export function useCustomRequestListQuery(
  filters: MaybeRefOrGetter<{
    status?: customApi.RequestStatus
    page?: number
    page_size?: number
  }> = () => ({}),
) {
  const auth = useAuthStore()
  return useQuery({
    queryKey: computed(() => customQueryKeys.list(toValue(filters))),
    queryFn: () => customApi.listCustomRequests(toValue(filters)),
    staleTime: STALE_15S,
    enabled: computed(() => auth.isLoggedIn),
  })
}

/** GET /custom-requests/{id} — 申請詳情 */
export function useCustomRequestDetailQuery(
  id: MaybeRefOrGetter<string | null | undefined>,
) {
  const auth = useAuthStore()
  return useQuery({
    queryKey: computed(() => customQueryKeys.detail(String(toValue(id) ?? ''))),
    queryFn: () => customApi.getCustomRequest(toValue(id) as string),
    staleTime: STALE_15S,
    enabled: computed(() => auth.isLoggedIn && !!toValue(id)),
  })
}

/** GET /custom-requests/{id}/photo-signed-url — 短期讀 URL，給 <img> 用 */
export function useCustomPhotoSignedUrlQuery(
  id: MaybeRefOrGetter<string | null | undefined>,
  hasPhoto: MaybeRefOrGetter<boolean>,
) {
  const auth = useAuthStore()
  return useQuery({
    queryKey: computed(() => ['custom', 'photo-signed-url', String(toValue(id) ?? '')]),
    queryFn: () => customApi.getCustomPhotoSignedUrl(toValue(id) as string),
    // signed URL 後端 TTL 15 min，前端 cache 10 min（與 _SIGNED_URL_CACHE_TTL 對齊）
    staleTime: 10 * 60 * 1000,
    enabled: computed(() => auth.isLoggedIn && !!toValue(id) && toValue(hasPhoto)),
  })
}

// ── Customer mutations ───────────────────────────────────────────────────────

export function useCreateCustomRequestMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: customApi.CreateCustomRequestPayload) =>
      customApi.createCustomRequest(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
    },
  })
}

export function usePostCustomMessageMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      requestId,
      message,
      image_url,
    }: {
      requestId: string
      message: string
      image_url?: string | null
    }) => customApi.postCustomMessage(requestId, message, image_url ?? null),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(vars.requestId) })
    },
  })
}

export function useUpdateCustomPhotoMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ requestId, photo_url }: { requestId: string; photo_url: string }) =>
      customApi.updateCustomPhoto(requestId, photo_url),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(vars.requestId) })
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
    },
  })
}

// ── Quote token queries / mutations ──────────────────────────────────────────

/** GET /custom/quote/{token} — 報價檢視（注意：每次 GET 會 +1 view_count）*/
export function useQuoteSummaryQuery(
  token: MaybeRefOrGetter<string | null | undefined>,
) {
  const auth = useAuthStore()
  return useQuery({
    queryKey: computed(() => customQueryKeys.quote(String(toValue(token) ?? ''))),
    queryFn: () => customApi.getQuoteSummary(toValue(token) as string),
    // 報價 viewer：拿到後即固定，狀態變化由 SSE / 行動回呼觸發 invalidate
    staleTime: Infinity,
    // 客戶端到 quote 頁前已 require 登入；防 token 為空時誤打
    enabled: computed(() => auth.isLoggedIn && !!toValue(token)),
    retry: false,  // 410 / 404 不重試
  })
}

export function useConfirmQuoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ token, quantity }: { token: string; quantity?: number }) =>
      customApi.confirmQuote(token, quantity ?? 1),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
      queryClient.invalidateQueries({ queryKey: customQueryKeys.quote(vars.token) })
      // cart 也要 refetch（剛加進去）
      queryClient.invalidateQueries({ queryKey: ['cart'] })
    },
  })
}

export function useRejectQuoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ token, reason }: { token: string; reason?: string | null }) =>
      customApi.rejectQuote(token, reason ?? null),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
      queryClient.invalidateQueries({ queryKey: customQueryKeys.quote(vars.token) })
    },
  })
}

export function useExtendQuoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => customApi.extendQuote(token),
    onSuccess: (_, token) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.quote(token) })
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
    },
  })
}

export function useRequestRevisionMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ token, reason }: { token: string; reason: string }) =>
      customApi.requestRevision(token, reason),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: customQueryKeys.all })
      queryClient.invalidateQueries({ queryKey: customQueryKeys.quote(vars.token) })
    },
  })
}
