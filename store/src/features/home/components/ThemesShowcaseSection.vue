<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useThemesQuery } from '@/features/browse/queries'
import type { ThemeListItem } from '@/features/browse/api'

const themesQuery = useThemesQuery()
const themes = computed<ThemeListItem[]>(
  () => themesQuery.data.value?.items.slice(0, 4) ?? [],
)

// 4 種 mood 漸層 — 跟 ThemeCard / SeriesDetail mosaic 對齊
const TONES = [
  'linear-gradient(135deg, rgba(221,229,210,0.6), rgba(151,166,135,0.4))',
  'linear-gradient(135deg, rgba(236,223,218,0.6), rgba(201,168,168,0.4))',
  'linear-gradient(135deg, rgba(236,227,210,0.6), rgba(184,160,132,0.4))',
  'linear-gradient(135deg, rgba(220,227,226,0.6), rgba(152,171,168,0.4))',
]
function toneFor(idx: number) {
  return TONES[idx % TONES.length]
}
</script>

<template>
  <section v-if="themes.length > 0" class="band">
    <div class="band-grain" aria-hidden="true"></div>

    <div class="inner">
      <div class="head">
        <div class="head-rule">
          <span class="head-no">No. 03</span>
          <span class="head-dot"></span>
          <span class="head-cap">Themes</span>
          <span class="head-line"></span>
        </div>
        <h2 class="title">
          依<em class="em">主題</em>挑選
          <span class="title-aux">— browse by mood —</span>
        </h2>
      </div>

      <div class="grid">
        <RouterLink
          v-for="(t, idx) in themes"
          :key="t.id"
          :to="`/themes/${t.id}`"
          class="card"
        >
          <img
            v-if="t.cover_image_url"
            :src="t.cover_image_url"
            :alt="t.name"
            class="card-img"
            loading="lazy"
          />
          <div
            v-else
            class="card-tone"
            :style="{ background: toneFor(idx) }"
          ></div>
          <div class="card-veil"></div>
          <div class="card-body">
            <div class="card-no">{{ String(idx + 1).padStart(2, '0') }}</div>
            <h3 class="card-name">{{ t.name }}</h3>
            <div class="card-meta">{{ t.series_count }} 系列 · {{ t.product_count }} 件</div>
          </div>
        </RouterLink>
      </div>

      <div class="foot">
        <RouterLink to="/themes" class="more">
          看全部主題 →
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.band {
  position: relative;
  background: var(--color-paper-deep);
  padding: 120px 0 128px;
  overflow: hidden;
  margin: 96px 0;
}

/* 紙質 grain（淡底上的微紋路） */
.band-grain {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.25;
  mix-blend-mode: multiply;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.4 0 0 0 0 0.32 0 0 0 0 0.22 0 0 0 0.05 0'/></filter><rect width='100%25' height='100%25' filter='url(%23g)'/></svg>");
}

.inner {
  position: relative;
  z-index: 2;
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 56px;
}

.head { margin-bottom: 56px; }
.head-rule {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}
.head-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.head-dot {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--color-accent);
}
.head-cap {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
}
.head-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, var(--color-accent-soft), transparent 80%);
}

.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: clamp(48px, 6vw, 80px);
  line-height: 1.1;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0;
}
.em {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  margin: 0 0.04em;
}
.title-aux {
  display: block;
  margin-top: 16px;
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.card {
  position: relative;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  text-decoration: none;
  color: inherit;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-surface);
  transition: transform 400ms ease, border-color 200ms;
}
.card:hover {
  transform: translateY(-4px);
  border-color: var(--color-line);
}

.card-img,
.card-tone {
  position: absolute;
  inset: 0;
  width: 100%; height: 100%;
}
.card-img {
  object-fit: cover;
  filter: sepia(0.06) saturate(0.9) brightness(0.9);
  transition: transform 700ms ease, filter 200ms;
}
.card:hover .card-img {
  transform: scale(1.05);
  filter: sepia(0.04) saturate(1) brightness(0.95);
}
.card-veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to top,
    rgba(20, 16, 12, 0.78) 0%,
    rgba(20, 16, 12, 0.12) 55%,
    rgba(20, 16, 12, 0) 100%
  );
}

.card-body {
  position: absolute;
  inset: auto 0 0 0;
  padding: 24px 24px 28px;
  z-index: 2;
}
.card-no {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  color: var(--color-fresh-soft);
  margin-bottom: 6px;
  font-weight: 500;
}
.card-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 26px;
  letter-spacing: 0.08em;
  color: var(--color-paper-canvas);
  margin: 0 0 6px;
  line-height: 1.2;
}
.card-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(236, 227, 210, 0.7);
}

.foot {
  margin-top: 56px;
  padding-top: 24px;
  border-top: 1px solid var(--color-accent-soft);
  text-align: right;
}
.more {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 4px;
}
.more:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }

@media (max-width: 1279px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .band { padding: 80px 0 88px; margin: 64px 0; }
  .inner { padding: 0 24px; }
  .grid { grid-template-columns: 1fr; gap: 14px; }
  .title { font-size: 38px; }
  .title-aux { font-size: 14px; }
  .card { aspect-ratio: 4 / 3; }
}
</style>
