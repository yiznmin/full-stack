import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import type { MaybeRefOrGetter } from 'vue'
import { toValue } from 'vue'

import {
  addImage,
  addVariant,
  createProduct,
  createSeries,
  createTag,
  createTheme,
  deleteImage,
  deleteProduct,
  deleteSeries,
  deleteTag,
  deleteTheme,
  deleteVariant,
  getProduct,
  listImages,
  listProducts,
  listSeries,
  listTags,
  listThemes,
  listVariants,
  reorderImages,
  updateProduct,
  updateSeries,
  updateTag,
  updateTheme,
  updateVariant,
  type ProductPayload,
  type ProductsListParams,
  type SeriesPayload,
  type ThemePayload,
} from './api'

const KEYS = {
  productsList: ['products', 'list'] as const,
  product: (id: string) => ['products', 'detail', id] as const,
  variants: (id: string) => ['products', 'variants', id] as const,
  images: (id: string) => ['products', 'images', id] as const,
  series: ['series', 'list'] as const,
  tags: ['tags', 'list'] as const,
  themes: ['themes', 'list'] as const,
}

// ── Products ──────────────────────────────────────────────────────────

export function useProductsQuery(params: MaybeRefOrGetter<ProductsListParams>) {
  return useQuery({
    queryKey: ['products', 'list', params],
    queryFn: () => listProducts(toValue(params)),
    staleTime: 30_000,
  })
}

export function useProductQuery(id: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['products', 'detail', id],
    queryFn: () => getProduct(toValue(id)!),
    enabled: () => !!toValue(id),
    staleTime: 30_000,
  })
}

export function useCreateProductMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createProduct,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.productsList })
    },
  })
}

export function useUpdateProductMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProductPayload }) =>
      updateProduct(id, payload),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: KEYS.productsList })
      qc.invalidateQueries({ queryKey: KEYS.product(id) })
    },
  })
}

export function useDeleteProductMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteProduct,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.productsList })
    },
  })
}

// ── Variants ──────────────────────────────────────────────────────────

export function useVariantsQuery(productId: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['products', 'variants', productId],
    queryFn: () => listVariants(toValue(productId)!),
    enabled: () => !!toValue(productId),
  })
}

export function useAddVariantMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { production_job_id: string; price: number }) =>
      addVariant(productId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.variants(productId) })
      qc.invalidateQueries({ queryKey: KEYS.productsList })
    },
  })
}

export function useUpdateVariantMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ variantId, payload }: { variantId: string; payload: { price?: number; is_active?: boolean } }) =>
      updateVariant(productId, variantId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.variants(productId) })
    },
  })
}

export function useDeleteVariantMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (variantId: string) => deleteVariant(productId, variantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.variants(productId) })
      qc.invalidateQueries({ queryKey: KEYS.productsList })
    },
  })
}

// ── Images ────────────────────────────────────────────────────────────

export function useImagesQuery(productId: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: ['products', 'images', productId],
    queryFn: () => listImages(toValue(productId)!),
    enabled: () => !!toValue(productId),
  })
}

export function useAddImageMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { image_url: string; sort_order: number }) =>
      addImage(productId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.images(productId) })
    },
  })
}

export function useDeleteImageMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (imageId: string) => deleteImage(productId, imageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.images(productId) })
    },
  })
}

export function useReorderImagesMutation(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (order: string[]) => reorderImages(productId, order),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.images(productId) })
    },
  })
}

// ── Series ────────────────────────────────────────────────────────────

export function useSeriesQuery() {
  return useQuery({
    queryKey: KEYS.series,
    queryFn: () => listSeries(),
    staleTime: 60_000,
  })
}

export function useCreateSeriesMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createSeries,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.series }),
  })
}

export function useUpdateSeriesMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SeriesPayload }) =>
      updateSeries(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.series }),
  })
}

export function useDeleteSeriesMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSeries,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.series }),
  })
}

// ── Themes ────────────────────────────────────────────────────────────

export function useThemesQuery() {
  return useQuery({
    queryKey: KEYS.themes,
    queryFn: () => listThemes({ page_size: 100 }),
    staleTime: 60_000,
  })
}

export function useCreateThemeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTheme,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.themes })
      qc.invalidateQueries({ queryKey: KEYS.series })  // 系列列表帶 theme_name
    },
  })
}

export function useUpdateThemeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ThemePayload }) =>
      updateTheme(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.themes })
      qc.invalidateQueries({ queryKey: KEYS.series })
    },
  })
}

export function useDeleteThemeMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTheme,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.themes })
      qc.invalidateQueries({ queryKey: KEYS.series })  // theme_id 變 NULL
    },
  })
}

// ── Tags ──────────────────────────────────────────────────────────────

export function useTagsQuery() {
  return useQuery({
    queryKey: KEYS.tags,
    queryFn: listTags,
    staleTime: 60_000,
  })
}

export function useCreateTagMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTag,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.tags }),
  })
}

export function useUpdateTagMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name: string } }) =>
      updateTag(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.tags }),
  })
}

export function useDeleteTagMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTag,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.tags }),
  })
}
