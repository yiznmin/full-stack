<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { ThemeListItem } from '@/features/browse/api'

defineProps<{
  theme: ThemeListItem
}>()
</script>

<template>
  <RouterLink :to="`/themes/${theme.id}`" class="theme-card">
    <div class="img-wrap">
      <img
        v-if="theme.cover_image_url"
        :src="theme.cover_image_url"
        :alt="theme.name"
        loading="lazy"
      />
      <div v-else class="placeholder" />
      <div class="overlay">
        <div class="name">{{ theme.name }}</div>
        <div class="meta">{{ theme.series_count }} 系列 · {{ theme.product_count }} 件商品</div>
      </div>
    </div>
  </RouterLink>
</template>

<style scoped>
.theme-card {
  display: block;
  text-decoration: none;
  color: inherit;
  position: relative;
  aspect-ratio: 1.3 / 1;
  overflow: hidden;
  border-radius: var(--radius-xs);
  border: 1px solid var(--color-line-subtle);
}

.img-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--color-paper-deep);
}

.img-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: sepia(0.06) saturate(0.85);
  transition: transform 800ms ease;
}
.theme-card:hover img {
  transform: scale(1.03);
}

.placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, var(--color-paper-deep), var(--color-accent-soft));
  opacity: 0.6;
}

.overlay {
  position: absolute;
  inset: 0;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: linear-gradient(
    to top,
    rgba(46, 40, 35, 0.55) 0%,
    rgba(46, 40, 35, 0.05) 60%,
    transparent 100%
  );
}

.name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-paper-canvas);
  margin-bottom: 4px;
}

.meta {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(245, 241, 232, 0.85);
}
</style>
