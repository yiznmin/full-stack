<script setup lang="ts">
withDefaults(defineProps<{
  size?: 'sm' | 'md' | 'lg'
}>(), {
  size: 'md',
})

const sizes = {
  sm: 'text-[18px] leading-none',
  md: 'text-[28px] leading-none',
  lg: 'text-[36px] leading-none',
}
</script>

<template>
  <div class="font-display text-ink-strong tracking-[-0.005em]" :class="sizes[size]">
    易木
    <span class="ml-1.5 text-ink-muted text-[0.5em] tracking-[0.16em] uppercase font-body font-medium align-middle">
      Yiimui
    </span>
  </div>
</template>
