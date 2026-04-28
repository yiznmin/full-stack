<script setup lang="ts">
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'

interface Stat {
  label: string
  value: string
  unit?: string
  trend: 'up' | 'down' | 'flat'
  delta: string
  meta: string
}

const stats: Stat[] = [
  {
    label: '本月訂單',
    value: '142',
    unit: '單',
    trend: 'up',
    delta: '+12%',
    meta: '較上月',
  },
  {
    label: '待處理客製',
    value: '8',
    trend: 'up',
    delta: '+3',
    meta: '報價中 4 / 待確認 4',
  },
  {
    label: '製作中批次',
    value: '5',
    trend: 'flat',
    delta: '—',
    meta: '工坊產線',
  },
  {
    label: '本月營收',
    value: '286,400',
    unit: 'NTD',
    trend: 'up',
    delta: '+18%',
    meta: '較上月',
  },
]

interface RecentItem {
  kind: '訂單' | '客製' | '通知' | '製作'
  title: string
  meta: string
  state?: { label: string; tone: 'success' | 'warning' | 'danger' | 'info' }
}

const recents: RecentItem[] = [
  {
    kind: '訂單',
    title: 'PL-202604-0142',
    meta: '5 分鐘前',
    state: { label: '已付款', tone: 'success' },
  },
  {
    kind: '客製',
    title: '#A8C2 — 婚紗 4 人 60×80',
    meta: '12 分鐘前',
    state: { label: '報價已送出', tone: 'info' },
  },
  {
    kind: '通知',
    title: '苔綠 #4F6B3A 庫存 < 200ml',
    meta: '1 小時前',
    state: { label: '需補貨', tone: 'warning' },
  },
  {
    kind: '訂單',
    title: 'PL-202604-0141',
    meta: '2 小時前',
    state: { label: '已出貨', tone: 'success' },
  },
  {
    kind: '製作',
    title: 'JOB-A24F · 30×40 · standard',
    meta: '3 小時前',
    state: { label: '完成', tone: 'success' },
  },
  {
    kind: '客製',
    title: '#A8B7 — 寵物 30×30',
    meta: '4 小時前',
    state: { label: '退費完成', tone: 'danger' },
  },
]

const productionPipeline = [
  { stage: '待製作', count: 12 },
  { stage: '製作中', count: 5 },
  { stage: '已完成', count: 38 },
  { stage: '已出貨', count: 89 },
]

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
      <Button variant="secondary">匯出報表</Button>
      <Button variant="primary">新增列印批次</Button>
    </template>
  </PageHeader>

  <!-- Stats grid -->
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
      <div class="flex items-center gap-1 text-[12px]">
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

  <!-- Two-column section -->
  <section class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
    <Card class="lg:col-span-2">
      <div class="flex items-baseline justify-between mb-5">
        <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
          最近活動
        </h2>
        <a class="text-[12px] text-accent underline underline-offset-4">查看全部</a>
      </div>
      <ul>
        <li
          v-for="r in recents"
          :key="r.title"
          class="flex items-center gap-4 py-3.5 border-b border-line-hairline last:border-0"
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
            v-if="r.state"
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
    </Card>

    <Card>
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-5">
        快速入口
      </h2>
      <div class="space-y-1">
        <a class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors">
          上傳新原圖 →
        </a>
        <a class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors">
          新建列印批次 →
        </a>
        <a class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors">
          查看待處理通知 →
        </a>
        <a class="block py-3 px-3 -mx-3 rounded-[var(--radius-xs)] hover:bg-paper-subtle text-[13px] text-ink-default cursor-pointer transition-colors">
          發放優惠券 →
        </a>
      </div>
    </Card>
  </section>

  <!-- Production pipeline -->
  <section>
    <Card>
      <div class="flex items-baseline justify-between mb-5">
        <div>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
            製作流水線
          </h2>
          <p class="text-[12px] text-ink-muted mt-0.5">本月各階段數量</p>
        </div>
        <a class="text-[12px] text-accent underline underline-offset-4">前往製作系統</a>
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
