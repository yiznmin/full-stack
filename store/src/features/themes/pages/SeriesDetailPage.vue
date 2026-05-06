<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Layers, Star } from 'lucide-vue-next'
import { useSeriesDetailQuery } from '@/features/browse/queries'
import { useProductsQuery } from '@/features/products/queries'
import ProductCard from '@/features/products/components/ProductCard.vue'
import type { ProductBrief } from '@/features/products/api'

const route = useRoute()
const id = computed(() => String(route.params.id || ''))

const seriesQuery = useSeriesDetailQuery(id)
const series = computed(() => seriesQuery.data.value ?? null)

// 該系列中真實精選的商品（admin 在後台勾選 is_featured）— 拼貼最多 5 格
const featuredQuery = useProductsQuery(
  computed(() => ({
    series_id: id.value,
    featured: true,
    page: 1,
    page_size: 5,
  })),
)

const allProducts = computed<ProductBrief[]>(() => {
  if (!series.value) return []
  return series.value.products.map((p) => ({
    id: p.id,
    title: p.title,
    cover_image_url: p.cover_image_url,
    difficulty_range: p.difficulty_range as ProductBrief['difficulty_range'],
    price_min: p.price_min,
    price_max: p.price_max,
    is_preorder: p.is_preorder,
  }))
})

// 拼貼區塊：優先真實精選；無則 fallback 前 5 個
const collageProducts = computed<ProductBrief[]>(() => {
  const featured = featuredQuery.data.value?.items ?? []
  if (featured.length > 0) return featured.slice(0, 5)
  return allProducts.value.slice(0, 5)
})

// 5 格拼貼位置 — 依 product 數量決定要填幾格，不夠的位置用淺色裝飾格補
// 位置：a (大左 2x2) / b (右上 1x1) / c (右下 1x1) / d (左下 1x1) / e (中下 1x1)
const collageSlots = computed(() => {
  const list = collageProducts.value
  const slots: Array<{ key: 'a' | 'b' | 'c' | 'd' | 'e'; product: ProductBrief | null; tone: number }> = [
    { key: 'a', product: list[0] ?? null, tone: 0 },
    { key: 'b', product: list[1] ?? null, tone: 1 },
    { key: 'c', product: list[2] ?? null, tone: 2 },
    { key: 'd', product: list[3] ?? null, tone: 3 },
    { key: 'e', product: list[4] ?? null, tone: 0 },
  ]
  return slots
})

// 4 種極簡裝飾色 — 紙本灰白＋微 taupe，配合 cell 留白美學
const TONES = [
  'linear-gradient(135deg, #FBF8F1 0%, #EBE2D0 110%)',
  'linear-gradient(160deg, #F6F2EA 0%, #DDD0BB 120%)',
  'linear-gradient(135deg, #EFE9DA 0%, #C8B79C 140%)',
  'linear-gradient(135deg, #FBF8F1 0%, #E8DFCD 100%)',
]
function toneFor(idx: number) {
  return TONES[idx % TONES.length]
}

// 排除 collage 中已顯示的，剩下的放下方
const restProducts = computed<ProductBrief[]>(() => {
  const usedIds = new Set(
    collageProducts.value.map((p) => p.id),
  )
  return allProducts.value.filter((p) => !usedIds.has(p.id))
})
</script>

