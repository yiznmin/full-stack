<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'
import type { SortMode } from '../api'

defineProps<{ modelValue: SortMode }>()
defineEmits<{ 'update:modelValue': [value: SortMode] }>()

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: 'latest', label: '最新上架' },
  { value: 'popular', label: '熱門商品' },
  { value: 'price_asc', label: '價格由低到高' },
  { value: 'price_desc', label: '價格由高到低' },
]
</script>

<template>
  <label class="sort" for="product-sort">
    <span class="sort-label">排序</span>
    <span class="sort-control">
      <select
        id="product-sort"
        name="sort"
        :value="modelValue"
        @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value as SortMode)"
      >
        <option v-for="o in SORT_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <ChevronDown class="sort-icon" />
    </span>
  </label>
</template>

<style scoped>
.sort {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.sort-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.sort-control {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.sort-control select {
  appearance: none;
  -webkit-appearance: none;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  background: transparent;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 8px 36px 8px 14px;
  cursor: pointer;
  transition: border-color 150ms;
}

.sort-control select:hover {
  border-color: var(--color-accent);
}

.sort-control select:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.sort-icon {
  position: absolute;
  right: 12px;
  width: 14px;
  height: 14px;
  stroke: var(--color-ink-muted);
  stroke-width: 1.5;
  fill: none;
  pointer-events: none;
}
</style>
