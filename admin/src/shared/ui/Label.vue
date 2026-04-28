<script setup lang="ts">
defineProps<{
  for?: string
}>()
</script>

<template>
  <label
    :for="$props.for"
    class="block text-[12px] leading-[18px] font-medium uppercase tracking-[0.06em] text-ink-muted mb-1.5"
  >
    <slot />
  </label>
</template>
