<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ShoppingBag } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import AppSearchInput from '@/shared/components/AppSearchInput.vue'
import AppDataTable, { type Column } from '@/shared/components/AppDataTable.vue'
import AppPagination from '@/shared/components/AppPagination.vue'
import Select from '@/shared/ui/Select.vue'

import { useOrdersQuery } from '../queries'
import type { OrderListItem, OrderStatus, OrderTypeFilter } from '../api'

const router = useRouter()
const route = useRoute()

const search = ref<string>(typeof route.query.search === 'string' ? route.query.search : '')
const status = ref<'' | OrderStatus>(
  (typeof route.query.status === 'string' ? route.query.status : '') as '' | OrderStatus,
)
const orderType = ref<'' | OrderTypeFilter>(
  (typeof route.query.order_type === 'string' ? route.query.order_type : '') as '' | OrderTypeFilter,
)
const dateFrom = ref<string>(typeof route.query.date_from === 'string' ? route.query.date_from : '')
const dateTo = ref<string>(typeof route.query.date_to === 'string' ? route.query.date_to : '')
const page = ref<number>(Number(route.query.page) > 0 ? Number(route.query.page) : 1)
const pageSize = 20

// 任一篩選條件變動時回到第一頁
watch([search, status, orderType, dateFrom, dateTo], () => {
  page.value = 1
})

// state ↔ URL query 雙向同步（讓 F5 / 分享網址保留條件）
watch(
  [search, status, orderType, dateFrom, dateTo, page],
  () => {
    router.replace({
      query: {
        ...(search.value ? { search: search.value } : {}),
        ...(status.value ? { status: status.value } : {}),
        ...(orderType.value ? { order_type: orderType.value } : {}),
        ...(dateFrom.value ? { date_from: dateFrom.value } : {}),
        ...(dateTo.value ? { date_to: dateTo.value } : {}),
        ...(page.value > 1 ? { page: String(page.value) } : {}),
      },
    })
  },
  { flush: 'post' },
)

const params = computed(() => ({
  search: search.value || undefined,
  status: status.value || undefined,
  order_type: orderType.value || undefined,
  date_from: dateFrom.value || undefined,
  date_to: dateTo.value || undefined,
  page: page.value,
  page_size: pageSize,
}))

const { data, isLoading, isError, error } = useOrdersQuery(params)

const items = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

const statusOptions = [
  { value: '', label: '全部狀態' },
  { value: 'pending_payment', label: '等待付款' },
  { value: 'payment_expired', label: '逾期未付' },
  { value: 'paid', label: '已付款' },
  { value: 'processing', label: '備貨中' },
  { value: 'shipped', label: '已出貨' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
  { value: 'refund_processing', label: '退款處理中' },
  { value: 'refunded', label: '已退款' },
  { value: 'partially_refunded', label: '部分退款' },
]

const typeOptions = [
  { value: '', label: '所有類型' },
  { value: 'regular', label: '一般商品' },
  { value: 'custom', label: '客製訂單' },
]

const statusBadge: Record<OrderStatus, { label: string; cls: string }> = {
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

const columns: Column<OrderListItem>[] = [
  { key: 'order_number', label: '訂單編號', width: '220px' },
  { key: 'customer', label: '客戶' },
  { key: 'status', label: '狀態', width: '110px' },
  { key: 'item_count', label: '品項', width: '60px', align: 'right' },
  { key: 'total', label: '金額', width: '120px', align: 'right' },
  { key: 'created_at', label: '下單時間', width: '170px' },
]

function goDetail(id: string) {
  router.push(`/admin/orders/${id}`)
}

function formatDateTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatMoney(n: number | string): string {
  const v = typeof n === 'string' ? Number(n) : n
  if (!Number.isFinite(v)) return '—'
  return `NT$ ${v.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

function clearFilters() {
  search.value = ''
  status.value = ''
  orderType.value = ''
  dateFrom.value = ''
  dateTo.value = ''
}

const hasFilter = computed(
  () => !!(search.value || status.value || orderType.value || dateFrom.value || dateTo.value),
)
</script>

<template>
  <PageHeader title="訂單管理" subtitle="客戶訂單列表、狀態流程、出貨與退款" />

  <!-- Filter bar -->
  <section class="bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)] p-4 mb-5">
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <div class="lg:col-span-2">
        <AppSearchInput v-model="search" placeholder="搜尋訂單編號 / 客戶名 / Email..." />
      </div>
      <Select v-model="status" :options="statusOptions" />
      <Select v-model="orderType" :options="typeOptions" />
      <div class="flex items-center gap-2">
        <input
          v-model="dateFrom"
          type="date"
          class="block w-full h-9 px-2 rounded-[var(--radius-xs)] bg-paper-surface text-ink-default border border-line-hairline text-[13px]"
          aria-label="下單日期起"
        />
        <span class="text-ink-muted text-[12px]">~</span>
        <input
          v-model="dateTo"
          type="date"
          class="block w-full h-9 px-2 rounded-[var(--radius-xs)] bg-paper-surface text-ink-default border border-line-hairline text-[13px]"
          aria-label="下單日期迄"
        />
      </div>
    </div>
    <div v-if="hasFilter" class="mt-3 flex justify-end">
      <button
        type="button"
        class="text-[12px] text-ink-muted hover:text-ink-strong transition-colors"
        @click="clearFilters"
      >
        清除所有篩選
      </button>
    </div>
  </section>

  <!-- Error -->
  <div
    v-if="isError"
    class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗：{{ (error as { message?: string })?.message ?? '未知錯誤' }}
  </div>

  <!-- Table -->
  <AppDataTable
    :columns="columns"
    :rows="items"
    :loading="isLoading"
    :row-key="(r) => r.id"
    :row-clickable="true"
    empty-text="尚無訂單"
    :empty-icon="ShoppingBag"
    @row-click="(r) => goDetail(r.id)"
  >
    <template #cell-order_number="{ row }">
      <span class="font-mono text-[13px] text-ink-strong">{{ row.order_number }}</span>
    </template>

    <template #cell-customer="{ row }">
      <div class="flex flex-col">
        <span class="text-ink-strong">{{ row.user_name }}</span>
        <span class="text-[11px] text-ink-muted">{{ row.user_email }}</span>
      </div>
    </template>

    <template #cell-status="{ row }">
      <span
        class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)]"
        :class="statusBadge[row.status as OrderStatus].cls"
      >
        {{ statusBadge[row.status as OrderStatus].label }}
      </span>
    </template>

    <template #cell-item_count="{ row }">
      <span class="font-mono text-[13px] text-ink-default">{{ row.item_count }}</span>
    </template>

    <template #cell-total="{ row }">
      <span class="font-mono text-[13px] text-ink-strong">{{ formatMoney(row.total) }}</span>
    </template>

    <template #cell-created_at="{ row }">
      <span class="text-ink-muted text-[12px] font-mono">{{ formatDateTime(row.created_at) }}</span>
    </template>
  </AppDataTable>

  <AppPagination
    v-if="total > pageSize"
    v-model:page="page"
    :page-size="pageSize"
    :total="total"
  />
</template>
