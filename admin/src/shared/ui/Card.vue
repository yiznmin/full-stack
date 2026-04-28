<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  padded?: boolean
}>(), {
  padded: true,
})

const classes = computed(() => {
  const base = 'bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)]'
  return props.padded ? `${base} p-7` : base
})
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
