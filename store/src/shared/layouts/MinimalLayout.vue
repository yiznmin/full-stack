<script setup lang="ts">
import { RouterView } from 'vue-router'
import SiteLogo from '@/shared/components/SiteLogo.vue'
</script>

<template>
  <div class="minimal-layout">
    <header class="minimal-header">
      <div class="minimal-header-inner">
        <SiteLogo size="sm" />
      </div>
    </header>

    <main class="minimal-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.minimal-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.minimal-header {
  border-bottom: 1px solid var(--color-line-subtle);
  background: rgba(242, 236, 224, 0.92);
  backdrop-filter: blur(12px);
}

.minimal-header-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 20px 56px;
  text-align: center;
}

.minimal-main {
  flex: 1;
}

@media (max-width: 767px) {
  .minimal-header-inner { padding: 16px 24px; }
}
</style>
