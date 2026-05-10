<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDownRight, ArrowUpRight, Minus, Loader2, AlertTriangle } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'

import { useDashboardSummary } from '../queries'

const router = useRouter()
const { data, isLoading, isError, error } = useDashboardSummary()

interface Stat {
  label: string
  value: string
  unit?: string
  trend?: 'up' | 'down' | 'flat'
  delta?: string
  meta?: string
}

const stats = computed<Stat[]>(() => {
  const s = data.value?.stats
  if (!s) return []
  return [
    {
      label: '本月訂單',
      value: String(s.orders_this_month.value),
      unit: '單',
      trend: s.orders_this_month.trend.direction,
      delta: s.orders_this_month.trend.delta,
      meta: s.orders_this_month.meta,
    },
    {
      label: '待處理客製',
      value: String(s.custom_pending.value),
      trend: s.custom_pending.value > 0 ? 'up' : 'flat',
      delta: s.custom_pending.value > 0 ? `+${s.custom_pending.value}` : '—',
      meta: `報價中 ${s.custom_pending.breakdown.quote_pending} / 議價 ${s.custom_pending.breakdown.negotiating} / 已送 ${s.custom_pending.breakdown.quote_sent}`,
    },
    {
      label: '製作中批次',
      value: String(s.production_in_progress.value),
      trend: 'flat',
      delta: '—',
      meta: '工坊產線',
    },
    {
      label: '本月營收',
      value: s.revenue_this_month.value.toLocaleString('zh-TW', {
        maximumFractionDigits: 0,
      }),
      unit: 'NTD',
      trend: s.revenue_this_month.trend.direction,
      delta: s.revenue_this_month.trend.delta,
      meta: s.revenue_this_month.meta,
    },
  ]
})

const ORDER_STATUS_LABEL: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'info' }> = {
  pending_payment: { label: '待付款', tone: 'warning' },
  payment_expired: { label: '逾期未付', tone: 'danger' },
  paid: { label: '已付款', tone: 'success' },
  processing: { label: '製作中', tone: 'info' },
  shipped: { label: '已出貨', tone: 'info' },
  completed: { label: '已完成', tone: 'success' },
  cancelled: { label: '已取消', tone: 'danger' },
  refund_processing: { label: '退款處理中', tone: 'warning' },
  refunded: { label: '已退款', tone: 'danger' },
  partially_refunded: { label: '部分退款', tone: 'warning' },
}

const CUSTOM_STATUS_LABEL: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'info' }> = {
  quote_pending: { label: '待報價', tone: 'warning' },
  negotiating: { label: '議價中', tone: 'warning' },
  quote_sent: { label: '報價已送出', tone: 'info' },
  in_cart: { label: '已加購物車', tone: 'success' },
  rejected: { label: '已拒絕', tone: 'danger' },
  expired: { label: '已逾期', tone: 'danger' },
}

interface ActivityRow {
  kind: '訂單' | '客製'
  title: string
  meta: string
  state: { label: string; tone: 'success' | 'warning' | 'danger' | 'info' }
  href: string
}

