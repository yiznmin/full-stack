<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, ArrowRight } from 'lucide-vue-next'
import type { OrderStatus, ProductionProgress, ProductionProgressStatus } from '../api'

const props = defineProps<{
  progress: ProductionProgress
  orderStatus: OrderStatus
  pending: boolean
}>()

const emit = defineEmits<{
  advance: [status: 'manufacturing' | 'packaging' | 'ready_to_ship']
}>()

// status flow: pending -> in_production (auto, 客製) -> manufacturing -> packaging -> ready_to_ship -> shipped (auto by E36)
const labels: Record<ProductionProgressStatus, string> = {
  pending: '等待開始',
  in_production: '製作中',
  manufacturing: '印製模板 / 備料',
  packaging: '打包中',
  ready_to_ship: '備貨完成',
  shipped: '已出貨',
}

// 下一步：當前 → 手動可推進的下一個 status；shipped 由 E36 自動推
const nextStatus = computed<'manufacturing' | 'packaging' | 'ready_to_ship' | null>(() => {
  switch (props.progress.status) {
    case 'pending':
    case 'in_production':
      return 'manufacturing'
    case 'manufacturing':
      return 'packaging'
    case 'packaging':
      return 'ready_to_ship'
    default:
      return null
  }
})

const nextLabel = computed(() => (nextStatus.value ? labels[nextStatus.value] : ''))

const canAdvance = computed(() => {
  if (!nextStatus.value) return false
  // 只在 paid 之後、shipped/completed 之前的狀態允許手動推
  return ['paid', 'processing'].includes(props.orderStatus)
})
</script>

<template>
  <div
    class="flex items-center justify-between flex-wrap gap-2 px-3 py-2 bg-paper-subtle rounded-[var(--radius-xs)]"
  >
    <div class="text-[12px]">
      <span class="text-ink-muted">生產進度：</span>
      <span class="text-ink-strong">{{ labels[progress.status] }}</span>
    </div>
    <button
      v-if="canAdvance"
      type="button"
      class="text-[12px] inline-flex items-center gap-1 text-accent hover:text-accent-hover transition-colors disabled:opacity-50"
      :disabled="pending"
      @click="nextStatus && emit('advance', nextStatus)"
    >
      <Loader2 v-if="pending" :size="12" :stroke-width="1.5" class="animate-spin" />
      <span>標記為「{{ nextLabel }}」</span>
      <ArrowRight :size="12" :stroke-width="1.5" />
    </button>
  </div>
</template>
