<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  type?: string
  placeholder?: string
  disabled?: boolean
  invalid?: boolean
  autocomplete?: string
  id?: string
  name?: string
}>(), {
  type: 'text',
  disabled: false,
  invalid: false,
})

defineEmits<{
  'update:modelValue': [value: string]
}>()

const classes = computed(() => [
  'block w-full h-9 px-3',
  'rounded-[var(--radius-xs)]',
  'bg-paper-surface text-ink-strong placeholder:text-ink-muted',
  'border',
  props.invalid ? 'border-state-danger' : 'border-line-hairline',
  'transition-colors duration-[120ms]',
  'disabled:bg-paper-subtle disabled:text-ink-disabled disabled:cursor-not-allowed',
  'text-[14px] leading-[20px]',
].join(' '))
</script>

<template>
  <input
    :id="id"
    :name="name"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :autocomplete="autocomplete"
    :aria-invalid="invalid"
    :class="classes"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
