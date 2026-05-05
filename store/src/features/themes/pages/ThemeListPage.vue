<script setup lang="ts">
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { useThemesQuery } from '@/features/browse/queries'
import ThemeCard from '../components/ThemeCard.vue'

const themesQuery = useThemesQuery()
const themes = computed(() => themesQuery.data.value?.items ?? [])
</script>

<template>
  <section class="page">
    <header class="page-header">
      <div class="page-eyebrow">Themes</div>
      <h1 class="page-title">主題瀏覽</h1>
      <p class="page-desc">
        從喜歡的世界開始挑 — 風景、萌寵、藝術畫、人物，<br>
        每個主題下有自己的系列與商品。
      </p>
    </header>

    <div v-if="themesQuery.isPending.value" class="loading">
      <Loader2 :size="20" />
    </div>

    <div v-else-if="themes.length === 0" class="empty">
      <p class="empty-title">主題建設中</p>
      <p class="empty-hint">後台還沒建立任何主題。</p>
    </div>

    <div v-else class="grid">
      <ThemeCard v-for="t in themes" :key="t.id" :theme="t" />
    </div>
  </section>
</template>

<style scoped>
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.page-header {
  margin-bottom: 64px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--color-line);
  text-align: center;
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 16px;
}

.page-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 44px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 24px;
}

.page-desc {
  font-size: 14px;
  line-height: 2;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  max-width: 480px;
  margin: 0 auto;
}

.loading {
  padding: 96px 0;
  display: flex;
  justify-content: center;
  color: var(--color-ink-muted);
}
.loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5; fill: none; stroke: currentColor;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  padding: 96px 24px;
  text-align: center;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0;
  letter-spacing: 0.04em;
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

@media (max-width: 1279px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 48px 32px 64px; }
  .page-title { font-size: 36px; }
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .page-title { font-size: 28px; }
  .grid { grid-template-columns: 1fr; }
}
</style>
