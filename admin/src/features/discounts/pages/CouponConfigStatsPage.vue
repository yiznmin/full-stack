<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, Loader2, BarChart3 } from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'

import { useCouponConfigStatsQuery, useCouponConfigsQuery } from '../queries'
import { COUPON_TYPE_LABEL, formatDiscount, type CouponType } from '../api'

const route = useRoute()
const router = useRouter()

const configId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))

const { data: configsData } = useCouponConfigsQuery()
const config = computed(() => configsData.value?.items.find((c) => c.id === configId.value))

const { data: stats, isLoading, isError } = useCouponConfigStatsQuery(configId)

function fmtMoney(n: number): string {
  return `NT$ ${n.toLocaleString('zh-TW')}`
}
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/discounts')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回折扣管理
    </button>
  </div>

  <header class="mb-7 pb-5 border-b border-line-hairline">
    <h1 class="font-display text-ink-strong text-[24px] leading-[32px]">
      使用統計
      <span v-if="config" class="ml-2 text-[18px] text-ink-muted">
        — {{ COUPON_TYPE_LABEL[config.coupon_type as CouponType] }}
      </span>
    </h1>
    <p v-if="config" class="mt-1 text-[13px] text-ink-muted">
      {{ formatDiscount(config.discount_type, config.discount_value) }}
      <span v-if="config.min_purchase">· 門檻 NT$ {{ config.min_purchase }}</span>
    </p>
  </header>

  <div v-if="isLoading" class="py-12 flex justify-center text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
  </div>

  <div
    v-else-if="isError"
    class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗
  </div>

  <template v-else-if="stats">
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      <Card>
        <p class="text-[12px] text-ink-muted tracking-[0.04em] uppercase mb-1">總發放</p>
        <p class="font-display text-ink-strong text-[26px]">{{ stats.total_issued.toLocaleString() }}</p>
      </Card>
      <Card>
        <p class="text-[12px] text-ink-muted tracking-[0.04em] uppercase mb-1">總使用</p>
        <p class="font-display text-ink-strong text-[26px]">{{ stats.total_used.toLocaleString() }}</p>
        <p v-if="stats.total_issued > 0" class="text-[12px] text-ink-muted">
          使用率 {{ ((stats.total_used / stats.total_issued) * 100).toFixed(1) }}%
        </p>
      </Card>
      <Card>
        <p class="text-[12px] text-ink-muted tracking-[0.04em] uppercase mb-1">折扣總金額</p>
        <p class="font-display text-ink-strong text-[26px] font-mono">{{ fmtMoney(stats.total_discount_amount) }}</p>
      </Card>
    </div>

    <Card>
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">
        <BarChart3 :size="14" :stroke-width="1.5" class="inline mr-1" />
        月份趨勢
      </h2>
      <div v-if="stats.usage_by_month.length === 0" class="text-ink-muted text-[13px] text-center py-6">
        尚無資料
      </div>
      <table v-else class="w-full text-[13px]">
        <thead>
          <tr class="border-b border-line-hairline text-left text-ink-muted">
            <th class="py-2">月份</th>
            <th class="py-2 text-right">發放</th>
            <th class="py-2 text-right">使用</th>
            <th class="py-2 text-right">折扣金額</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in stats.usage_by_month" :key="m.month" class="border-b border-line-hairline last:border-0">
            <td class="py-2 font-mono text-[12px]">{{ m.month }}</td>
            <td class="py-2 text-right font-mono">{{ m.issued }}</td>
            <td class="py-2 text-right font-mono">{{ m.used }}</td>
            <td class="py-2 text-right font-mono">{{ fmtMoney(m.discount_amount) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="mt-3 text-[11px] text-ink-muted">
        圖表化呈現 → 等 F11 銷售報表模組統一引入 echarts 後再升級。
      </p>
    </Card>
  </template>
</template>
