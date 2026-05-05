import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  listProducts,
  searchProducts,
  getProduct,
  getRelatedProducts,
  type ProductsListParams,
} from './api'

const STALE_60S = 60 * 1000
const STALE_5MIN = 5 * 60 * 1000

/** Products list — 接受 reactive params，filter / sort / page 改變時自動 refetch */
export function useProductsQuery(params: MaybeRefOrGetter<ProductsListParams>) {
  return useQuery({
    queryKey: computed(() => ['public', 'products', toValue(params)] as const),
    queryFn: () => listProducts(toValue(params)),
    staleTime: STALE_60S,
  })
}

/** Search — q 變動時重打 */
export function useSearchProductsQuery(
  q: MaybeRefOrGetter<string>,
  page: MaybeRefOrGetter<number> = 1,
  page_size = 24,
) {
  return useQuery({
    queryKey: computed(
      () => ['public', 'products', 'search', { q: toValue(q), page: toValue(page), page_size }] as const,
    ),
    queryFn: () => searchProducts(toValue(q), toValue(page), page_size),
    staleTime: STALE_60S,
    enabled: computed(() => toValue(q).length > 0),
  })
}

// 判斷是否為合法 UUID（避免 dev preview / 假 id 直接打 backend 觸發 422）
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function isValidId(id: string): boolean {
  return UUID_RE.test(id)
}

/** Product detail — 5min stale；非 UUID id 時自動 disabled */
export function useProductDetailQuery(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['public', 'product', toValue(id)] as const),
    queryFn: () => getProduct(toValue(id)),
    staleTime: STALE_5MIN,
    enabled: computed(() => isValidId(toValue(id))),
  })
}

/** Related — 詳情頁同系列推薦；非 UUID id 時自動 disabled */
export function useRelatedProductsQuery(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['public', 'product', toValue(id), 'related'] as const),
    queryFn: () => getRelatedProducts(toValue(id)),
    staleTime: STALE_5MIN,
    enabled: computed(() => isValidId(toValue(id))),
  })
}
