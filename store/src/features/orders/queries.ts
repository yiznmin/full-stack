import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import * as ordersApi from './api'
import { useAuthStore } from '@/features/auth/store'

const STALE_30S = 30 * 1000

export function useOrdersQuery(
  status: MaybeRefOrGetter<string | undefined>,
  page: MaybeRefOrGetter<number>,
) {
  const auth = useAuthStore()
  return useQuery({
    queryKey: computed(() => ['orders', toValue(status), toValue(page)] as const),
    queryFn: () => ordersApi.listOrders(toValue(status) ?? undefined, toValue(page), 20),
    staleTime: STALE_30S,
    enabled: computed(() => auth.isLoggedIn),
  })
}

export function useOrderDetailQuery(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['order', toValue(id)] as const),
    queryFn: () => ordersApi.getOrder(toValue(id)),
    enabled: computed(() => !!toValue(id)),
    staleTime: STALE_30S,
  })
}

export function useSubmitPaymentMutation(orderId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ordersApi.PaymentSubmissionInput) =>
      ordersApi.submitPayment(toValue(orderId), data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order', toValue(orderId)] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

export function useConfirmReceivedMutation(orderId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => ordersApi.confirmReceived(toValue(orderId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order', toValue(orderId)] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

export function useCancelOrderMutation(orderId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (cancelReason: string) =>
      ordersApi.cancelOrder(toValue(orderId), cancelReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order', toValue(orderId)] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

export function useUpdateShippingMutation(orderId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ordersApi.UpdateShippingPayload) =>
      ordersApi.updateShipping(toValue(orderId), payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order', toValue(orderId)] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

// 從後端公開 system_settings 拿 admin_contact_email（給「請寄信至」hint 用）
export function usePublicSettingsQuery() {
  return useQuery({
    queryKey: ['public-settings'] as const,
    queryFn: async () => {
      const res = await fetch('/api/v1/system-settings/public')
      if (!res.ok) return { items: {} as Record<string, string> }
      return res.json() as Promise<{ items: Record<string, string> }>
    },
    staleTime: 5 * 60 * 1000,
  })
}

// 訂單狀態 → 中文 + tab 分類
// 對應 backend OrderStatusEnum 完整 10 個狀態
export const STATUS_LABEL: Record<string, string> = {
  pending_payment: '待付款',
  payment_expired: '逾期未付',
  paid: '已付款',
  processing: '製作中',
  shipped: '已出貨',
  completed: '已完成',
  cancelled: '已取消',
  refund_processing: '退款處理中',
  refunded: '已退款',
  partially_refunded: '部分退款',
}

export const STATUS_TAB: Record<string, 'unpaid' | 'shipping' | 'done'> = {
  pending_payment: 'unpaid',
  payment_expired: 'unpaid',     // 逾期也算未付（讓用戶看到並能處理）
  paid: 'shipping',
  processing: 'shipping',
  shipped: 'shipping',
  completed: 'done',
  cancelled: 'done',
  refund_processing: 'done',     // 退款處理中歸類已結案區
  refunded: 'done',
  partially_refunded: 'done',
}
