import { useQuery } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import { listOrders, type OrdersListParams } from './api'

export const ORDER_KEYS = {
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
