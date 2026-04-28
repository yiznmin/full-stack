import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'

import {
  adminLogin,
  adminLogout,
  adminForgotPassword,
  fetchMe,
  resetPassword,
  type LoginPayload,
} from './api'
import { useAuthStore } from './store'

const ME_KEY = ['auth', 'me'] as const

export function useMeQuery() {
  const auth = useAuthStore()
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => {
      const me = await fetchMe()
      auth.setUser(me)
      return me
    },
    retry: false,
    staleTime: 5 * 60_000,
  })
}

export function useLoginMutation() {
  const auth = useAuthStore()
  const router = useRouter()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      const result = await adminLogin(payload)
      // /admin/auth/login 只回 {id, name, role}，再打 /auth/me 拿完整資料
      const me = await fetchMe()
      auth.setUser(me)
      qc.setQueryData(ME_KEY, me)
      return result
    },
    onSuccess: () => {
      const next = (router.currentRoute.value.query.next as string) || '/admin/dashboard'
      router.push(next)
    },
  })
}

export function useLogoutMutation() {
  const auth = useAuthStore()
  const router = useRouter()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: adminLogout,
    onSettled: () => {
      auth.clear()
      qc.clear()
      router.push('/admin/login')
    },
  })
}

export function useForgotPasswordMutation() {
  return useMutation({
    mutationFn: (email: string) => adminForgotPassword(email),
  })
}

export function useResetPasswordMutation() {
  return useMutation({
    mutationFn: ({ token, newPassword }: { token: string; newPassword: string }) =>
      resetPassword(token, newPassword),
  })
}
