<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppSidebar from '@/shared/components/AppSidebar.vue'
import AppHeader from '@/shared/components/AppHeader.vue'

const sidebarOpen = ref(false)
const route = useRoute()

// Auto-close drawer when route changes (mobile UX)
watch(() => route.fullPath, () => {
  sidebarOpen.value = false
})
</script>

<template>
  <div class="min-h-screen">
    <AppSidebar :mobile-open="sidebarOpen" @close="sidebarOpen = false" />
    <AppHeader @toggle-sidebar="sidebarOpen = !sidebarOpen" />
    <main class="lg:ml-[240px] mt-16 p-5 lg:p-7">
      <RouterView />
    </main>
  </div>
</template>
