<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, X } from 'lucide-vue-next'
import { useDebounceFn } from '@vueuse/core'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
  debounceMs?: number
}>(), {
  placeholder: '搜尋...',
  debounceMs: 300,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const local = ref(props.modelValue)

watch(() => props.modelValue, (v) => {
  if (v !== local.value) local.value = v
})

const debouncedEmit = useDebounceFn((v: string) => {
  emit('update:modelValue', v)
}, props.debounceMs)

function onInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  local.value = v
  debouncedEmit(v)
}

function clear() {
  local.value = ''
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="relative">
    <Search
      :size="14"
      :stroke-width="1.5"
      class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
    />
    <input
      type="text"
      :value="local"
      :placeholder="placeholder"
      class="block w-full h-9 pl-9 pr-9 rounded-[var(--radius-xs)] bg-paper-surface text-ink-strong placeholder:text-ink-muted border border-line-hairline transition-colors duration-[120ms] text-[14px] leading-[20px]"
      @input="onInput"
    />
    <button
      v-if="local"
      type="button"
      class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-ink-muted hover:text-ink-strong transition-colors"
      :aria-label="'清除搜尋'"
      @click="clear"
    >
      <X :size="14" :stroke-width="1.5" />
    </button>
  </div>
</template>
