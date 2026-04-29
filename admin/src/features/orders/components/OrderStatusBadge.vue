<script setup lang="ts">
import type { OrderStatus } from '../api'

defineProps<{ status: OrderStatus }>()

const labels: Record<OrderStatus, { label: string; cls: string }> = {
  pending_payment: { label: '等待付款', cls: 'bg-[var(--color-state-warning)]/[0.12] text-state-warning' },
  payment_expired: { label: '逾期未付', cls: 'bg-paper-subtle text-ink-muted' },
  paid: { label: '已付款', cls: 'bg-[var(--color-state-success)]/[0.12] text-state-success' },
  processing: { label: '備貨中', cls: 'bg-[var(--color-state-info)]/[0.12] text-state-info' },
  shipped: { label: '已出貨', cls: 'bg-[var(--color-state-info)]/[0.18] text-state-info' },
  completed: { label: '已完成', cls: 'bg-[var(--color-accent)]/[0.10] text-accent' },
  cancelled: { label: '已取消', cls: 'bg-paper-subtle text-ink-muted' },
  refund_processing: { label: '退款處理中', cls: 'bg-[var(--color-state-warning)]/[0.18] text-state-warning' },
  refunded: { label: '已退款', cls: 'bg-aux-rice-mid/40 text-ink-default' },
  partially_refunded: { label: '部分退款', cls: 'bg-aux-rice-mid/30 text-ink-default' },
}
</script>

<template>
  <span
    class="inline-flex items-center px-2 h-[24px] text-[12px] tracking-[0.04em] rounded-[var(--radius-xs)]"
    :class="labels[status].cls"
  >
    {{ labels[status].label }}
  </span>
</template>
