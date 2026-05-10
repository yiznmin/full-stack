<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Layers, Star } from 'lucide-vue-next'
import {
  useSeriesDetailQuery,
  useSeriesQuery,
  useFeaturedSeriesQuery,
} from '@/features/browse/queries'
import { useProductsQuery } from '@/features/products/queries'
import ProductCard from '@/features/products/components/ProductCard.vue'
import SeriesCard from '@/features/themes/components/SeriesCard.vue'
import type { ProductBrief } from '@/features/products/api'

const route = useRoute()
const id = computed(() => String(route.params.id || ''))

const seriesQuery = useSeriesDetailQuery(id)
const series = computed(() => seriesQuery.data.value ?? null)

// 該系列真實精選商品（admin 勾選 is_featured） — Pick 最多 4 個
const featuredQuery = useProductsQuery(
  computed(() => ({
    series_id: id.value,
    featured: true,
    page: 1,
    page_size: 4,
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

// Hero 4 cell mosaic — 優先 admin 真實精選 4 個；無則 fallback 前 4 個
const heroCells = computed<Array<ProductBrief | null>>(() => {
  const featured = featuredQuery.data.value?.items ?? []
  const list = featured.length > 0 ? featured.slice(0, 4) : allProducts.value.slice(0, 4)
  return [list[0] ?? null, list[1] ?? null, list[2] ?? null, list[3] ?? null]
})

// 4 種雜誌 mood 漸層：苔綠 / 舊玫瑰 / 焦糖 / 煙青（從乳白 surface 起色）
const CELL_TONES = [
  'linear-gradient(135deg, #FFFCF4 0%, #DDE5D2 70%, #97A687 130%)',
  'linear-gradient(135deg, #FFFCF4 0%, #ECDFDA 70%, #C9A8A8 130%)',
  'linear-gradient(135deg, #FFFCF4 0%, #ECE3D2 70%, #B8A084 130%)',
  'linear-gradient(135deg, #FFFCF4 0%, #DCE3E2 70%, #98ABA8 130%)',
]
function toneFor(idx: number) {
  return CELL_TONES[idx % CELL_TONES.length]
}

// 同主題其他系列（沒商品時用來導覽用戶）；無 theme_id 則 fallback 到精選系列
const themeId = computed(() => series.value?.theme_id ?? undefined)
const siblingSeriesQuery = useSeriesQuery(themeId)
const featuredSeriesFallback = useFeaturedSeriesQuery()

const otherSeries = computed(() => {
  const currentId = series.value?.id
  const sameTheme = (siblingSeriesQuery.data.value?.items ?? [])
    .filter((s) => s.id !== currentId)
  if (sameTheme.length > 0) return sameTheme.slice(0, 4)
  return (featuredSeriesFallback.data.value?.items ?? [])
    .filter((s) => s.id !== currentId)
    .slice(0, 4)
})

const otherSeriesEyebrow = computed(() =>
  series.value?.theme_name
    ? `More in ${series.value.theme_name}`
    : 'Featured Series',
)
const otherSeriesTitle = computed(() =>
  series.value?.theme_name
    ? `${series.value.theme_name} 其他系列`
    : '精選系列',
)
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
    <!-- breadcrumb -->
    <nav class="breadcrumb">
      <RouterLink to="/themes">主題</RouterLink>
      <span>/</span>
      <RouterLink v-if="series.theme_id" :to="`/themes/${series.theme_id}`">
        {{ series.theme_name }}
      </RouterLink>
      <span v-if="series.theme_id">/</span>
      <span class="current">{{ series.name }}</span>
    </nav>

    <!-- Hero header — moodboard 風：左側標題塊 + 右上小色票 -->
    <header class="hero">
      <div class="hero-text">
        <div class="hero-eyebrow">
          <span class="eyebrow-text">Series</span>
          <span v-if="series.is_featured" class="featured-mark">
            <Star class="featured-icon" />Featured
          </span>
        </div>

        <h1 class="hero-title">{{ series.name }}</h1>

        <p v-if="series.description" class="hero-desc">{{ series.description }}</p>
        <p v-else class="hero-desc hero-desc-empty">— 一個還在悄悄誕生的系列 —</p>

        <div class="hero-meta">
          <span class="meta-num">{{ series.products.length }}</span>
          <span class="meta-label">件商品</span>
          <span v-if="series.theme_name" class="meta-divider">·</span>
          <RouterLink
            v-if="series.theme_id"
            :to="`/themes/${series.theme_id}`"
            class="meta-theme"
          >{{ series.theme_name }}</RouterLink>
        </div>
      </div>

    </header>

    <!-- 系列有自訂 cover → 全幅 hero banner（admin 上傳 sample_cover_image_url）-->
    <section v-if="series.sample_cover_image_url" class="hero-banner" aria-label="系列封面">
      <img
        :src="series.sample_cover_image_url"
        :alt="series.name"
        class="hero-banner-img"
        loading="lazy"
      />
      <div class="hero-banner-veil"></div>
    </section>

    <!-- 沒自訂 cover → 全寬 magazine mosaic 用商品圖拼貼 fallback -->
    <section v-else class="mosaic" aria-label="系列雜誌拼貼">
      <template v-for="(p, idx) in heroCells" :key="idx">
        <RouterLink
          v-if="p"
          :to="`/products/${p.id}`"
          :class="['mosaic-cell', `cell-${idx}`]"
        >
          <img
            v-if="p.cover_image_url"
            :src="p.cover_image_url"
            :alt="p.title"
            class="mosaic-img"
            loading="lazy"
          />
          <div
            v-else
            class="mosaic-tone"
            :style="{ background: toneFor(idx) }"
          ></div>
          <div class="mosaic-overlay">
            <div class="mosaic-title">{{ p.title }}</div>
            <div class="mosaic-price">NT$ {{ p.price_min.toLocaleString() }} 起</div>
          </div>
        </RouterLink>
        <div
          v-else
          :class="['mosaic-cell', 'cell-empty', `cell-${idx}`]"
          :style="{ background: toneFor(idx) }"
        >
          <div v-if="idx === 0" class="cell-deco cell-deco-main">
            <span class="deco-watermark" aria-hidden="true">Y</span>
            <div class="deco-eyebrow">Vol.</div>
            <div class="deco-num">{{ String(series.products.length).padStart(2, '0') }}</div>
            <div class="deco-rule"></div>
            <div class="deco-meta">{{ series.theme_name || 'Atelier' }}</div>
          </div>
          <div v-else-if="idx === 1" class="cell-deco">
            <div class="deco-word-pair">
              <span class="deco-word">M</span><span class="deco-word-soft">ood</span>
            </div>
            <div class="deco-caption">本系列氛圍</div>
          </div>
          <div v-else-if="idx === 2" class="cell-deco">
            <div class="deco-word-pair">
              <span class="deco-word">S</span><span class="deco-word-soft">eries</span>
            </div>
            <div class="deco-caption">{{ series.theme_name || 'Atelier' }}</div>
          </div>
          <div v-else class="cell-deco cell-deco-tall">
            <div class="deco-eyebrow">— Coming Soon —</div>
            <div class="deco-headline">
              quietly<br /><em>under preparation</em>
            </div>
            <RouterLink to="/products" class="deco-link">
              看其他商品 →
            </RouterLink>
          </div>
        </div>
      </template>
    </section>

    <!-- 該系列全部商品（陣列排列） -->
    <section v-if="allProducts.length > 0" class="products-section">
      <div class="section-header">
        <span class="section-eyebrow">All Products</span>
        <h2 class="section-title">本系列全部商品</h2>
        <span class="section-count">{{ allProducts.length }} 件</span>
      </div>
      <div class="products-grid">
        <ProductCard v-for="p in allProducts" :key="p.id" :product="p" />
      </div>
    </section>

    <!-- 沒商品時：導覽其他系列（同主題優先，否則精選） -->
    <section v-else-if="otherSeries.length > 0" class="others-section">
      <div class="section-header">
        <span class="section-eyebrow">{{ otherSeriesEyebrow }}</span>
        <h2 class="section-title">{{ otherSeriesTitle }}</h2>
        <span class="section-count">{{ otherSeries.length }} 個系列</span>
      </div>
      <div class="others-grid">
        <SeriesCard
          v-for="(s, idx) in otherSeries"
          :key="s.id"
          :series="s"
          :index="idx"
        />
      </div>
      <div class="others-footer">
        <RouterLink to="/themes" class="others-link">
          看全部主題與系列 →
        </RouterLink>
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

/* ── Breadcrumb ── */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 56px;
  flex-wrap: wrap;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

/* ── Hero (moodboard 風 — 純標題塊) ── */
.hero {
  margin: 0 0 32px;
}

.hero-text { display: flex; flex-direction: column; max-width: 720px; }

.hero-eyebrow {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.eyebrow-text {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.34em;
  text-transform: uppercase;
  color: var(--color-fresh);
  position: relative;
  padding-left: 18px;
}
.eyebrow-text::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 12px;
  height: 1px;
  background: var(--color-fresh);
}

.featured-mark {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent-wine);
  padding: 3px 9px;
  border: 1px solid var(--color-accent-wine);
  border-radius: var(--radius-xs);
  background: transparent;
}
.featured-icon {
  width: 10px; height: 10px;
  stroke: currentColor; fill: currentColor; stroke-width: 1.5;
}

.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 64px;
  line-height: 1.18;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0 0 28px;
  word-break: keep-all;
  overflow-wrap: break-word;
}

.hero-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 17px;
  line-height: 2;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 32px;
  white-space: pre-wrap;
  max-width: 560px;
}

.hero-meta {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  align-self: flex-start;
  padding-top: 20px;
  border-top: 1px solid var(--color-line-subtle);
}
.meta-num {
  font-family: var(--font-mono);
  font-size: 16px;
  color: var(--color-ink-strong);
  font-weight: 500;
}
.meta-label {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.meta-divider { color: var(--color-line); margin: 0 4px; }
.meta-theme {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  transition: color 150ms;
}
.meta-theme:hover { color: var(--color-accent-deep); }

/* ── Hero banner (系列有自訂 cover 時) ── */
.hero-banner {
  position: relative;
  width: 100%;
  aspect-ratio: 21 / 9;
  margin: 0 0 56px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-paper-deep);
}
.hero-banner-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.hero-banner-veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0) 50%,
    rgba(0, 0, 0, 0.18) 100%
  );
}
@media (max-width: 767px) {
  .hero-banner { aspect-ratio: 16 / 10; margin-bottom: 32px; }
}

