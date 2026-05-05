<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Layers, Palette, Tags } from 'lucide-vue-next'

const ENTRIES = [
  {
    icon: Layers,
    title: '依難易度',
    desc: '入門 / 初級 / 中級 / 進階。剛開始的話建議從入門起步。',
    to: '/products?sort=latest',
    label: 'By Difficulty',
  },
  {
    icon: Palette,
    title: '依主題',
    desc: '風景、萌寵、藝術畫⋯ 從喜歡的世界開始挑。',
    to: '/themes',
    label: 'By Theme',
  },
  {
    icon: Tags,
    title: '依標籤',
    desc: '療癒、送禮、節慶⋯ 用情境找對的商品。',
    to: '/products',
    label: 'By Tag',
  },
]
</script>

<template>
  <section class="section">
    <div class="section-header">
      <div>
        <div class="section-eyebrow">No. 04 — Browse</div>
        <h2 class="section-title">挑選方式</h2>
      </div>
    </div>
    <div class="grid">
      <RouterLink v-for="e in ENTRIES" :key="e.title" :to="e.to" class="entry">
        <component :is="e.icon" class="entry-icon" />
        <div class="entry-label">{{ e.label }}</div>
        <h3 class="entry-title">{{ e.title }}</h3>
        <p class="entry-desc">{{ e.desc }}</p>
        <span class="entry-arrow">→</span>
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

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.entry {
  display: block;
  text-decoration: none;
  color: inherit;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 40px 32px;
  position: relative;
  transition: all 200ms;
}
.entry:hover {
  border-color: var(--color-line);
  box-shadow: 0 4px 18px rgba(46, 40, 35, 0.06);
}

.entry-icon {
  width: 32px;
  height: 32px;
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
  margin-bottom: 24px;
}

.entry-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent-soft);
  margin-bottom: 8px;
}

.entry-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 12px;
}

.entry-desc {
  font-size: 13px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 16px;
}

.entry-arrow {
  font-family: var(--font-body);
  font-size: 16px;
  color: var(--color-accent);
  transition: transform 200ms;
}
.entry:hover .entry-arrow {
  transform: translateX(4px);
}

@media (max-width: 1023px) {
  .section { padding: 64px 32px; }
  .grid { grid-template-columns: 1fr; gap: 20px; }
  .section-title { font-size: 28px; }
  .entry { padding: 32px 24px; }
}
@media (max-width: 767px) {
  .section { padding: 48px 24px; }
}
</style>
