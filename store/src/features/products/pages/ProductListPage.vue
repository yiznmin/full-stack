<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2, SlidersHorizontal } from 'lucide-vue-next'
import { useProductsQuery } from '../queries'
import { useSeriesQuery } from '@/features/browse/queries'
import type {
  Difficulty,
  SortMode,
  ProductsListParams,
  ProductBrief,
} from '../api'
import ProductGrid from '../components/ProductGrid.vue'
import ProductFilter from '../components/ProductFilter.vue'
import ProductSort from '../components/ProductSort.vue'
import Pagination from '../components/Pagination.vue'
import SeriesProductGroup from '../components/SeriesProductGroup.vue'

const route = useRoute()
const router = useRouter()

interface FilterState {
  theme_id?: string
  series_id?: string
  difficulty?: Difficulty
  canvas_size?: string
  tag_id?: string
}

// Read state from URL query
const filter = computed<FilterState>(() => ({
  theme_id: stringOrUndefined(route.query.theme_id),
  series_id: stringOrUndefined(route.query.series_id),
  difficulty: stringOrUndefined(route.query.difficulty) as Difficulty | undefined,
  canvas_size: stringOrUndefined(route.query.canvas_size),
  tag_id: stringOrUndefined(route.query.tag_id),
}))

const sort = computed<SortMode>(
  () => (stringOrUndefined(route.query.sort) as SortMode) || 'latest',
)
const page = computed(() => Number(route.query.page) || 1)

function stringOrUndefined(v: unknown): string | undefined {
  return typeof v === 'string' && v.length > 0 ? v : undefined
}

// 是否啟用「依系列分組」layout
// 當沒有指定特定 series_id 時，全部商品改以系列為單位呈現（雜誌風）
const isGroupedMode = computed(() => !filter.value.series_id)

// 系列分組所需資料：listSeries(theme_id?) — theme 過濾自動帶入
const seriesQuery = useSeriesQuery(() => filter.value.theme_id)
const seriesList = computed(() => seriesQuery.data.value?.items ?? [])
const groupedSeries = computed(() =>
  seriesList.value.filter((s) => s.product_count > 0),
)

// 平鋪 mode 的 API params（series_id 模式才用）
const flatParams = computed<ProductsListParams>(() => ({
  ...filter.value,
  sort: sort.value,
  page: page.value,
  page_size: 24,
}))
const flatQuery = useProductsQuery(flatParams)

const flatItems = computed(() => flatQuery.data.value?.items ?? [])
const flatTotal = computed(() => flatQuery.data.value?.total ?? 0)

// 共用的 total / empty 狀態
const total = computed(() =>
  isGroupedMode.value
    ? seriesList.value.reduce((sum, s) => sum + s.product_count, 0)
    : flatTotal.value,
)

const isEmpty = computed(() => {
  if (isGroupedMode.value) {
    return !seriesQuery.isPending.value && groupedSeries.value.length === 0
  }
  return !flatQuery.isPending.value && flatItems.value.length === 0
})

const isPending = computed(() =>
  isGroupedMode.value ? seriesQuery.isPending.value : flatQuery.isPending.value,
)

// Push helpers
function updateQuery(patch: Record<string, string | undefined>) {
  const newQuery: Record<string, string> = {}
  for (const [k, v] of Object.entries({ ...route.query, ...patch })) {
    const value = typeof v === 'string' ? v : Array.isArray(v) ? v[0] : undefined
    if (value !== undefined && value !== null && value !== '') {
      newQuery[k] = value
    }
  }
  router.push({ path: '/products', query: newQuery })
}

function onFilterUpdate(newFilter: FilterState) {
  // Reset page when filter changes
  updateQuery({
    theme_id: newFilter.theme_id,
    series_id: newFilter.series_id,
    difficulty: newFilter.difficulty,
    canvas_size: newFilter.canvas_size,
    tag_id: newFilter.tag_id,
    page: undefined,
  })
}

function onSortChange(newSort: SortMode) {
  updateQuery({ sort: newSort, page: undefined })
}