<template>
  <section v-if="seriesQuery.isPending.value" class="page page-loading">
    <Loader2 :size="20" />
  </section>

  <section v-else-if="seriesQuery.isError.value || !series" class="page page-empty">
    <Layers class="empty-icon" />
    <h1 class="empty-title">找不到這個系列</h1>
    <p class="empty-hint">系列已下架或網址錯誤。</p>
    <RouterLink to="/themes" class="empty-cta">回主題列表</RouterLink>
  </section>

  <section v-else class="page">
    <!-- Hero — 雜誌左右佈局 -->
    <header class="hero">
      <nav class="breadcrumb">
        <RouterLink to="/themes">主題</RouterLink>
        <span>/</span>
        <RouterLink v-if="series.theme_id" :to="`/themes/${series.theme_id}`">
          {{ series.theme_name }}
        </RouterLink>
        <span v-if="series.theme_id">/</span>
        <span class="current">{{ series.name }}</span>
      </nav>

      <div class="hero-band">
        <span class="corner corner-tl"></span>
        <span class="corner corner-tr"></span>
        <span class="corner corner-bl"></span>
        <span class="corner corner-br"></span>

        <span class="watermark">SERIES</span>

        <div class="hero-layout">
          <!-- 左：系列說明 -->
          <div class="hero-info">
            <div class="hero-eyebrow">
              <span class="eyebrow-text">— Series —</span>
              <span v-if="series.is_featured" class="featured-mark">
                <Star class="featured-icon" />
                Featured
              </span>
            </div>

            <h1 class="hero-title">{{ series.name }}</h1>

            <div class="hero-rule">
              <span class="rule-line"></span>
              <span class="rule-dot"></span>
              <span class="rule-line"></span>
            </div>

            <p v-if="series.description" class="hero-desc">{{ series.description }}</p>
            <p v-else class="hero-desc hero-desc-empty">— 一個還在悄悄誕生的系列 —</p>

            <div class="hero-meta">
              <span class="meta-num">{{ series.products.length }}</span>
              <span class="meta-label">件商品</span>
              <span v-if="series.theme_name" class="meta-divider">·</span>
              <span v-if="series.theme_name" class="meta-theme">{{ series.theme_name }}</span>
            </div>
          </div>

          <!-- 右：拼貼/collage 雜誌格（5 格不對稱） -->
          <div class="hero-showcase">
            <div class="showcase-eyebrow">— Pick of this Series —</div>

            <div class="collage">
              <RouterLink
                v-for="slot in collageSlots"
                :key="slot.key"
                :class="['cell', `cell-${slot.key}`, { 'cell-empty': !slot.product }]"
                :to="slot.product ? `/products/${slot.product.id}` : `#`"
                @click="!slot.product && $event.preventDefault()"
              >
                <template v-if="slot.product">
                  <img
                    v-if="slot.product.cover_image_url"
                    :src="slot.product.cover_image_url"
                    :alt="slot.product.title"
                    class="cell-img"
                    loading="lazy"
                  />
                  <div
                    v-else
                    class="cell-tone"
                    :style="{ background: toneFor(slot.tone) }"
                  ></div>
                  <div class="cell-overlay">
                    <div class="cell-title">{{ slot.product.title }}</div>
                    <div class="cell-price">NT$ {{ slot.product.price_min.toLocaleString() }} 起</div>
                  </div>
                </template>
                <template v-else>
                  <div
                    class="cell-tone cell-tone-empty"
                    :style="{ background: toneFor(slot.tone) }"
                  ></div>
                </template>
              </RouterLink>

              <div v-if="collageProducts.length === 0" class="collage-empty-hint">
                <span>{{ series.name }} · 商品準備中</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- 該系列其他商品（非精選）-->
    <section v-if="restProducts.length > 0" class="products-section">
      <div class="section-header">
        <div class="section-eyebrow">— More in this Series —</div>
        <h2 class="section-title">系列其他商品</h2>
      </div>
      <div class="products-grid">
        <ProductCard v-for="p in restProducts" :key="p.id" :product="p" />
      </div>
    </section>
  </section>
</template>

<style scoped>
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 56px 56px 96px;
}

.page-loading,
.page-empty {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-align: center;
}
.page-loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5; fill: none; stroke: currentColor;
  color: var(--color-ink-muted);
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-icon {
  width: 32px; height: 32px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none;
  margin-bottom: 24px;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 16px;
}
.empty-hint { font-size: 13px; color: var(--color-ink-muted); letter-spacing: 0.04em; margin: 0 0 24px; }
.empty-cta {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}

/* ── Hero ── */
.hero { margin-bottom: 80px; }

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 32px;
  flex-wrap: wrap;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

.hero-band {
  position: relative;
  padding: 80px 64px;
  background: linear-gradient(
    135deg,
    #FBF8F1 0%,
    #F6F2EA 55%,
    #EBE2D0 130%
  );
  border: 1px solid var(--color-line-subtle);
  overflow: hidden;
}

.corner {
  position: absolute;
  width: 32px; height: 32px;
  border-color: var(--color-ink-strong);
  border-style: solid;
  border-width: 0;
  opacity: 0.45;
  pointer-events: none;
  z-index: 1;
}
.corner-tl { top: 16px; left: 16px; border-top-width: 1.5px; border-left-width: 1.5px; }
.corner-tr { top: 16px; right: 16px; border-top-width: 1.5px; border-right-width: 1.5px; }
.corner-bl { bottom: 16px; left: 16px; border-bottom-width: 1.5px; border-left-width: 1.5px; }
.corner-br { bottom: 16px; right: 16px; border-bottom-width: 1.5px; border-right-width: 1.5px; }

.watermark {
  position: absolute;
  top: 32px;
  left: -12px;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 168px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  opacity: 0.045;
  user-select: none;
  line-height: 1;
  pointer-events: none;
}

.hero-layout {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr 1.05fr;
  gap: 64px;
  align-items: center;
}

/* 左：info */
.hero-info {
  display: flex;
  flex-direction: column;
}

.hero-eyebrow {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.eyebrow-text {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-accent);
}

.featured-mark {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-state-warning);
  padding: 4px 10px;
  background: rgba(184, 145, 73, 0.15);
  border: 1px solid var(--color-state-warning);
  border-radius: var(--radius-xs);
}
.featured-icon {
  width: 11px; height: 11px;
  stroke: currentColor; fill: currentColor; stroke-width: 1.5;
}

