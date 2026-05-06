<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Layers } from 'lucide-vue-next'
import { useThemeDetailQuery } from '@/features/browse/queries'
import { useProductsQuery } from '@/features/products/queries'
import SeriesCard from '../components/SeriesCard.vue'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

const route = useRoute()
const id = computed(() => String(route.params.id || ''))

const themeQuery = useThemeDetailQuery(id)
const theme = computed(() => themeQuery.data.value ?? null)

// 該主題精選商品（admin 勾選 is_featured）— 取 4 張在 hero 右側 2x2 顯示
const featuredQuery = useProductsQuery(
  computed(() => ({
    theme_id: id.value,
    featured: true,
    page: 1,
    page_size: 4,
  })),
)
const fallbackQuery = useProductsQuery(
  computed(() => ({
    theme_id: id.value,
    sort: 'latest' as const,
    page: 1,
    page_size: 4,
  })),
)

const heroProducts = computed(() => {
  const featured = featuredQuery.data.value?.items ?? []
  if (featured.length > 0) return featured.slice(0, 4)
  return (fallbackQuery.data.value?.items ?? []).slice(0, 4)
})

// 4 格 cell（不夠 4 個就 null）
const heroCells = computed(() => [
  heroProducts.value[0] ?? null,
  heroProducts.value[1] ?? null,
  heroProducts.value[2] ?? null,
  heroProducts.value[3] ?? null,
])

const hasMosaic = computed(() => heroProducts.value.length > 0)

// 主題色卡（找不到 image 時的單格 fallback 色）
const CELL_TONES = [
  'linear-gradient(135deg, rgba(221,229,210,0.9), rgba(151,166,135,0.6))',
  'linear-gradient(135deg, rgba(236,223,218,0.9), rgba(201,168,168,0.55))',
  'linear-gradient(135deg, rgba(236,227,210,0.9), rgba(184,160,132,0.55))',
  'linear-gradient(135deg, rgba(220,227,226,0.9), rgba(152,171,168,0.55))',
]
function toneFor(idx: number) {
  return CELL_TONES[idx % CELL_TONES.length]
}

// hero 背景圖：第一張精選商品圖；無則 theme cover；無則用 gradient
const heroImage = computed<string | null>(() => {
  const first = heroProducts.value[0]?.cover_image_url
  if (first && !hasMosaic.value) return first
  if (theme.value?.cover_image_url) return theme.value.cover_image_url
  return null
})

const totalProducts = computed(() =>
  theme.value?.series.reduce((sum, s) => sum + s.product_count, 0) ?? 0,
)
</script>

