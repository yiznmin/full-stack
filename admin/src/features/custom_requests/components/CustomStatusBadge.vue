<script setup lang="ts">
import type { CustomStatus } from '../api'

defineProps<{ status: CustomStatus }>()

const labels: Record<CustomStatus, { label: string; cls: string }> = {
  quote_pending: { label: '等待報價', cls: 'bg-[var(--color-state-warning)]/[0.12] text-state-warning' },
  negotiating: { label: '洽談中', cls: 'bg-[var(--color-state-info)]/[0.12] text-state-info' },
  quote_sent: { label: '報價已寄出', cls: 'bg-[var(--color-accent)]/[0.10] text-accent' },
  draft_revision: { label: '需修改', cls: 'bg-[var(--color-state-warning)]/[0.18] text-state-warning' },
  quote_confirmed: { label: '已確認', cls: 'bg-[var(--color-state-success)]/[0.12] text-state-success' },
  quote_rejected: { label: '已拒絕', cls: 'bg-paper-subtle text-ink-muted' },
  quote_expired: { label: '已逾期', cls: 'bg-paper-subtle text-ink-muted' },
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
