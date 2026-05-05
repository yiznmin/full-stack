<script setup lang="ts">
import { computed, toRef } from 'vue'
import { RouterLink } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { useProductsQuery } from '../queries'
import type { Difficulty, SortMode } from '../api'
import ProductCard from './ProductCard.vue'
import type { SeriesListItem } from '@/features/browse/api'

const props = defineProps<{
  series: SeriesListItem
  /** 額外 filter 透傳：difficulty / canvas_size / tag_id / sort */
  difficulty?: Difficulty
  canvasSize?: string
  tagId?: string
  sort?: SortMode
  /** 每組系列最多顯示的商品數，超過時顯示「看全部」 */
  limit?: number
}>()

const params = computed(() => ({
  series_id: props.series.id,
  difficulty: props.difficulty,
  canvas_size: props.canvasSize,
  tag_id: props.tagId,
  page: 1,
  page_size: props.limit ?? 8,
  sort: props.sort ?? 'latest',
}))

const seriesRef = toRef(props, 'series')
const productsQuery = useProductsQuery(params)
const items = computed(() => productsQuery.data.value?.items ?? [])
const total = computed(() => productsQuery.data.value?.total ?? 0)
const hasMore = computed(() => total.value > items.value.length)

const seriesLink = computed(() => `/series/${seriesRef.value.id}`)
const filterLink = computed(() => ({
  path: '/products',
  query: {
    series_id: seriesRef.value.id,
    ...(props.difficulty ? { difficulty: props.difficulty } : {}),
    ...(props.canvasSize ? { canvas_size: props.canvasSize } : {}),
    ...(props.tagId ? { tag_id: props.tagId } : {}),
  },
}))

const isEmpty = computed(
  () => !productsQuery.isPending.value && items.value.length === 0,
)
</script>

<template>
  <section v-if="!isEmpty" class="group">
    <header class="group-header">
      <div class="group-eyebrow">
        <span v-if="series.theme_name" class="eyebrow-theme">{{ series.theme_name }}</span>
        <span v-if="series.theme_name" class="eyebrow-divider">/</span>
        <span class="eyebrow-tag">— Series —</span>
      </div>
      <div class="group-title-row">
        <RouterLink :to="seriesLink" class="group-title">
          {{ series.name }}
        </RouterLink>
        <span class="group-count">{{ series.product_count }} 件</span>
      </div>
      <p v-if="series.description" class="group-desc">{{ series.description }}</p>
      <div class="group-rule">
        <span class="rule-line"></span>
        <span class="rule-dot"></span>
        <span class="rule-line"></span>
      </div>
    </header>

    <div v-if="productsQuery.isPending.value" class="group-loading">
      <Loader2 :size="18" />
    </div>

    <div v-else class="group-grid">
      <ProductCard v-for="p in items" :key="p.id" :product="p" />
    </div>

    <div v-if="hasMore" class="group-footer">
      <RouterLink :to="filterLink" class="see-more">
        看 {{ series.name }} 全部 {{ total }} 件 →
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.group {
  margin-bottom: 96px;
}
.group:last-child { margin-bottom: 0; }

.group-header {
  margin-bottom: 36px;
}

.group-eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 14px;
}
.eyebrow-theme { color: var(--color-accent); }
.eyebrow-divider { opacity: 0.4; }

.group-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 12px;
}

.group-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 32px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  text-decoration: none;
  transition: color 150ms;
}
.group-title:hover { color: var(--color-accent-deep); }

.group-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  flex-shrink: 0;
}

.group-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.85;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 20px;
  max-width: 640px;
  white-space: pre-wrap;
}

.group-rule {
  display: flex;
  align-items: center;
  gap: 10px;
}
.rule-line {
  flex: 1;
  height: 1px;
  background: var(--color-line-subtle);
  max-width: 60px;
}
.rule-line:last-of-type {
  flex: 0;
  width: 200px;
  max-width: none;
  background: linear-gradient(to right, var(--color-line-subtle), transparent);
}
.rule-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  flex-shrink: 0;
}

.group-loading {
  padding: 48px 0;
  display: flex;
  justify-content: center;
  color: var(--color-ink-muted);
}
.group-loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5; fill: none; stroke: currentColor;
}
@keyframes spin { to { transform: rotate(360deg); } }

.group-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 28px;
}

.group-footer {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--color-line-subtle);
  text-align: right;
}

.see-more {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  transition: color 150ms;
}
.see-more:hover { color: var(--color-accent-deep); }

@media (max-width: 1279px) {
  .group-grid { grid-template-columns: repeat(3, 1fr); gap: 24px; }
  .group-title { font-size: 28px; }
}
@media (max-width: 1023px) {
  .group { margin-bottom: 72px; }
  .group-grid { grid-template-columns: repeat(2, 1fr); gap: 20px; }
  .group-title { font-size: 24px; }
}
@media (max-width: 767px) {
  .group { margin-bottom: 56px; }
  .group-grid { grid-template-columns: 1fr; gap: 18px; }
  .group-title { font-size: 22px; }
  .group-title-row { flex-direction: column; align-items: flex-start; gap: 6px; }
}
</style>
