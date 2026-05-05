<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { useProductsQuery } from '@/features/products/queries'
import ProductCard from '@/features/products/components/ProductCard.vue'
import type { ProductBrief } from '@/features/products/api'

const productsQuery = useProductsQuery({ sort: 'latest', page: 1, page_size: 4 })

const items = computed(() => productsQuery.data.value?.items ?? [])
const isEmpty = computed(
  () => !productsQuery.isPending.value && items.value.length === 0,
)

// Dev 預覽用：production DB 還沒商品時，dev 模式下顯示 4 張示意卡片，
// 讓使用者看 ProductCard 在 grid 內的視覺。Production build 不顯示。
const isDev = import.meta.env.DEV
const PREVIEW_PRODUCTS: ProductBrief[] = [
  {
    id: 'preview-1',
    title: '京都嵐山的秋',
    cover_image_url: '',
    difficulty_range: ['beginner', 'beginner'],
    price_min: 397,
    price_max: 860,
    is_preorder: false,
  },
  {
    id: 'preview-2',
    title: '安靜的廚房',
    cover_image_url: '',
    difficulty_range: ['elementary', 'elementary'],
    price_min: 397,
    price_max: 860,
    is_preorder: false,
  },
  {
    id: 'preview-3',
    title: '貓與初雪',
    cover_image_url: '',
    difficulty_range: ['beginner', 'beginner'],
    price_min: 397,
    price_max: 720,
    is_preorder: false,
  },
  {
    id: 'preview-4',
    title: '藍色海岸的午後',
    cover_image_url: '',
    difficulty_range: ['intermediate', 'intermediate'],
    price_min: 540,
    price_max: 1180,
    is_preorder: true,
  },
]
</script>

<template>
  <section class="section">
    <div class="section-header">
      <div>
        <div class="section-eyebrow">No. 01 — Featured</div>
        <h2 class="section-title">最新上架</h2>
      </div>
      <RouterLink to="/products?sort=latest" class="section-link">看全部 →</RouterLink>
    </div>

    <div v-if="productsQuery.isPending.value" class="loading">
      <Loader2 :size="20" />
    </div>

    <template v-else-if="isEmpty">
      <div v-if="isDev" class="preview-note">
        <span class="preview-note-eyebrow">Design Preview</span>
        <span class="preview-note-text">商品建設中 — 以下為設計示意，dev mode only。</span>
      </div>
      <div v-if="isDev" class="grid">
        <ProductCard
          v-for="(p, idx) in PREVIEW_PRODUCTS"
          :key="p.id"
          :product="p"
          :number="String(idx + 1).padStart(2, '0')"
          :preview="true"
        />
      </div>
      <div v-else class="empty">
        <p class="empty-title">商品準備中</p>
        <p class="empty-hint">還沒有商品上架。</p>
        <RouterLink to="/custom" class="empty-cta">用照片客製 →</RouterLink>
      </div>
    </template>

    <div v-else class="grid">
      <ProductCard
        v-for="(p, idx) in items"
        :key="p.id"
        :product="p"
        :number="String(idx + 1).padStart(2, '0')"
      />
    </div>
  </section>
</template>

<style scoped>
.section {
  max-width: 1440px;
  margin: 0 auto;
  padding: 96px 56px;
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 56px;
  border-bottom: 1px solid var(--color-line);
  padding-bottom: 24px;
}

.section-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 16px;
}

.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}

.section-link {
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  transition: color 150ms;
}
.section-link:hover {
  color: var(--color-accent-deep);
}

.loading {
  padding: 64px 0;
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
  padding: 64px 24px;
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
  margin: 0 0 24px;
  letter-spacing: 0.04em;
}
.empty-cta {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
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

.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 32px;
}

@media (max-width: 1279px) {
  .grid { grid-template-columns: repeat(3, 1fr); gap: 28px; }
}
@media (max-width: 1023px) {
  .section { padding: 64px 32px; }
  .grid { grid-template-columns: repeat(2, 1fr); gap: 24px; }
  .section-title { font-size: 28px; }
}
@media (max-width: 767px) {
  .section { padding: 48px 24px; }
  .grid { grid-template-columns: 1fr; gap: 20px; }
  .section-header { margin-bottom: 32px; padding-bottom: 16px; }
}
</style>
