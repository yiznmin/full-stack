<script setup lang="ts">
defineProps<{
  modelValue?: string
  placeholder?: string
  rows?: number
  disabled?: boolean
  invalid?: boolean
  id?: string
  name?: string
  maxlength?: number
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <textarea
    :id="id"
    :name="name"
    :value="modelValue"
    :placeholder="placeholder"
    :rows="rows ?? 4"
    :disabled="disabled"
    :maxlength="maxlength"
    :aria-invalid="invalid"
    :class="[
      'block w-full px-3 py-2 resize-y',
      'rounded-[var(--radius-xs)]',
      'bg-paper-surface text-ink-strong placeholder:text-ink-muted',
      'border',
      invalid ? 'border-state-danger' : 'border-line-hairline',
      'transition-colors duration-[120ms]',
      'disabled:bg-paper-subtle disabled:text-ink-disabled disabled:cursor-not-allowed',
      'text-[14px] leading-[22px]',
    ]"
    @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
  />
</template>
