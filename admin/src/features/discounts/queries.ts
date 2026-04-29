import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import {
  createAutoCheckout,
  createPromoCode,
  deleteCouponConfig,
  deletePromoCode,
  getCouponConfigStats,
  issueCoupons,
  listCouponConfigs,
  listPromoCodes,
  listUserCoupons,
  patchCouponConfig,
  updatePromoCode,
  type CreateAutoCheckoutPayload,
  type CreatePromoCodePayload,
  type IssueCouponsPayload,
  type PatchCouponConfigPayload,
  type UpdatePromoCodePayload,
  type UserCouponsParams,
} from './api'

export const DC_KEYS = {
  all: ['admin', 'discounts'] as const,
  configs: ['admin', 'discounts', 'configs'] as const,
  configStats: (id: string) => ['admin', 'discounts', 'configs', 'stats', id] as const,
  promoCodes: ['admin', 'discounts', 'promo-codes'] as const,
  userCoupons: (params: UserCouponsParams) =>
    ['admin', 'discounts', 'user-coupons', params] as const,
}

export function useCouponConfigsQuery() {
  return useQuery({
    queryKey: DC_KEYS.configs,
    queryFn: () => listCouponConfigs(),
    staleTime: 60_000,
  })
}

export function useCouponConfigStatsQuery(id: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['admin', 'discounts', 'configs', 'stats', id],
    queryFn: () => getCouponConfigStats(toValue(id)!),
    enabled: () => !!toValue(id),
    staleTime: 60_000,
  })
}

export function usePromoCodesQuery() {
  return useQuery({
    queryKey: DC_KEYS.promoCodes,
    queryFn: () => listPromoCodes(),
    staleTime: 60_000,
  })
}

export function useUserCouponsQuery(params: MaybeRefOrGetter<UserCouponsParams>) {
  return useQuery({
    queryKey: ['admin', 'discounts', 'user-coupons', params],
    queryFn: () => listUserCoupons(toValue(params)),
    staleTime: 30_000,
  })
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: DC_KEYS.all })
}

export function usePatchCouponConfigMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: PatchCouponConfigPayload }) =>
      patchCouponConfig(id, payload),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useCreateAutoCheckoutMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateAutoCheckoutPayload) => createAutoCheckout(payload),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useDeleteCouponConfigMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteCouponConfig(id),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useCreatePromoCodeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreatePromoCodePayload) => createPromoCode(payload),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useUpdatePromoCodeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdatePromoCodePayload }) =>
      updatePromoCode(id, payload),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useDeletePromoCodeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deletePromoCode(id),
    onSuccess: () => invalidateAll(qc),
  })
}

export function useIssueCouponsMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: IssueCouponsPayload) => issueCoupons(payload),
    onSuccess: () => invalidateAll(qc),
  })
}