<template>
  <section v-if="themeQuery.isPending.value" class="page page-loading">
    <Loader2 :size="20" />
  </section>

  <section v-else-if="themeQuery.isError.value || !theme" class="page page-empty">
    <Layers class="empty-icon" />
    <h1 class="empty-title">找不到這個主題</h1>
    <p class="empty-hint">主題已下架或網址錯誤。</p>
    <RouterLink to="/themes" class="empty-cta">回主題列表</RouterLink>
  </section>

  <section v-else class="page">
    <nav class="breadcrumb">
      <RouterLink to="/themes">主題</RouterLink>
      <span>/</span>
      <span class="current">{{ theme.name }}</span>
    </nav>

    <!-- Cinematic hero — 左 text / 右 2x2 精選商品 -->
    <header
      class="hero hero-with-mosaic"
      :class="{ 'hero-with-image': heroImage }"
    >
      <div v-if="heroImage" class="hero-bg" :style="{ backgroundImage: `url(${heroImage})` }"></div>
      <div v-else class="hero-bg hero-bg-tone"></div>
      <div class="hero-veil"></div>

      <div class="hero-inner">
        <div class="hero-text-side">
          <div class="hero-top">
            <span class="hero-stamp">Theme · No. {{ String(theme.sort_order).padStart(2, '0') }}</span>
            <span class="hero-stamp-rule"></span>
            <span class="hero-stamp-cap">Yiimui Atelier</span>
          </div>

          <h1 class="hero-title">{{ theme.name }}</h1>

          <p v-if="theme.description" class="hero-desc">
            <em class="desc-quote">“</em>{{ theme.description }}<em class="desc-quote">”</em>
          </p>

          <div class="hero-bottom">
            <div class="hero-meta">
              <span class="meta-num">{{ theme.series.length }}</span>
              <span class="meta-label">Series</span>
              <span class="meta-divider"></span>
              <span class="meta-num">{{ totalProducts }}</span>
              <span class="meta-label">Products</span>
            </div>
            <RouterLink :to="`/products?theme_id=${theme.id}`" class="hero-cta">
              該主題全部商品 →
            </RouterLink>
          </div>
        </div>

        <!-- 右側 2x2 精選商品 -->
        <aside class="hero-mosaic" aria-label="精選商品">
          <span class="mosaic-cap" aria-hidden="true">— Featured —</span>
          <div class="mosaic-grid">
            <template v-for="(p, idx) in heroCells" :key="idx">
              <RouterLink
                v-if="p"
                :to="`/products/${p.id}`"
                class="mosaic-cell"
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
                <span class="mosaic-overlay">
                  <span class="mosaic-name">{{ p.title }}</span>
                  <span class="mosaic-price">NT$ {{ p.price_min.toLocaleString() }} 起</span>
                </span>
              </RouterLink>
              <div
                v-else
                class="mosaic-cell mosaic-empty"
                :style="{ background: toneFor(idx) }"
              >
                <span class="empty-mark">{{ theme.name.slice(0, 1) }}</span>
              </div>
            </template>
          </div>
        </aside>
      </div>
    </header>

    <!-- 該主題下的系列 -->
    <section class="series-section">
      <SectionMasthead
        no="01"
        chapter="Series"
        title="系列"
        :caption="`under ${theme.name}`"
      />

      <div v-if="theme.series.length === 0" class="empty-inner">
        <p>這個主題還沒有任何系列。</p>
      </div>

      <div v-else class="series-grid">
        <SeriesCard
          v-for="(s, idx) in theme.series"
          :key="s.id"
          :series="s"
          :index="idx"
        />
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
.empty-hint {
  font-size: 13px; color: var(--color-ink-muted); letter-spacing: 0.04em; margin: 0 0 24px;
}
.empty-cta {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

/* ── Cinematic Hero（單欄、滿版、層次飽滿） ── */
.hero {
  position: relative;
  margin-bottom: 80px;
  height: clamp(440px, 60vh, 620px);
  overflow: hidden;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: sepia(0.06) saturate(0.92);
}
.hero-bg-tone {
  background:
    radial-gradient(circle at 20% 25%, rgba(255,255,255,0.5), transparent 55%),
    radial-gradient(circle at 80% 75%, var(--color-accent-tint), transparent 60%),
    linear-gradient(135deg,
      var(--color-paper-deep) 0%,
      var(--color-accent-soft) 70%,
      var(--color-accent) 130%);
}

/* 紙質紋路 + 暗角 veil 讓字夠清楚 */
.hero-veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg,
      rgba(31, 26, 21, 0.42) 0%,
      rgba(31, 26, 21, 0.18) 50%,
      rgba(31, 26, 21, 0.45) 100%);
  pointer-events: none;
}
.hero-with-image .hero-veil {
  background:
    linear-gradient(135deg,
      rgba(31, 26, 21, 0.55) 0%,
      rgba(31, 26, 21, 0.32) 55%,
      rgba(31, 26, 21, 0.58) 100%);
}

.hero-inner {
  position: relative;
  z-index: 2;
  height: 100%;
  padding: 56px 64px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 48px;
  color: var(--color-paper-canvas);
}
.hero-with-mosaic .hero-inner {
  grid-template-columns: 1fr 0.75fr;
  align-items: stretch;
}

.hero-text-side {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 24px;
  min-width: 0;
}

/* Top — 戳印 */
.hero-top {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: rgba(250, 244, 221, 0.85);
}
.hero-stamp {
  font-weight: 500;
  color: rgba(250, 244, 221, 0.95);
}
.hero-stamp-rule {
  flex: 0 1 80px;
  height: 1px;
  background: rgba(250, 244, 221, 0.4);
}
.hero-stamp-cap {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: rgba(250, 244, 221, 0.75);
  text-transform: none;
}

