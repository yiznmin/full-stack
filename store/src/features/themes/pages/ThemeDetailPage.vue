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

// 該主題的精選商品（admin 勾選 is_featured）— 取 1 張當 hero 大圖
const featuredQuery = useProductsQuery(
  computed(() => ({
    theme_id: id.value,
    featured: true,
    page: 1,
    page_size: 1,
  })),
)
const fallbackQuery = useProductsQuery(
  computed(() => ({
    theme_id: id.value,
    sort: 'latest' as const,
    page: 1,
    page_size: 1,
  })),
)

const heroImage = computed<string | null>(() => {
  const featured = featuredQuery.data.value?.items?.[0]?.cover_image_url
  if (featured) return featured
  const fallback = fallbackQuery.data.value?.items?.[0]?.cover_image_url
  if (fallback) return fallback
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

    <!-- Cinematic hero — 大圖背景上疊雜誌封面式排版 -->
    <header class="hero" :class="{ 'hero-with-image': heroImage }">
      <div v-if="heroImage" class="hero-bg" :style="{ backgroundImage: `url(${heroImage})` }"></div>
      <div v-else class="hero-bg hero-bg-tone"></div>
      <div class="hero-veil"></div>

      <div class="hero-inner">
        <div class="hero-top">
          <span class="hero-stamp">Theme · No. {{ String(theme.sort_order).padStart(2, '0') }}</span>
          <span class="hero-stamp-rule"></span>
          <span class="hero-stamp-cap">Yiimui Atelier</span>
        </div>

        <h1 class="hero-title">
          {{ theme.name }}
        </h1>

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
  grid-template-rows: auto 1fr auto;
  gap: 24px;
  color: var(--color-paper-canvas);
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
  .series-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .hero { height: clamp(380px, 56vh, 540px); }
  .hero-inner { padding: 40px 36px; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .hero { height: auto; min-height: 380px; border-radius: 0; margin-left: -24px; margin-right: -24px; border-left: none; border-right: none; }
  .hero-inner { padding: 32px 24px; gap: 20px; }
  .hero-title { letter-spacing: 0.06em; }
  .hero-bottom { flex-direction: column; align-items: flex-start; }
  .series-grid { grid-template-columns: 1fr; }
}
</style>
