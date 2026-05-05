import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { listThemes, listSeries, listTags, getTheme, getSeries } from './api'

const STALE_10MIN = 10 * 60 * 1000

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function isValidId(id: string): boolean {
  return UUID_RE.test(id)
}

/** Themes — stale 10 分鐘（主題不常變） */
export function useThemesQuery() {
  return useQuery({
    queryKey: ['public', 'themes'],
    queryFn: listThemes,
    staleTime: STALE_10MIN,
  })
}

/** Series — 全部系列；mega-menu / 主題詳情頁共用；接受 reactive themeId */
export function useSeriesQuery(themeId?: MaybeRefOrGetter<string | undefined>) {
  return useQuery({
    queryKey: computed(() => ['public', 'series', toValue(themeId) ?? null] as const),
    queryFn: () => listSeries(toValue(themeId)),
    staleTime: STALE_10MIN,
  })
}

/** Featured Series — 精選系列（admin 後台勾選）；主題 mega-menu 上方區塊用 */
export function useFeaturedSeriesQuery() {
  return useQuery({
    queryKey: ['public', 'series', 'featured'],
    queryFn: () => listSeries(undefined, true),
    staleTime: STALE_10MIN,
  })
}

/** Tags — 標籤清單，mega-menu / 商品列表 filter 共用 */
export function useTagsQuery() {
  return useQuery({
    queryKey: ['public', 'tags'],
    queryFn: listTags,
    staleTime: STALE_10MIN,
  })
}

/** Theme detail — 主題詳情頁 */
export function useThemeDetailQuery(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['public', 'theme', toValue(id)] as const),
    queryFn: () => getTheme(toValue(id)),
    staleTime: STALE_10MIN,
    enabled: computed(() => isValidId(toValue(id))),
  })
}

/** Series detail — 系列詳情頁 */
export function useSeriesDetailQuery(id: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ['public', 'series', toValue(id)] as const),
    queryFn: () => getSeries(toValue(id)),
    staleTime: STALE_10MIN,
    enabled: computed(() => isValidId(toValue(id))),
  })
}