function onPageChange(newPage: number) {
  updateQuery({ page: newPage > 1 ? String(newPage) : undefined })
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

// Mobile filter drawer
const mobileFilterOpen = ref(false)
watch(
  () => route.fullPath,
  () => {
    mobileFilterOpen.value = false
  },
)

// Dev preview when DB empty
const isDev = import.meta.env.DEV
const PREVIEW_PRODUCTS: ProductBrief[] = Array.from({ length: 8 }, (_, i) => ({
  id: `preview-${i + 1}`,
  title: ['京都嵐山的秋', '安靜的廚房', '貓與初雪', '藍色海岸的午後', '櫻花盛開的午後', '老書桌與檯燈', '寵物熟睡時', '海邊的小屋'][i],
  cover_image_url: '',
  difficulty_range: [
    (['beginner', 'elementary', 'beginner', 'intermediate', 'beginner', 'elementary', 'beginner', 'intermediate'] as const)[i],
    (['beginner', 'elementary', 'beginner', 'intermediate', 'elementary', 'elementary', 'beginner', 'advanced'] as const)[i],
  ],
  price_min: [397, 397, 397, 540, 397, 460, 397, 540][i],
  price_max: [860, 860, 720, 1180, 860, 980, 720, 1180][i],
  is_preorder: i === 3 || i === 7,
}))
</script>

<template>
  <section class="page">
    <header class="page-header">
      <div>
        <div class="page-eyebrow">All Products</div>
        <h1 class="page-title">商品</h1>
      </div>
      <div class="page-meta">
        <button
          type="button"
          class="filter-trigger-mobile"
          @click="mobileFilterOpen = true"
        >
          <SlidersHorizontal />
          篩選
        </button>
        <span v-if="total > 0" class="result-count">共 {{ total }} 件</span>
        <ProductSort :model-value="sort" @update:model-value="onSortChange" />
      </div>
    </header>

    <div class="layout">
      <!-- Desktop filter -->
      <ProductFilter
        class="filter-desktop"
        :model-value="filter"
        @update:model-value="onFilterUpdate"
        @close="mobileFilterOpen = false"
      />

      <!-- Mobile drawer -->
      <Teleport to="body">
        <Transition name="drawer-overlay">
          <div
            v-if="mobileFilterOpen"
            class="drawer-overlay"
            @click="mobileFilterOpen = false"
          />
        </Transition>
        <Transition name="drawer-panel">
          <div v-if="mobileFilterOpen" class="drawer-panel">
            <ProductFilter
              :model-value="filter"
              @update:model-value="onFilterUpdate"
              @close="mobileFilterOpen = false"
            />
          </div>
        </Transition>
      </Teleport>

      <!-- Main grid area -->
      <div class="main">
        <div v-if="isPending" class="loading">
          <Loader2 :size="20" />
        </div>

        <template v-else-if="isEmpty">
          <div v-if="isDev" class="preview-note">
            <span class="preview-note-eyebrow">Design Preview</span>
            <span class="preview-note-text">商品建設中 — 以下為設計示意，dev mode only。</span>
          </div>
          <ProductGrid v-if="isDev" :products="PREVIEW_PRODUCTS" :preview="true" />
          <div v-else class="empty">
            <p class="empty-title">沒有符合條件的商品</p>
            <p class="empty-hint">試試調整篩選或回到全部商品。</p>
          </div>
        </template>

        <!-- 分組模式：每個系列一個 section（雜誌風） -->
        <template v-else-if="isGroupedMode">
          <SeriesProductGroup
            v-for="s in groupedSeries"
            :key="s.id"
            :series="s"
            :difficulty="filter.difficulty"
            :canvas-size="filter.canvas_size"
            :tag-id="filter.tag_id"
            :sort="sort"
            :limit="8"
          />
        </template>

        <!-- 平鋪模式：選定特定 series_id 時 -->
        <template v-else>
          <ProductGrid :products="flatItems" />
          <div class="page-footer">
            <Pagination
              :page="page"
              :total="flatTotal"
              :page-size="24"
              @change="onPageChange"
            />
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 48px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-line);
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}

.page-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 44px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}

.page-meta {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.result-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.filter-trigger-mobile {
  display: none;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 1px solid var(--color-line);
  padding: 8px 16px;
  border-radius: var(--radius-xs);
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-strong);
  cursor: pointer;
}
.filter-trigger-mobile :deep(svg) {
  width: 14px;
  height: 14px;
  stroke: currentColor;
  stroke-width: 1.5;
  fill: none;
}

.layout {
  display: flex;
  gap: 64px;
  align-items: flex-start;
}

.filter-desktop {
  position: sticky;
  top: 96px;
}

.main {
  flex: 1;
  min-width: 0;
}

.loading {
  padding: 96px 0;
  display: flex;
  justify-content: center;
  color: var(--color-ink-muted);
}
.loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5;
  fill: none;
  stroke: currentColor;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  padding: 96px 24px;
  text-align: center;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0;
  letter-spacing: 0.04em;
}

.preview-note {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-paper-deep);
  border: 1px dashed var(--color-line);
  border-radius: var(--radius-xs);
  margin-bottom: 28px;
}
.preview-note-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
}
.preview-note-text {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

.page-footer {
  margin-top: 64px;
  display: flex;
  justify-content: center;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
}

/* Mobile drawer */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(46, 40, 35, 0.4);
  z-index: 90;
}

.drawer-panel {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: min(320px, 90vw);
  background: var(--color-paper-canvas);
  border-right: 1px solid var(--color-line);
  z-index: 91;
  padding: 24px;
  overflow-y: auto;
}

.drawer-overlay-enter-active,
.drawer-overlay-leave-active {
  transition: opacity 200ms ease;
}
.drawer-overlay-enter-from,
.drawer-overlay-leave-to { opacity: 0; }

.drawer-panel-enter-active,
.drawer-panel-leave-active {
  transition: transform 240ms ease;
}
.drawer-panel-enter-from,
.drawer-panel-leave-to {
  transform: translateX(-100%);
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 64px; }
  .page-title { font-size: 36px; }
  .filter-desktop { display: none; }
  .filter-trigger-mobile { display: inline-flex; }
  .layout { gap: 0; }
}

@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    margin-bottom: 32px;
  }
  .page-title { font-size: 28px; }
  .page-meta { width: 100%; justify-content: space-between; }
}
</style>
