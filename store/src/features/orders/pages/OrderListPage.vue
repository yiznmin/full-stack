<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowLeft, Loader2, ShoppingBag } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { useOrdersQuery, STATUS_LABEL, STATUS_TAB } from '../queries'

type Tab = 'unpaid' | 'shipping' | 'done'

const tab = ref<Tab>('unpaid')
const page = ref(1)

// 後端的 status query 是單一字串，前端 tab 對應多種狀態
// → 不傳 status 全拉，前端自己依 tab 過濾
const ordersQuery = useOrdersQuery(undefined, page)
const allItems = computed(() => ordersQuery.data.value?.items ?? [])

const items = computed(() =>
  allItems.value.filter((o) => STATUS_TAB[o.status] === tab.value),
)
const totalCount = computed(() => allItems.value.length)
const tabCounts = computed(() => ({
  unpaid: allItems.value.filter((o) => STATUS_TAB[o.status] === 'unpaid').length,
  shipping: allItems.value.filter((o) => STATUS_TAB[o.status] === 'shipping').length,
  done: allItems.value.filter((o) => STATUS_TAB[o.status] === 'done').length,
}))

const isEmpty = computed(
  () => !ordersQuery.isPending.value && items.value.length === 0,
)

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

const TAB_LABEL: Record<Tab, string> = {
  unpaid: '待付款',
  shipping: '出貨中',
  done: '已完成',
}

const TAB_AUX: Record<Tab, string> = {
  unpaid: 'pending payment',
  shipping: 'in transit',
  done: 'closed',
}
</script>

<template>
  <main class="page">
    <RouterLink to="/profile" class="back-link">
      <ArrowLeft :size="14" />
      會員中心
    </RouterLink>

    <SectionMasthead
      no="08"
      chapter="Orders"
      title="我的訂單"
      :caption="totalCount > 0 ? `${totalCount} 筆` : 'My Orders'"
    />

    <!-- Tabs -->
    <nav class="tabs">
      <button
        v-for="t in (['unpaid', 'shipping', 'done'] as Tab[])"
        :key="t"
        type="button"
        class="tab"
        :class="{ 'tab-active': tab === t }"
        @click="tab = t"
      >
        <span class="tab-label">{{ TAB_LABEL[t] }}</span>
        <em class="tab-aux">{{ TAB_AUX[t] }}</em>
        <span v-if="tabCounts[t] > 0" class="tab-count">{{ tabCounts[t] }}</span>
      </button>
    </nav>

    <div v-if="ordersQuery.isPending.value" class="loading">
      <Loader2 :size="20" />
    </div>

    <section v-else-if="isEmpty" class="empty">
      <ShoppingBag class="empty-icon" />
      <h2 class="empty-title">這裡還沒有訂單</h2>
      <p class="empty-hint">
        {{ tab === 'unpaid' ? '所有訂單都已付款。' :
           tab === 'shipping' ? '目前沒有出貨中的訂單。' :
           '尚未完成任何訂單。' }}
      </p>
      <RouterLink to="/products" class="empty-cta">看看商品 →</RouterLink>
    </section>

    <ul v-else class="list">
      <li v-for="o in items" :key="o.id" class="card">
        <RouterLink :to="`/orders/${o.id}`" class="card-link">
          <div class="card-head">
            <span class="card-no">{{ o.order_number }}</span>
            <span class="card-date">{{ fmtDate(o.created_at) }}</span>
          </div>
          <div class="card-body">
            <div class="card-status">
              <span
                class="status-dot"
                :class="`dot-${STATUS_TAB[o.status]}`"
              ></span>
              <span class="status-text">{{ STATUS_LABEL[o.status] }}</span>
              <span class="status-aux">·</span>
              <span class="status-aux">{{ o.item_count }} 件商品</span>
            </div>
            <div class="card-total">
              <span class="total-label">總額</span>
              <span class="total-value">NT$ {{ o.total.toLocaleString() }}</span>
            </div>
          </div>
          <div class="card-arrow">→</div>
        </RouterLink>
      </li>
    </ul>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted); text-decoration: none;
  margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.tabs {
  margin-top: 36px;
  display: flex;
  gap: 8px;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--color-line);
}
.tab {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 14px 20px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: color 150ms, border-color 150ms;
  color: var(--color-ink-muted);
}
.tab:hover {
  color: var(--color-ink-default);
}
.tab-active {
  color: var(--color-ink-strong);
  border-bottom-color: var(--color-ink-strong);
}
.tab-label {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.06em;
}
.tab-aux {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 12px;
  color: var(--color-accent-soft);
  letter-spacing: 0.04em;
}
.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--color-accent-tint);
  color: var(--color-accent-deep);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0;
}
.tab-active .tab-count {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}

.loading {
  display: flex;
  justify-content: center;
  padding: 96px 0;
  color: var(--color-ink-muted);
}
.loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  text-align: center;
  padding: 96px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-icon {
  width: 36px; height: 36px;
  stroke: var(--color-ink-muted);
  stroke-width: 1.25;
  fill: none;
  margin-bottom: 20px;
  opacity: 0.5;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 12px;
}
.empty-hint {
  font-size: 14px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 24px;
}
.empty-cta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 4px;
}
.empty-cta:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  transition: border-color 150ms, transform 200ms ease;
}
.card:hover {
  border-color: var(--color-line);
  transform: translateY(-1px);
}
.card-link {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px 32px;
  align-items: center;
  padding: 22px 28px;
  text-decoration: none;
  color: inherit;
}

.card-head {
  grid-column: 1 / span 2;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
  margin-bottom: 4px;
}
.card-no {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}
.card-date {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--color-ink-muted);
}

.card-body {
  display: contents;
}
.card-status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot-unpaid { background: var(--color-state-warning); }
.dot-shipping { background: var(--color-fresh); }
.dot-done { background: var(--color-ink-muted); }

.status-text {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.status-aux {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
}

.card-total { text-align: right; }
.total-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 2px;
}
.total-value {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
  color: var(--color-accent-wine);
}

.card-arrow {
  display: none;
}

@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .tabs { overflow-x: auto; }
  .tab { padding: 12px 14px; flex-shrink: 0; }
  .card-link { padding: 18px 20px; gap: 12px 16px; }
}
</style>
