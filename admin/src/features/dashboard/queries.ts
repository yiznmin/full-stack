import { useQuery } from '@tanstack/vue-query'
import { getDashboardSummary } from './api'

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['admin', 'dashboard', 'summary'] as const,
    queryFn: getDashboardSummary,
    staleTime: 60_000,
    refetchInterval: 60_000,  // 每分鐘自動 refetch
  })
}
