<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Layers, Star, ImageOff } from 'lucide-vue-next'
import { useSeriesDetailQuery } from '@/features/browse/queries'
import { useProductsQuery } from '@/features/products/queries'
import ProductCard from '@/features/products/components/ProductCard.vue'
import type { ProductBrief } from '@/features/products/api'

const route = useRoute()
const id = computed(() => String(route.params.id || ''))

const seriesQuery = useSeriesDetailQuery(id)
const series = computed(() => seriesQuery.data.value ?? null)

// 該系列中真實精選的商品（admin 在後台勾選 is_featured）
const featuredQuery = useProductsQuery(
  computed(() => ({
    series_id: id.value,
    featured: true,
    page: 1,
    page_size: 3,
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

// Pick 區塊：優先 admin 真實精選；無精選則 fallback 前 3 個（依 series_order）
const showcaseProducts = computed<ProductBrief[]>(() => {
  const featured = featuredQuery.data.value?.items ?? []
  if (featured.length > 0) return featured.slice(0, 3)
  return allProducts.value.slice(0, 3)
})

// 排除 showcase 中已顯示的，剩下的放下方
const restProducts = computed<ProductBrief[]>(() => {
  const showcaseIds = new Set(showcaseProducts.value.map((p) => p.id))
  return allProducts.value.filter((p) => !showcaseIds.has(p.id))
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

          <!-- 右：精選商品展示 -->
          <div class="hero-showcase">
            <div class="showcase-eyebrow">— Pick of this Series —</div>

            <!-- 有商品時：1 大 + 2 小 雜誌排版 -->
            <template v-if="showcaseProducts.length > 0">
              <div
                class="showcase-grid"
                :class="`showcase-grid-${showcaseProducts.length}`"
              >
                <div class="showcase-main">
                  <ProductCard :product="showcaseProducts[0]" />
                </div>
                <div v-if="showcaseProducts.length > 1" class="showcase-side">
                  <div
                    v-for="p in showcaseProducts.slice(1)"
                    :key="p.id"
                    class="showcase-side-item"
                  >
                    <ProductCard :product="p" />
                  </div>
                </div>
              </div>
            </template>

            <!-- 無商品 fallback -->
            <div v-else class="showcase-fallback">
              <div class="fallback-band">
                <ImageOff class="fallback-icon" />
                <span class="fallback-name">{{ series.name }}</span>
                <span class="fallback-text">本系列商品準備中</span>
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
    var(--color-paper-surface) 0%,
    var(--color-paper-deep) 60%,
    var(--color-accent-tint) 130%
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
  background: rgba(237, 228, 211, 0.6);
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

.showcase-grid {
  display: grid;
  gap: 16px;
}
/* 1 商品 → 占滿；2-3 商品 → 1 大 + 1-2 小 */
.showcase-grid-1 .showcase-main { grid-column: 1 / -1; }
.showcase-grid-1 .showcase-side { display: none; }
.showcase-grid-2,
.showcase-grid-3 {
  grid-template-columns: 1.4fr 1fr;
}
.showcase-side {
  display: grid;
  gap: 16px;
}

.showcase-side-item :deep(.title) { font-size: 16px !important; }
.showcase-side-item :deep(.body) { padding: 14px 14px 16px !important; }
.showcase-side-item :deep(.price-row) { padding-top: 10px !important; }

.showcase-fallback {
  aspect-ratio: 4 / 5;
  position: relative;
}
.fallback-band {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(
    135deg,
    var(--color-paper-deep) 0%,
    var(--color-accent) 55%,
    var(--color-accent-deep) 110%
  );
  border: 1px solid var(--color-line-subtle);
}
.fallback-icon {
  width: 40px; height: 40px;
  stroke: var(--color-paper-canvas); stroke-width: 1.25; fill: none;
  opacity: 0.7;
}
.fallback-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.12em;
  color: var(--color-paper-canvas);
  text-shadow: 0 4px 16px rgba(46, 40, 35, 0.25);
}
.fallback-text {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(245, 241, 232, 0.85);
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
