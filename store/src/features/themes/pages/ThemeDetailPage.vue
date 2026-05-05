<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Layers } from 'lucide-vue-next'
import { useThemeDetailQuery } from '@/features/browse/queries'
import SeriesCard from '../components/SeriesCard.vue'

const route = useRoute()
const id = computed(() => String(route.params.id || ''))

const themeQuery = useThemeDetailQuery(id)
const theme = computed(() => themeQuery.data.value ?? null)
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
    <!-- Hero -->
    <header class="hero">
      <nav class="breadcrumb">
        <RouterLink to="/themes">主題</RouterLink>
        <span>/</span>
        <span class="current">{{ theme.name }}</span>
      </nav>

      <div class="hero-grid">
        <div class="hero-text">
          <div class="hero-eyebrow">Theme</div>
          <h1 class="hero-title">{{ theme.name }}</h1>
          <p v-if="theme.description" class="hero-desc">{{ theme.description }}</p>
          <div class="hero-meta">
            <span class="hero-meta-item">
              {{ theme.series.length }} 個系列
            </span>
            <span class="hero-meta-divider">·</span>
            <span class="hero-meta-item">
              {{ theme.series.reduce((sum, s) => sum + s.product_count, 0) }} 件商品
            </span>
          </div>
          <RouterLink :to="`/products?theme_id=${theme.id}`" class="hero-cta">
            該主題全部商品 →
          </RouterLink>
        </div>

        <div class="hero-visual">
          <img
            v-if="theme.cover_image_url"
            :src="theme.cover_image_url"
            :alt="theme.name"
          />
          <div v-else class="hero-visual-fallback">
            <span class="fallback-name">{{ theme.name }}</span>
          </div>
        </div>
      </div>
    </header>

    <!-- 該主題下的系列 -->
    <section class="series-section">
      <div class="series-header">
        <div>
          <div class="series-eyebrow">Series</div>
          <h2 class="series-title">系列</h2>
        </div>
      </div>

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

.hero {
  margin-bottom: 80px;
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
  margin-bottom: 32px;
  flex-wrap: wrap;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

.hero-grid {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 64px;
  align-items: center;
}

.hero-text {
  display: flex;
  flex-direction: column;
}

.hero-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-bottom: 24px;
}

.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 56px;
  line-height: 1.3;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 28px;
}

.hero-desc {
  font-size: 15px;
  line-height: 1.95;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 32px;
  max-width: 480px;
  white-space: pre-wrap;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 36px;
}
.hero-meta-divider {
  opacity: 0.4;
}

.hero-cta {
  display: inline-block;
  align-self: flex-start;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  padding: 16px 32px;
  border: 1px solid var(--color-ink-strong);
  color: var(--color-ink-strong);
  text-decoration: none;
  transition: all 200ms;
}
.hero-cta:hover {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}

.hero-visual {
  aspect-ratio: 4 / 5;
  overflow: hidden;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
}
.hero-visual img {
  width: 100%; height: 100%;
  object-fit: cover;
  filter: sepia(0.05) saturate(0.95);
}
.hero-visual-fallback {
  width: 100%; height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-paper-deep) 0%, var(--color-accent) 55%, var(--color-accent-deep) 110%);
}
.fallback-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 48px;
  letter-spacing: 0.12em;
  color: var(--color-paper-canvas);
  text-shadow: 0 4px 16px rgba(46, 40, 35, 0.25);
}

.series-section {
  padding-top: 32px;
  border-top: 1px solid var(--color-line);
}

.series-header {
  margin-bottom: 40px;
}

.series-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}

.series-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0;
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
  .hero-title { font-size: 44px; }
  .series-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .hero-grid { grid-template-columns: 1fr; gap: 32px; }
  .hero-title { font-size: 36px; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .hero-title { font-size: 28px; }
  .series-grid { grid-template-columns: 1fr; }
}
</style>