/* ── Mosaic (全寬 magazine 4 格不對稱) ── */
.mosaic {
  display: grid;
  grid-template-columns: 0.85fr 1.4fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 14px;
  height: 540px;
  margin-bottom: 96px;
}
.mosaic-cell {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-surface);
  text-decoration: none;
  color: inherit;
  transition: transform 400ms ease, box-shadow 300ms;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mosaic-cell:not(.cell-empty):hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(31, 26, 21, 0.06);
}
.cell-empty { cursor: default; }

/* 4 格 magazine 排版：A tall left / B wide top / C wide bot / D tall right */
.cell-0 { grid-column: 1; grid-row: 1 / span 2; }
.cell-1 { grid-column: 2; grid-row: 1; }
.cell-2 { grid-column: 2; grid-row: 2; }
.cell-3 { grid-column: 3; grid-row: 1 / span 2; }

.mosaic-img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  filter: sepia(0.04) saturate(0.95);
  transition: transform 600ms ease;
}
.mosaic-cell:not(.cell-empty):hover .mosaic-img {
  transform: scale(1.04);
}
.mosaic-tone { width: 100%; height: 100%; }

.mosaic-overlay {
  position: absolute;
  inset: auto 0 0 0;
  padding: 14px 18px;
  background: linear-gradient(to top, rgba(31, 26, 21, 0.62), rgba(31, 26, 21, 0));
  color: var(--color-paper-canvas);
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 240ms, transform 240ms;
}
.mosaic-cell:hover .mosaic-overlay {
  opacity: 1;
  transform: translateY(0);
}
.mosaic-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.04em;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.mosaic-price {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  opacity: 0.85;
}

