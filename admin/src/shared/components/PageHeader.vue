<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <header class="mb-7 pb-5 border-b border-line-hairline flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
    <div>
      <h1 class="font-display text-ink-strong text-[26px] leading-[34px] tracking-[-0.005em]">
        {{ title }}
      </h1>
      <p v-if="subtitle" class="mt-1 text-[13px] text-ink-muted">
        {{ subtitle }}
      </p>
    </div>
    <div class="flex items-center gap-2 shrink-0 flex-wrap">
      <slot name="actions" />
    </div>
  </header>
</template>
