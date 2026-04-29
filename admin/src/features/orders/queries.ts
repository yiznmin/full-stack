import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import {
  createShipment,
  flagPaymentSubmission,
  getOrder,
  listOrders,
  refundOrder,
  updateAdminNotes,
  updateOrderStatus,
  updateProductionProgress,
  type AdminNotesPayload,
  type CreateShipmentPayload,
  type FlagPaymentSubmissionPayload,
  type OrdersListParams,
  type RefundOrderPayload,
  type UpdateOrderStatusPayload,
  type UpdateProductionProgressPayload,
} from './api'

export const ORDER_KEYS = {
  all: ['admin', 'orders'] as const,
  list: (params: OrdersListParams) => ['admin', 'orders', 'list', params] as const,
  detail: (id: string) => ['admin', 'orders', 'detail', id] as const,
}

export function useOrdersQuery(params: MaybeRefOrGetter<OrdersListParams>) {
  return useQuery({
    queryKey: ['admin', 'orders', 'list', params],
    queryFn: () => listOrders(toValue(params)),
    staleTime: 30_000,
  })
}

export function useOrderQuery(id: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['admin', 'orders', 'detail', id],
    queryFn: () => getOrder(toValue(id)!),
    enabled: () => !!toValue(id),
    staleTime: 10_000,
  })
}

function invalidateOrder(qc: ReturnType<typeof useQueryClient>, id: string) {
  qc.invalidateQueries({ queryKey: ORDER_KEYS.detail(id) })
  qc.invalidateQueries({ queryKey: ORDER_KEYS.all })
}

export function useUpdateStatusMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: UpdateOrderStatusPayload) => updateOrderStatus(orderId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}

export function useCreateShipmentMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateShipmentPayload) => createShipment(orderId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}

export function useUpdateProductionProgressMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      progressId,
      payload,
    }: {
      progressId: string
      payload: UpdateProductionProgressPayload
    }) => updateProductionProgress(orderId, progressId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}

export function useFlagPaymentSubmissionMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      submissionId,
      payload,
    }: {
      submissionId: string
      payload: FlagPaymentSubmissionPayload
    }) => flagPaymentSubmission(orderId, submissionId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}

export function useRefundOrderMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: RefundOrderPayload) => refundOrder(orderId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}

export function useUpdateAdminNotesMutation(orderId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AdminNotesPayload) => updateAdminNotes(orderId, payload),
    onSuccess: () => invalidateOrder(qc, orderId),
  })
}