/* 空 cell 的 deco typography */
.cell-deco {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  padding: 20px;
}
.cell-deco-main { gap: 14px; position: relative; }
.deco-watermark {
  position: absolute;
  bottom: 8px;
  right: 16px;
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 96px;
  line-height: 1;
  color: var(--color-ink-strong);
  opacity: 0.06;
  pointer-events: none;
  user-select: none;
}
.cell-deco-tall { gap: 16px; padding: 28px; }

.deco-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
}
.deco-num {
  font-family: var(--font-display);
  font-weight: 300;
  font-size: 88px;
  line-height: 1;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.deco-rule {
  width: 32px;
  height: 1px;
  background: var(--color-accent);
}
.deco-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.deco-word-pair {
  display: inline-flex;
  align-items: baseline;
  font-family: var(--font-display);
  font-weight: 300;
  color: var(--color-ink-strong);
}
.deco-word {
  font-size: 64px;
  line-height: 1;
  letter-spacing: 0.02em;
}
.deco-word-soft {
  font-size: 22px;
  font-style: italic;
  color: var(--color-accent);
  margin-left: 4px;
}
.deco-caption {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
}
.deco-headline {
  font-family: var(--font-display);
  font-weight: 300;
  font-size: 26px;
  line-height: 1.4;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.deco-headline em {
  font-style: italic;
  color: var(--color-accent);
  font-size: 0.85em;
}
.deco-link {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 3px;
  transition: color 150ms, border-color 150ms;
}
.deco-link:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}


/* ── Products section (本系列全部商品) ── */
.products-section {
  padding-top: 32px;
  border-top: 1px solid var(--color-line-subtle);
}
.section-header {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 36px;
}
.section-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
  width: 100%;
  margin-bottom: 6px;
}
.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.section-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
}
.products-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 28px;
}

