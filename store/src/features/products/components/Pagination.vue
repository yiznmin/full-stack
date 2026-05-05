<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps<{
  page: number
  total: number
  pageSize: number
}>()

const emit = defineEmits<{ change: [page: number] }>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const visiblePages = computed(() => {
  // 顯示 1, 2, ..., 當前-1, 當前, 當前+1, ..., 倒數第 2, 倒數第 1（用 ...）
  const tp = totalPages.value
  const cur = props.page
  const set = new Set<number>([1, tp, cur - 1, cur, cur + 1])
  const arr = [...set].filter((p) => p >= 1 && p <= tp).sort((a, b) => a - b)
  // 插 ... 標記
  const out: (number | 'ellipsis')[] = []
  for (let i = 0; i < arr.length; i++) {
    if (i > 0 && arr[i] - arr[i - 1] > 1) out.push('ellipsis')
    out.push(arr[i])
  }
  return out
})

function go(p: number) {
  if (p < 1 || p > totalPages.value || p === props.page) return
  emit('change', p)
}
</script>

<template>
  <nav v-if="totalPages > 1" class="pagination" aria-label="商品分頁">
    <button
      class="page-btn"
      :disabled="page <= 1"
      aria-label="上一頁"
      @click="go(page - 1)"
    >
      <ChevronLeft />
    </button>

    <template v-for="(p, idx) in visiblePages" :key="`p-${idx}-${p}`">
      <span v-if="p === 'ellipsis'" class="ellipsis">⋯</span>
      <button
        v-else
        class="page-btn"
        :class="{ 'page-btn-active': p === page }"
        @click="go(p)"
      >
        {{ p }}
      </button>
    </template>

    <button
      class="page-btn"
      :disabled="page >= totalPages"
      aria-label="下一頁"
      @click="go(page + 1)"
    >
      <ChevronRight />
    </button>
  </nav>
</template>

<style scoped>
.pagination {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.page-btn {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-default);
  cursor: pointer;
  transition: all 150ms;
}

.page-btn:hover:not(:disabled) {
  background: var(--color-paper-deep);
  border-color: var(--color-line-subtle);
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-btn-active {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border-color: var(--color-ink-strong);
  cursor: default;
}
.page-btn-active:hover {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
}

.page-btn :deep(svg) {
  width: 14px;
  height: 14px;
  stroke: currentColor;
  stroke-width: 1.5;
  fill: none;
}

.ellipsis {
  width: 24px;
  text-align: center;
  font-family: var(--font-mono);
  color: var(--color-ink-muted);
}
</style>