function fmtRelative(iso: string | null): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const sec = Math.floor((Date.now() - t) / 1000)
  if (sec < 60) return `${sec} 秒前`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分鐘前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小時前`
  return `${Math.floor(sec / 86400)} 天前`
}

const activities = computed<ActivityRow[]>(() => {
  const list = data.value?.recent_activities ?? []
  return list.map((a) => {
    if (a.kind === 'order') {
      const stm = ORDER_STATUS_LABEL[a.status] ?? { label: a.status, tone: 'info' as const }
      return {
        kind: '訂單' as const,
        title: a.title,
        meta: fmtRelative(a.created_at),
        state: stm,
        href: `/admin/orders/${a.id}`,
      }
    }
    const stm = CUSTOM_STATUS_LABEL[a.status] ?? { label: a.status, tone: 'info' as const }
    return {
      kind: '客製' as const,
      title: a.title,
      meta: fmtRelative(a.created_at),
      state: stm,
      href: `/admin/custom-requests/${a.id}`,
    }
  })
})

const productionPipeline = computed(() => {
  const p = data.value?.production_pipeline
  if (!p) return []
  return [
    { stage: '待製作', count: p.pending },
    { stage: '製作中', count: p.processing },
    { stage: '已完成', count: p.completed },
    { stage: '失敗', count: p.failed },
  ]
})

const stateClass: Record<string, { bg: string; color: string }> = {
  success: { bg: 'bg-[var(--color-state-success)]/[0.10]', color: 'text-state-success' },
  warning: { bg: 'bg-[var(--color-state-warning)]/[0.10]', color: 'text-state-warning' },
  danger: { bg: 'bg-[var(--color-state-danger)]/[0.10]', color: 'text-state-danger' },
  info: { bg: 'bg-[var(--color-state-info)]/[0.10]', color: 'text-state-info' },
}

const trendIcon = { up: ArrowUpRight, down: ArrowDownRight, flat: Minus } as const
const trendColor = {
  up: 'text-state-success',
  down: 'text-state-danger',
  flat: 'text-ink-muted',
}
</script>

<template>
  <PageHeader title="儀表板" subtitle="易木工房 · 本日工作概要">
    <template #actions>
      <Button variant="secondary" @click="router.push('/admin/reports')">查看報表</Button>
      <Button variant="primary" @click="router.push('/admin/print-batches')">新增列印批次</Button>
    </template>
  </PageHeader>

  <div v-if="isLoading" class="flex items-center gap-2 text-ink-muted text-[13px] mb-6">
    <Loader2 :size="16" class="animate-spin" />
    <span>載入儀表板資料…</span>
  </div>
  <div
    v-else-if="isError"
    class="mb-6 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-center gap-2"
  >
    <AlertTriangle :size="14" />
    載入失敗：{{ (error as { message?: string })?.message ?? '未知錯誤' }}
  </div>

  <template v-else>
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <Card v-for="s in stats" :key="s.label">
        <p class="text-[12px] uppercase tracking-[0.06em] text-ink-muted">
          {{ s.label }}
        </p>
        <div class="mt-3 mb-2 flex items-baseline gap-1.5">
          <span class="font-mono text-[28px] leading-[34px] text-ink-strong">
            {{ s.value }}
          </span>
          <span v-if="s.unit" class="text-[12px] text-ink-muted">{{ s.unit }}</span>
        </div>
        <div v-if="s.trend" class="flex items-center gap-1 text-[12px]">
          <component
            :is="trendIcon[s.trend]"
            :size="13"
            :stroke-width="1.75"
            :class="trendColor[s.trend]"
          />
          <span :class="trendColor[s.trend]" class="font-mono">{{ s.delta }}</span>
          <span class="text-ink-muted">{{ s.meta }}</span>
        </div>
      </Card>
    </section>

    <section class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
      <Card class="lg:col-span-2">
        <div class="flex items-baseline justify-between mb-5">
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
            最近活動
          </h2>
          <a
            class="text-[12px] text-accent underline underline-offset-4 cursor-pointer"
            @click="router.push('/admin/orders')"
          >查看全部</a>
        </div>
        <ul v-if="activities.length > 0">
          <li
            v-for="r in activities"
            :key="r.href"
            class="flex items-center gap-4 py-3.5 border-b border-line-hairline last:border-0 cursor-pointer hover:bg-paper-subtle/40 -mx-3 px-3 transition-colors"
            @click="router.push(r.href)"
          >
            <span
              class="text-[11px] tracking-[0.06em] uppercase px-2 h-[22px] flex items-center rounded-[var(--radius-xs)] border border-line-strong text-ink-muted shrink-0"
            >
              {{ r.kind }}
            </span>
            <span class="text-[13px] text-ink-default flex-1 min-w-0 truncate">
              {{ r.title }}
            </span>
            <span
              class="text-[11px] tracking-[0.04em] px-2 h-[22px] flex items-center rounded-[var(--radius-xs)] shrink-0"
              :class="[stateClass[r.state.tone].bg, stateClass[r.state.tone].color]"
            >
              {{ r.state.label }}
            </span>
            <span class="text-[12px] text-ink-muted whitespace-nowrap shrink-0 w-20 text-right">
              {{ r.meta }}
            </span>
          </li>
        </ul>
        <p v-else class="text-[13px] text-ink-muted py-6 text-center">
          目前沒有最近活動
        </p>
      </Card>

      <Card>
        <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-5">
          快速入口
        </h2>
        <div class="space-y-1">
          <a
            class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors"
            @click="router.push('/admin/production')"
          >上傳新原圖 →</a>
          <a
            class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors"
            @click="router.push('/admin/print-batches')"
          >新建列印批次 →</a>
          <a
            class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors"
            @click="router.push('/admin/notifications')"
          >
            查看待處理通知
            <span
              v-if="data?.stats.unhandled_notifications.value && data.stats.unhandled_notifications.value > 0"
              class="ml-1 inline-flex items-center px-1.5 h-[16px] text-[10px] rounded-[999px] bg-[var(--color-accent-wine)]/[0.10] text-accent-wine font-medium"
            >
              {{ data.stats.unhandled_notifications.value }}
            </span>
            →
          </a>
          <a
            class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors"
            @click="router.push('/admin/discounts')"
          >發放優惠券 →</a>
        </div>
      </Card>
    </section>

    <section>
      <Card>
        <div class="flex items-baseline justify-between mb-5">
          <div>
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
              製作流水線
            </h2>
            <p class="text-[12px] text-ink-muted mt-0.5">本月各階段數量</p>
          </div>
          <a
            class="text-[12px] text-accent underline underline-offset-4 cursor-pointer"
            @click="router.push('/admin/production')"
          >前往製作系統</a>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 sm:divide-x divide-line-hairline">
          <div
            v-for="(p, i) in productionPipeline"
            :key="p.stage"
            class="px-5 py-3"
            :class="[
              i % 2 === 1 ? 'border-l sm:border-l-0 border-line-hairline' : '',
              i >= 2 ? 'border-t sm:border-t-0 border-line-hairline' : '',
            ]"
          >
            <p class="text-[11px] tracking-[0.06em] uppercase text-ink-muted">
              {{ p.stage }}
            </p>
            <p class="font-mono text-[24px] leading-[30px] text-ink-strong mt-1.5">
              {{ p.count }}
            </p>
          </div>
        </div>
      </Card>
    </section>
  </template>
</template>
