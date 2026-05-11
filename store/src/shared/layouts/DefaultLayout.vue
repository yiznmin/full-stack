<script setup lang="ts">
import { RouterView } from 'vue-router'
import SiteHeader from '@/shared/components/SiteHeader.vue'
import SiteFooter from '@/shared/components/SiteFooter.vue'
import ContactBubble from '@/shared/components/ContactBubble.vue'
</script>

<template>
  <div class="layout">
    <SiteHeader />
    <main class="layout-main">
      <RouterView />
    </main>
    <SiteFooter />
    <ContactBubble />
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout-main {
  flex: 1;
}
</style>