/* 中段 — 大標 + 描述 */
.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: clamp(48px, 9vw, 96px);
  line-height: 1.1;
  letter-spacing: 0.12em;
  margin: 16px 0 0;
  color: rgba(250, 244, 221, 0.98);
  align-self: end;
  text-shadow: 0 4px 24px rgba(31, 26, 21, 0.35);
}
.hero-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  line-height: 1.95;
  letter-spacing: 0.06em;
  color: rgba(250, 244, 221, 0.85);
  max-width: 540px;
  margin: 0;
  align-self: start;
}
.desc-quote {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 26px;
  font-weight: 300;
  color: var(--color-accent-tint);
  margin: 0 4px;
  vertical-align: -4px;
}

/* 底部 — meta + CTA */
.hero-bottom {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.hero-meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: var(--font-mono);
  color: rgba(250, 244, 221, 0.9);
}
.meta-num {
  font-size: 26px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: rgba(250, 244, 221, 1);
}
.meta-label {
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: rgba(250, 244, 221, 0.6);
  margin-right: 6px;
}
.meta-divider {
  width: 1px;
  height: 18px;
  background: rgba(250, 244, 221, 0.4);
  margin: 0 8px;
}
.hero-cta {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  padding: 14px 28px;
  border: 1px solid rgba(250, 244, 221, 0.7);
  color: rgba(250, 244, 221, 0.95);
  text-decoration: none;
  transition: all 200ms;
}
.hero-cta:hover {
  background: rgba(250, 244, 221, 0.95);
  color: var(--color-ink-strong);
  border-color: rgba(250, 244, 221, 0.95);
}

/* ── Hero mosaic 2x2（右側精選商品） ── */
.hero-mosaic {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.mosaic-cap {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: rgba(250, 244, 221, 0.7);
  align-self: flex-end;
}
.mosaic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 10px;
  flex: 1;
  min-height: 0;
}
.mosaic-cell {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(250, 244, 221, 0.25);
  background: rgba(31, 26, 21, 0.15);
  text-decoration: none;
  color: inherit;
  transition: transform 400ms ease, border-color 200ms;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mosaic-cell:hover {
  border-color: rgba(250, 244, 221, 0.7);
  transform: translateY(-2px);
}
.mosaic-empty { cursor: default; }
.mosaic-empty:hover { transform: none; border-color: rgba(250, 244, 221, 0.25); }

.mosaic-img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  filter: sepia(0.06) saturate(0.92);
  transition: transform 600ms ease, filter 200ms;
}
.mosaic-cell:hover .mosaic-img {
  transform: scale(1.06);
  filter: sepia(0.04) saturate(0.98) brightness(1.04);
}
.mosaic-tone { width: 100%; height: 100%; }

.mosaic-overlay {
  position: absolute;
  inset: auto 0 0 0;
  padding: 10px 12px 11px;
  background: linear-gradient(to top, rgba(20, 16, 12, 0.78), rgba(20, 16, 12, 0));
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 240ms, transform 240ms;
}
.mosaic-cell:hover .mosaic-overlay {
  opacity: 1;
  transform: translateY(0);
}
.mosaic-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: rgba(250, 244, 221, 0.95);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.mosaic-price {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: rgba(250, 244, 221, 0.75);
}

.empty-mark {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 56px;
  line-height: 1;
  color: rgba(250, 244, 221, 0.45);
  user-select: none;
}

/* ── Series section ── */
.series-section {
  padding-top: 8px;
}

.empty-inner {
  padding: 48px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

.series-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

@media (max-width: 1279px) {
  .hero-with-mosaic .hero-inner { grid-template-columns: 1fr 0.7fr; gap: 36px; }
  .series-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .hero { height: auto; min-height: 480px; }
  .hero-inner { padding: 40px 36px; }
  .hero-with-mosaic .hero-inner {
    grid-template-columns: 1fr;
    gap: 32px;
  }
  .mosaic-grid { aspect-ratio: 2 / 1; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .hero {
    height: auto;
    min-height: 380px;
    border-radius: 0;
    margin-left: -24px;
    margin-right: -24px;
    border-left: none;
    border-right: none;
  }
  .hero-inner { padding: 32px 24px; gap: 24px; }
  .hero-title { letter-spacing: 0.06em; }
  .hero-bottom { flex-direction: column; align-items: flex-start; }
  .mosaic-grid { aspect-ratio: 1; }
  .series-grid { grid-template-columns: 1fr; }
}
</style>
