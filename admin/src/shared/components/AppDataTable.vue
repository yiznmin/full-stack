<script setup lang="ts" generic="T extends Record<string, unknown>">
import { Loader2 } from 'lucide-vue-next'

export interface Column<R> {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  width?: string  // CSS width like '120px' or '20%'
  cell?: (row: R) => string | number  // simple text accessor
}

defineProps<{
  columns: Column<T>[]
  rows: T[]
  loading?: boolean
  rowKey: (row: T) => string
  emptyText?: string
  emptyIcon?: unknown  // lucide icon component
  rowClickable?: boolean
}>()

defineEmits<{
  rowClick: [row: T]
}>()
</script>

<template>
  <div class="bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)] overflow-hidden">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-16 text-ink-muted">
      <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
      <span class="ml-2 text-[13px]">載入中...</span>
    </div>

    <!-- Empty -->
    <div
      v-else-if="rows.length === 0"
      class="flex flex-col items-center justify-center py-20 text-center"
    >
      <component
        :is="emptyIcon"
        v-if="emptyIcon"
        :size="32"
        :stroke-width="1.25"
        class="text-aux-rice-mid mb-3"
      />
      <p class="text-[13px] text-ink-muted">{{ emptyText || '尚無資料' }}</p>
      <slot name="empty-action" />
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left">
        <thead>
          <tr class="bg-paper-subtle border-b border-line-hairline">
            <th
              v-for="col in columns"
              :key="col.key"
              :style="col.width ? { width: col.width } : {}"
              :class="[
                'h-10 px-4 text-[13px] font-semibold text-ink-strong',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
              ]"
            >
              {{ col.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="rowKey(row)"
            :class="[
              'border-b border-line-hairline last:border-0 transition-colors',
              rowClickable ? 'cursor-pointer hover:bg-paper-subtle' : '',
            ]"
            @click="rowClickable && $emit('rowClick', row)"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="[
                'h-10 px-4 text-[13px] text-ink-default align-middle',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
              ]"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="col.cell?.(row)">
                {{ col.cell?.(row) ?? '' }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
