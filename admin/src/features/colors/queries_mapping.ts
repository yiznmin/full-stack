import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import {
  completePaletteMappings,
  copyMappingsFromJob,
  listPaletteMappings,
  updatePaletteMapping,
} from './api_mapping'

export const PM_KEYS = {
  mappings: (jobId: string) => ['admin', 'palette-mappings', jobId] as const,
}

export function usePaletteMappingsQuery(jobId: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['admin', 'palette-mappings', jobId],
    queryFn: () => listPaletteMappings(toValue(jobId)!),
    enabled: () => !!toValue(jobId),
    staleTime: 30_000,
  })
}

export function useUpdateMappingMutation(jobId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ templateId, physicalColorId }: { templateId: number; physicalColorId: string }) =>
      updatePaletteMapping(jobId, templateId, physicalColorId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PM_KEYS.mappings(jobId) })
    },
  })
}

export function useCopyMappingsMutation(jobId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sourceJobId: string) => copyMappingsFromJob(jobId, sourceJobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PM_KEYS.mappings(jobId) })
    },
  })
}

export function useCompleteMappingsMutation(jobId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => completePaletteMappings(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PM_KEYS.mappings(jobId) })
    },
  })
}
