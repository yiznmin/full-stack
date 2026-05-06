<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useFeaturedSeriesQuery } from '@/features/browse/queries'

const featuredQuery = useFeaturedSeriesQuery()
const series = computed(() => featuredQuery.data.value?.items ?? [])

// 4 種漸層，基於 index 循環使用，避免每張卡看起來都一樣
// 4 種極淡漸層 — 紙本灰白為主、僅末端微微 taupe 點綴；極簡留白為核心
const VISUAL_GRADIENTS = [
  'linear-gradient(135deg, #FBF8F1 0%, #EFE9DA 80%, #DDD0BB 140%)',
  'linear-gradient(135deg, #F6F2EA 0%, #E8DFCD 70%, #C8B79C 150%)',
  'linear-gradient(135deg, #FBF8F1 0%, #EBE2D0 70%, #D6C5AB 150%)',
  'linear-gradient(135deg, #F6F2EA 0%, #E5DBC4 70%, #C0AE92 160%)',
]

function gradientFor(index: number) {
  return VISUAL_GRADIENTS[index % VISUAL_GRADIENTS.length]
}
</script>

<template>
  <section v-if="series.length > 0" class="section">
    <div class="section-header">
      <div>
        <div class="section-eyebrow">No. 03 — Featured Series</div>
        <h2 class="section-title">精選系列</h2>
      </div>
      <RouterLink to="/products" class="section-link">所有商品 →</RouterLink>
    </div>

    <div class="grid">
      <RouterLink
        v-for="(s, idx) in series"
        :key="s.id"
        :to="`/series/${s.id}`"
        class="card"
      >
        <div class="card-visual" :style="{ background: gradientFor(idx) }">
          <div class="visual-overlay">
            <span class="visual-num">No. {{ String(idx + 1).padStart(2, '0') }}</span>
            <span class="visual-name">{{ s.name }}</span>
            <span v-if="s.theme_name" class="visual-theme">{{ s.theme_name }}</span>
          </div>
          <div class="visual-corner-mark"></div>
        </div>
        <div class="card-body">
          <p v-if="s.description" class="card-desc">{{ s.description }}</p>
          <p v-else class="card-desc card-desc-empty">— 一個還在悄悄誕生的系列 —</p>
          <div class="card-foot">
            <span class="card-count">{{ s.product_count }} 件商品</span>
            <span class="card-arrow">→</span>
          </div>
        </div>
      </RouterLink>
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
}
.section-link:hover { color: var(--color-accent-deep); }

.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.card {
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  overflow: hidden;
  transition: all 220ms ease;
}
.card:hover {
  border-color: var(--color-accent);
  box-shadow: 0 6px 24px rgba(46, 40, 35, 0.08);
  transform: translateY(-2px);
}

.card-visual {
  position: relative;
  aspect-ratio: 5 / 4;
  overflow: hidden;
  background-size: 200% 200%;
  background-position: 30% 30%;
  transition: background-position 600ms ease;
}
.card:hover .card-visual {
  background-position: 70% 70%;
}

.visual-overlay {
  position: absolute;
  inset: 0;
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: flex-start;
  background: linear-gradient(
    to top,
    rgba(46, 40, 35, 0.4) 0%,
    rgba(46, 40, 35, 0.05) 50%,
    transparent 100%
  );
}

.visual-num {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: rgba(245, 241, 232, 0.8);
  margin-bottom: 12px;
}

.visual-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.06em;
  color: var(--color-paper-canvas);
  line-height: 1.3;
  text-shadow: 0 2px 12px rgba(46, 40, 35, 0.25);
  margin-bottom: 8px;
}

.visual-theme {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(245, 241, 232, 0.85);
  padding: 4px 10px;
  background: rgba(46, 40, 35, 0.4);
  backdrop-filter: blur(4px);
  border-radius: var(--radius-xs);
}

.visual-corner-mark {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 28px;
  height: 28px;
  border-top: 1px solid rgba(245, 241, 232, 0.6);
  border-right: 1px solid rgba(245, 241, 232, 0.6);
}

.card-body {
  padding: 24px 24px 22px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.card-desc {
  font-size: 13px;
  line-height: 1.85;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}
.card-desc-empty {
  color: var(--color-ink-muted);
  font-style: italic;
}

.card-foot {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--color-line-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
}

.card-arrow {
  font-family: var(--font-body);
  font-size: 16px;
  color: var(--color-accent);
  transition: transform 220ms ease;
}
.card:hover .card-arrow {
  transform: translateX(6px);
}

@media (max-width: 1279px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1023px) {
  .section { padding: 64px 32px; }
  .grid { grid-template-columns: repeat(2, 1fr); gap: 20px; }
  .section-title { font-size: 28px; }
  .visual-name { font-size: 24px; }
}
@media (max-width: 767px) {
  .section { padding: 48px 24px; }
  .grid { grid-template-columns: 1fr; }
  .visual-name { font-size: 26px; }
}
</style>
