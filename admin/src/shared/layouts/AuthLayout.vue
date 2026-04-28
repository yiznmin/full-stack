<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppLogo from '@/shared/components/AppLogo.vue'
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-5 py-12">
    <div class="w-full max-w-[400px]">
      <div class="flex justify-center mb-7">
        <AppLogo size="md" />
      </div>
      <RouterView />
      <p class="text-center text-[12px] text-ink-muted mt-8 tracking-[0.04em]">
        易木工房 · Admin
      </p>
    </div>
  </div>
</template>
