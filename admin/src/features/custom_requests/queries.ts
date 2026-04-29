import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import {
  getCustomRequest,
  getPhotoSignedUrl,
  listCustomPhotoPrices,
  listCustomPhotoSurcharges,
  listCustomRequests,
  markNegotiating,
  postMessage,
  postQuote,
  type CustomRequestsListParams,
  type MessagePayload,
  type QuotePayload,
} from './api'

export const CR_KEYS = {
  all: ['admin', 'custom-requests'] as const,
  list: (params: CustomRequestsListParams) =>
    ['admin', 'custom-requests', 'list', params] as const,
  detail: (id: string) => ['admin', 'custom-requests', 'detail', id] as const,
  prices: ['admin', 'custom-photo-prices'] as const,
  surcharges: ['admin', 'custom-photo-surcharges'] as const,
}

export function useCustomRequestsQuery(params: MaybeRefOrGetter<CustomRequestsListParams>) {
  return useQuery({
    queryKey: ['admin', 'custom-requests', 'list', params],
    queryFn: () => listCustomRequests(toValue(params)),
    staleTime: 30_000,
  })
}

export function useCustomRequestQuery(id: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['admin', 'custom-requests', 'detail', id],
    queryFn: () => getCustomRequest(toValue(id)!),
    enabled: () => !!toValue(id),
    staleTime: 10_000,
    refetchOnWindowFocus: true,
  })
}

export function useCustomPhotoPricesQuery() {
  return useQuery({
    queryKey: CR_KEYS.prices,
    queryFn: () => listCustomPhotoPrices(),
    staleTime: 5 * 60_000,
  })
}

export function useCustomPhotoSurchargesQuery() {
  return useQuery({
    queryKey: CR_KEYS.surcharges,
    queryFn: () => listCustomPhotoSurcharges(),
    staleTime: 5 * 60_000,
  })
}

function invalidate(qc: ReturnType<typeof useQueryClient>, id: string) {
  qc.invalidateQueries({ queryKey: CR_KEYS.detail(id) })
  qc.invalidateQueries({ queryKey: CR_KEYS.all })
}

export function useMarkNegotiatingMutation(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => markNegotiating(id),
    onSuccess: () => invalidate(qc, id),
  })
}

export function usePostMessageMutation(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: MessagePayload) => postMessage(id, payload),
    onSuccess: () => invalidate(qc, id),
  })
}

export function usePostQuoteMutation(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: QuotePayload) => postQuote(id, payload),
    onSuccess: () => invalidate(qc, id),
  })
}

export async function fetchPhotoSignedUrl(id: string) {
  return getPhotoSignedUrl(id)
}