/* ── Other series section ── */
.others-section {
  padding-top: 32px;
  border-top: 1px solid var(--color-line-subtle);
}
.others-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 36px;
}
.others-footer {
  text-align: center;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
}
.others-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 4px;
  transition: color 150ms, border-color 150ms;
}
.others-link:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

@media (max-width: 1279px) {
  .hero-title { font-size: 48px; }
  .mosaic { height: 460px; }
  .deco-num { font-size: 72px; }
  .deco-word { font-size: 56px; }
  .products-grid,
  .others-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .hero-title { font-size: 40px; }
  .mosaic {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr 1fr;
    height: 600px;
  }
  .cell-0 { grid-column: 1; grid-row: 1 / span 2; }
  .cell-1 { grid-column: 2; grid-row: 1; }
  .cell-2 { grid-column: 2; grid-row: 2; }
  .cell-3 { grid-column: 1 / span 2; grid-row: 3; }
  .deco-num { font-size: 64px; }
  .products-grid,
  .others-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .hero { margin-bottom: 24px; }
  .hero-title { font-size: 32px; letter-spacing: 0.06em; }
  .hero-desc { font-size: 15px; }
  .mosaic {
    grid-template-columns: 1fr;
    grid-template-rows: repeat(4, 220px);
    height: auto;
    margin-bottom: 64px;
  }
  .cell-0,
  .cell-1,
  .cell-2,
  .cell-3 {
    grid-column: 1;
    grid-row: auto;
  }
  .deco-num { font-size: 56px; }
  .products-grid,
  .others-grid { grid-template-columns: 1fr; }
}
</style>
