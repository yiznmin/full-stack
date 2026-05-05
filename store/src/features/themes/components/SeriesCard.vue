<script setup lang="ts">
import { RouterLink } from 'vue-router'

defineProps<{
  series: {
    id: string
    name: string
    description: string | null
    product_count: number
    is_featured?: boolean
  }
  /** 漸層 index（每張卡不同） */
  index?: number
}>()

const VISUAL_GRADIENTS = [
  'linear-gradient(135deg, #DBC8B0 0%, #A88161 55%, #6A4A34 110%)',
  'linear-gradient(135deg, #EDE4D3 0%, #9B3850 55%, #781D35 110%)',
  'linear-gradient(135deg, #F4ECDA 0%, #C4A37D 55%, #A88161 110%)',
  'linear-gradient(135deg, #E0D2B8 0%, #8E6044 55%, #6A4A34 110%)',
]
function gradientFor(idx: number) {
  return VISUAL_GRADIENTS[idx % VISUAL_GRADIENTS.length]
}
</script>

<template>
  <RouterLink :to="`/series/${series.id}`" class="card">
    <div class="card-visual" :style="{ background: gradientFor(index ?? 0) }">
      <div class="visual-overlay">
        <span class="visual-name">{{ series.name }}</span>
        <span v-if="series.is_featured" class="visual-featured">⭐ 精選</span>
      </div>
      <div class="visual-corner-mark"></div>
    </div>
    <div class="card-body">
      <p v-if="series.description" class="card-desc">{{ series.description }}</p>
      <p v-else class="card-desc card-desc-empty">— 暫無系列說明 —</p>
      <div class="card-foot">
        <span class="card-count">{{ series.product_count }} 件商品</span>
        <span class="card-arrow">→</span>
      </div>
    </div>
  </RouterLink>
</template>

<style scoped>
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
  gap: 8px;
  background: linear-gradient(
    to top,
    rgba(46, 40, 35, 0.4) 0%,
    rgba(46, 40, 35, 0.05) 50%,
    transparent 100%
  );
}

.visual-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  letter-spacing: 0.06em;
  color: var(--color-paper-canvas);
  line-height: 1.3;
  text-shadow: 0 2px 12px rgba(46, 40, 35, 0.25);
}

.visual-featured {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  background: rgba(46, 40, 35, 0.4);
  backdrop-filter: blur(4px);
  padding: 3px 8px;
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
  padding: 22px 24px 22px;
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
</style>
