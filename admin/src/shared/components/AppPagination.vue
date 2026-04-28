<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps<{
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const start = computed(() => (props.page - 1) * props.pageSize + 1)
const end = computed(() => Math.min(props.page * props.pageSize, props.total))

function go(p: number) {
  if (p < 1 || p > totalPages.value || p === props.page) return
  emit('update:page', p)
}
</script>

<template>
  <div class="flex items-center justify-between mt-5">
    <p class="text-[12px] text-ink-muted tracking-[0.04em]">
      <span v-if="total > 0">第 {{ start }} – {{ end }} 筆，共 {{ total }} 筆</span>
      <span v-else>—</span>
    </p>
    <div class="flex items-center gap-1">
      <button
        type="button"
        class="h-8 w-8 flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-paper-subtle hover:text-ink-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        :disabled="page <= 1"
        aria-label="上一頁"
        @click="go(page - 1)"
      >
        <ChevronLeft :size="14" :stroke-width="1.5" />
      </button>
      <span class="px-3 text-[13px] text-ink-default font-mono">
        {{ page }} / {{ totalPages }}
      </span>
      <button
        type="button"
        class="h-8 w-8 flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-paper-subtle hover:text-ink-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        :disabled="page >= totalPages"
        aria-label="下一頁"
        @click="go(page + 1)"
      >
        <ChevronRight :size="14" :stroke-width="1.5" />
      </button>
    </div>
  </div>
</template>