.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 56px;
  line-height: 1.25;
  letter-spacing: 0.1em;
  color: var(--color-ink-strong);
  margin: 0 0 28px;
  word-break: keep-all;
  overflow-wrap: break-word;
}

.hero-rule {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}
.rule-line {
  width: 60px; height: 1px;
  background: var(--color-accent-soft);
}
.rule-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
}

.hero-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  line-height: 1.95;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 32px;
  white-space: pre-wrap;
  max-width: 460px;
}
.hero-desc-empty { color: var(--color-ink-muted); font-style: italic; font-size: 14px; }

.hero-meta {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  align-self: flex-start;
  padding: 10px 20px;
  background: rgba(246, 242, 234, 0.7);
  backdrop-filter: blur(4px);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.meta-num {
  font-family: var(--font-mono);
  font-size: 18px;
  color: var(--color-ink-strong);
  font-weight: 500;
}
.meta-label,
.meta-theme {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.meta-divider { color: var(--color-line); margin: 0 4px; }
.meta-theme { color: var(--color-accent); }

/* 右：showcase */
.hero-showcase {
  display: flex;
  flex-direction: column;
}

.showcase-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 20px;
  text-align: right;
}

/* ── Collage 拼貼 5 格 ── */
.collage {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 10px;
  aspect-ratio: 5 / 4;
  position: relative;
}
.cell {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-surface);
  text-decoration: none;
  color: inherit;
  transition: transform 400ms ease, box-shadow 300ms;
  cursor: pointer;
}
.cell:not(.cell-empty):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 22px rgba(46, 40, 35, 0.08);
}
.cell-empty { cursor: default; }
.cell-empty:hover { transform: none; box-shadow: none; }

/* 5 格 magazine 排版：a 大左 2x2、b 右上、c 左下、d 中下、e 右下 */
.cell-a { grid-column: 1; grid-row: 1 / span 2; }
.cell-b { grid-column: 2 / span 2; grid-row: 1; }
.cell-c { grid-column: 2; grid-row: 2; }
.cell-d { grid-column: 3; grid-row: 2; }
.cell-e { display: none; } /* 5 格但實作 4 格雜誌；e 預留 */

.cell-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  filter: sepia(0.05) saturate(0.95);
  transition: transform 600ms ease;
}
.cell:not(.cell-empty):hover .cell-img {
  transform: scale(1.04);
}

.cell-tone {
  width: 100%;
  height: 100%;
}
.cell-tone-empty {
  position: relative;
}
.cell-tone-empty::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.25), transparent 40%),
    radial-gradient(circle at 70% 70%, rgba(106, 74, 52, 0.06), transparent 50%);
}

.cell-overlay {
  position: absolute;
  inset: auto 0 0 0;
  padding: 12px 14px 12px;
  background: linear-gradient(to top, rgba(46, 40, 35, 0.62), rgba(46, 40, 35, 0));
  color: var(--color-paper-canvas);
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 240ms, transform 240ms;
}
.cell:hover .cell-overlay {
  opacity: 1;
  transform: translateY(0);
}
.cell-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.cell-price {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  opacity: 0.85;
}
.cell-a .cell-title { font-size: 18px; }
.cell-a .cell-overlay { padding: 16px 18px 16px; }

.collage-empty-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.12em;
  color: var(--color-ink-strong);
  opacity: 0.55;
  text-shadow: 0 1px 3px rgba(247, 240, 223, 0.6);
}

/* ── Products section ── */
.products-section {
  padding-top: 32px;
  border-top: 1px solid var(--color-line);
}
.section-header {
  text-align: center;
  margin-bottom: 48px;
}
.section-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}
.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0;
}

.products-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 28px;
}

@media (max-width: 1279px) {
  .hero-title { font-size: 44px; }
  .watermark { font-size: 132px; }
  .products-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .hero-band { padding: 56px 32px; }
  .hero-layout { grid-template-columns: 1fr; gap: 48px; }
  .hero-title { font-size: 36px; }
  .watermark { font-size: 96px; }
  .corner { width: 24px; height: 24px; }
  .corner-tl { top: 12px; left: 12px; }
  .corner-tr { top: 12px; right: 12px; }
  .corner-bl { bottom: 12px; left: 12px; }
  .corner-br { bottom: 12px; right: 12px; }
  .showcase-eyebrow { text-align: left; }
  .products-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .hero-band { padding: 48px 24px 40px; }
  .hero-title { font-size: 30px; letter-spacing: 0.08em; }
  .hero-desc { font-size: 14px; }
  .watermark { font-size: 64px; top: 20px; left: -8px; }
  .showcase-grid-2,
  .showcase-grid-3 {
    grid-template-columns: 1fr;
  }
  .products-grid { grid-template-columns: 1fr; }
}
</style>
