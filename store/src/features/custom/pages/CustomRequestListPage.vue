<script setup lang="ts">
import { computed, ref } from 'vue'
import { Loader2, FileQuestion } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { useCustomRequestListQuery } from '../queries'
import { STATUS_LABEL, REQUEST_TYPE_LABEL, type RequestStatus } from '../api'

const FILTERS: Array<{ value: RequestStatus | null; label: string }> = [
  { value: null, label: '全部' },
  { value: 'quote_pending', label: '等待報價' },
  { value: 'negotiating', label: '洽談中' },
  { value: 'quote_sent', label: '報價已送達' },
  { value: 'quote_confirmed', label: '已確認' },
  { value: 'quote_expired', label: '已逾期' },
  { value: 'quote_rejected', label: '已拒絕' },
]

const filter = ref<RequestStatus | null>(null)
const page = ref(1)
const PAGE_SIZE = 12

const listQuery = useCustomRequestListQuery(() => ({
  status: filter.value || undefined,
  page: page.value,
  page_size: PAGE_SIZE,
}))

const items = computed(() => listQuery.data.value?.items ?? [])
const total = computed(() => listQuery.data.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function setFilter(v: RequestStatus | null) {
  filter.value = v
  page.value = 1
}

function statusTone(status: RequestStatus): string {
  switch (status) {
    case 'quote_sent': return 'tone-action'
    case 'quote_confirmed': return 'tone-ok'
    case 'quote_rejected':
    case 'quote_expired': return 'tone-danger'
    case 'draft_revision':
    case 'negotiating': return 'tone-progress'
    default: return 'tone-neutral'
  }
}
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="07"
      chapter="My Requests"
      title="我的客製申請"
      caption="Custom orders"
    />

    <!-- filter chips -->
    <div class="filter-row">
      <button
        v-for="f in FILTERS"
        :key="f.value ?? 'all'"
        type="button"
        class="filter-chip"
        :class="{ active: filter === f.value }"
        @click="setFilter(f.value)"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- loading -->
    <div v-if="listQuery.isPending.value" class="state">
      <Loader2 :size="18" class="spin" />
      <span>載入中…</span>
    </div>

    <!-- empty -->
    <div v-else-if="items.length === 0" class="state empty">
      <FileQuestion :size="32" :stroke-width="1.25" />
      <p class="state-title">{{ filter ? '此狀態目前沒有申請。' : '您尚未提出任何客製申請。' }}</p>
      <RouterLink to="/custom" class="cta">前往申請 →</RouterLink>
    </div>

    <!-- list -->
    <ul v-else class="list">
      <li v-for="r in items" :key="r.id" class="row">
        <RouterLink :to="{ name: 'custom-request-detail', params: { id: r.id } }">
          <div class="row-main">
            <div class="row-id">{{ REQUEST_TYPE_LABEL[r.request_type] }}</div>
            <div class="row-meta">
              <span>{{ fmtDate(r.created_at) }}</span>
              <span v-if="r.quoted_price">NT$ {{ r.quoted_price }}</span>
              <span v-if="r.revision_count > 0">已修改 {{ r.revision_count }} 次</span>
            </div>
          </div>
          <span class="status" :class="statusTone(r.status)">{{ STATUS_LABEL[r.status] }}</span>
        </RouterLink>
      </li>
    </ul>

    <!-- pagination -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="page--">‹</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="page++">›</button>
    </div>
  </main>
</template>

<style scoped>
.page {
  max-width: 960px; margin: 0 auto;
  padding: 56px 24px 96px;
}
.filter-row {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 32px 0 24px;
}
.filter-chip {
  padding: 8px 14px; cursor: pointer;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-size: 13px; font-family: inherit;
  color: var(--color-ink-default);
  transition: border-color 150ms, color 150ms, background 150ms;
}
.filter-chip:hover {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.filter-chip.active {
  background: var(--color-accent-deep); border-color: var(--color-accent-deep);
  color: #FCF7E5;
}
.state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.empty .state-title {
  font-family: var(--font-cn-serif); font-size: 17px;
  color: var(--color-ink-default); margin: 0;
}
.cta {
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.2em;
  color: var(--color-accent-deep); text-decoration: none;
  border-bottom: 1px solid currentColor; padding-bottom: 2px;
}

.list { list-style: none; padding: 0; margin: 0; }
.row { border-top: 1px solid var(--color-line); }
.row:last-child { border-bottom: 1px solid var(--color-line); }
.row a {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 4px; gap: 16px;
  text-decoration: none; color: var(--color-ink-strong);
  transition: background 150ms;
}
.row a:hover { background: var(--color-paper-surface, #FCF7E5); }
.row-id {
  font-family: var(--font-cn-serif); font-size: 16px;
  color: var(--color-ink-strong); margin-bottom: 6px;
}
.row-meta {
  display: flex; gap: 12px;
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.1em; color: var(--color-ink-muted);
}
.status {
  flex-shrink: 0; padding: 4px 12px; border-radius: 999px;
  font-size: 12px; letter-spacing: 0.06em;
  border: 1px solid transparent;
}
.tone-action {
  background: var(--color-accent-deep); color: #FCF7E5;
  animation: pulse 1.6s ease-in-out infinite;
}
.tone-ok {
  background: rgba(122, 156, 110, 0.15);
  color: #5A7A4F; border-color: rgba(122, 156, 110, 0.3);
}
.tone-danger {
  background: rgba(184, 91, 88, 0.1);
  color: #B85B58; border-color: rgba(184, 91, 88, 0.25);
}
.tone-progress {
  background: rgba(212, 165, 116, 0.18);
  color: #8B6232; border-color: rgba(212, 165, 116, 0.35);
}
.tone-neutral {
  background: var(--color-paper-surface, #FCF7E5);
  color: var(--color-ink-muted); border-color: var(--color-line);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.pagination {
  margin-top: 32px; display: flex; justify-content: center; align-items: center;
  gap: 16px; font-family: var(--font-mono); font-size: 13px;
  color: var(--color-ink-default);
}
.pagination button {
  width: 32px; height: 32px; cursor: pointer;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-size: 16px;
  color: var(--color-ink-default);
}
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination button:hover:not(:disabled) {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
