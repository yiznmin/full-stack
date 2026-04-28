<script setup lang="ts">
import { computed } from 'vue'

type Variant = 'primary' | 'secondary' | 'tertiary' | 'danger'

const props = withDefaults(defineProps<{
  variant?: Variant
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  block?: boolean
}>(), {
  variant: 'primary',
  type: 'button',
  disabled: false,
  block: false,
})

const classes = computed(() => {
  const base = [
    'inline-flex items-center justify-center gap-2',
    'h-9 px-4 rounded-[var(--radius-sm)]',
    'text-[14px] font-medium leading-none',
    'transition-colors duration-[120ms]',
    'disabled:cursor-not-allowed disabled:opacity-60',
  ]

  const variants: Record<Variant, string[]> = {
    primary: [
      'bg-accent text-paper-surface',
      'hover:bg-accent-hover',
      'disabled:bg-ink-disabled',
    ],
    secondary: [
      'bg-paper-surface text-ink-default border border-line-strong',
      'hover:bg-paper-subtle',
    ],
    tertiary: [
      'bg-transparent text-accent underline underline-offset-4',
      'hover:text-accent-hover',
    ],
    danger: [
      'bg-state-danger text-paper-surface',
      'hover:brightness-90',
    ],
  }

  return [
    ...base,
    ...variants[props.variant],
    props.block ? 'w-full' : '',
  ].join(' ')
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="classes"
  >
    <slot />
  </button>
</template>
