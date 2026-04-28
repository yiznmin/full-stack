<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'

interface Option {
  value: string
  label: string
}

defineProps<{
  modelValue: string
  options: Option[]
  placeholder?: string
  disabled?: boolean
  invalid?: boolean
  id?: string
  name?: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="relative">
    <select
      :id="id"
      :name="name"
      :value="modelValue"
      :disabled="disabled"
      :aria-invalid="invalid"
      :class="[
        'block w-full h-9 pl-3 pr-9 appearance-none cursor-pointer',
        'rounded-[var(--radius-xs)]',
        'bg-paper-surface text-ink-strong',
        'border',
        invalid ? 'border-state-danger' : 'border-line-hairline',
        'transition-colors duration-[120ms]',
        'disabled:bg-paper-subtle disabled:text-ink-disabled disabled:cursor-not-allowed',
        'text-[14px] leading-[20px]',
      ]"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
    <ChevronDown
      :size="14"
      :stroke-width="1.5"
      class="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
    />
  </div>
</template>
