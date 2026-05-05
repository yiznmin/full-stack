<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useThemesQuery } from '@/features/browse/queries'
import ThemeCard from '@/features/themes/components/ThemeCard.vue'

const themesQuery = useThemesQuery()
const themes = computed(() => themesQuery.data.value?.items.slice(0, 4) ?? [])
</script>

<template>
  <section v-if="themes.length > 0" class="section">
    <div class="section-header">
      <div>
        <div class="section-eyebrow">No. 02 — Themes</div>
        <h2 class="section-title">主題瀏覽</h2>
      </div>
      <RouterLink to="/themes" class="section-link">所有主題 →</RouterLink>
    </div>
    <div class="grid">
      <ThemeCard v-for="t in themes" :key="t.id" :theme="t" />
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

@media (max-width: 1023px) {
  .section { padding: 64px 32px; }
  .grid { grid-template-columns: repeat(2, 1fr); }
  .section-title { font-size: 28px; }
}
@media (max-width: 767px) {
  .section { padding: 48px 24px; }
  .grid { grid-template-columns: 1fr; }
}
</style>
