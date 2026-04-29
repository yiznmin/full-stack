<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sparkles } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import AppDataTable, { type Column } from '@/shared/components/AppDataTable.vue'
import AppPagination from '@/shared/components/AppPagination.vue'
import Select from '@/shared/ui/Select.vue'

import CustomStatusBadge from '../components/CustomStatusBadge.vue'
import { useCustomRequestsQuery } from '../queries'
import type {
  CustomRequestSummary,
  CustomStatus,
  RequestType,
} from '../api'

const router = useRouter()
const route = useRoute()

const status = ref<'' | CustomStatus>(
  (typeof route.query.status === 'string' ? route.query.status : '') as '' | CustomStatus,
)
const requestType = ref<'' | RequestType>(
  (typeof route.query.request_type === 'string' ? route.query.request_type : '') as '' | RequestType,
)
const page = ref<number>(Number(route.query.page) > 0 ? Number(route.query.page) : 1)
const pageSize = 20

watch([status, requestType], () => {
  page.value = 1
})

watch(
  [status, requestType, page],
  () => {
    router.replace({
      query: {
        ...(status.value ? { status: status.value } : {}),
        ...(requestType.value ? { request_type: requestType.value } : {}),
        ...(page.value > 1 ? { page: String(page.value) } : {}),
      },
    })
  },
  { flush: 'post' },
)

const params = computed(() => ({
  status: status.value || undefined,
  request_type: requestType.value || undefined,
  page: page.value,
  page_size: pageSize,
}))

const { data, isLoading, isError, error } = useCustomRequestsQuery(params)
const items = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

const statusOptions = [
  { value: '', label: '全部狀態' },
  { value: 'quote_pending', label: '等待報價' },
  { value: 'negotiating', label: '洽談中' },
  { value: 'quote_sent', label: '報價已寄出' },
  { value: 'draft_revision', label: '需修改' },
  { value: 'quote_confirmed', label: '已確認' },
  { value: 'quote_rejected', label: '已拒絕' },
  { value: 'quote_expired', label: '已逾期' },
]

const typeOptions = [
  { value: '', label: '所有類型' },
  { value: 'custom_photo', label: '客製照片' },
  { value: 'custom_spec', label: '客製規格' },
]

const requestTypeLabel: Record<RequestType, string> = {
  custom_photo: '照片',
  custom_spec: '規格',
}

const columns: Column<CustomRequestSummary>[] = [
  { key: 'id_short', label: '申請 ID', width: '110px' },
  { key: 'customer', label: '客戶' },
  { key: 'type', label: '類型', width: '80px' },
  { key: 'status', label: '狀態', width: '120px' },
  { key: 'quoted_price', label: '報價', width: '120px', align: 'right' },
  { key: 'revision', label: '修改', width: '70px', align: 'center' },
  { key: 'created_at', label: '申請時間', width: '170px' },
]

function goDetail(id: string) {
  router.push(`/admin/custom-requests/${id}`)
}

function fmtDateTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtMoney(n: number | null): string {
  if (n == null) return '—'
  return `NT$ ${Number(n).toLocaleString('zh-TW')}`
}
</script>

<template>
  <PageHeader title="客製訂單" subtitle="客戶客製申請、訊息溝通、報價流程" />

  <!-- Filter bar -->
  <section class="bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)] p-4 mb-5">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <Select v-model="status" :options="statusOptions" />
      <Select v-model="requestType" :options="typeOptions" />
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
    empty-text="尚無客製申請"
    :empty-icon="Sparkles"
    @row-click="(r) => goDetail(r.id)"
  >
    <template #cell-id_short="{ row }">
      <span class="font-mono text-[12px] text-ink-strong">{{ row.id.slice(0, 8) }}</span>
    </template>

    <template #cell-customer="{ row }">
      <div class="flex flex-col">
        <span class="text-ink-strong">{{ row.user_name }}</span>
        <span class="text-[11px] text-ink-muted">{{ row.user_email }}</span>
      </div>
    </template>

    <template #cell-type="{ row }">
      <span class="text-[12px] text-ink-default">{{ requestTypeLabel[row.request_type as RequestType] }}</span>
    </template>

    <template #cell-status="{ row }">
      <CustomStatusBadge :status="row.status as CustomStatus" />
    </template>

    <template #cell-quoted_price="{ row }">
      <span class="font-mono text-[13px]" :class="row.quoted_price ? 'text-ink-strong' : 'text-ink-muted'">
        {{ fmtMoney(row.quoted_price) }}
      </span>
    </template>

    <template #cell-revision="{ row }">
      <span class="font-mono text-[12px] text-ink-default">{{ row.revision_count }} / 3</span>
    </template>

    <template #cell-created_at="{ row }">
      <span class="text-ink-muted text-[12px] font-mono">{{ fmtDateTime(row.created_at) }}</span>
    </template>
  </AppDataTable>

  <AppPagination
    v-if="total > pageSize"
    v-model:page="page"
    :page-size="pageSize"
    :total="total"
  />
</template>
