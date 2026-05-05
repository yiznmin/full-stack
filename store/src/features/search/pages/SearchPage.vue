<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { useSearchProductsQuery } from '@/features/products/queries'
import ProductGrid from '@/features/products/components/ProductGrid.vue'
import Pagination from '@/features/products/components/Pagination.vue'

const route = useRoute()
const router = useRouter()

const q = computed(() =>
  typeof route.query.q === 'string' ? route.query.q : '',
)
const page = computed(() => Number(route.query.page) || 1)

// 沒 q → 重導 /products
watch(
  q,
  (val) => {
    if (val.length === 0) {
      router.replace('/products')
    }
  },
  { immediate: true },
)

const searchQuery = useSearchProductsQuery(q.value, page.value, 24)

// q / page 變更時重打
watch(
  () => [q.value, page.value],
  () => {
    searchQuery.refetch()
  },
)

const items = computed(() => searchQuery.data.value?.items ?? [])
const total = computed(() => searchQuery.data.value?.total ?? 0)
const isEmpty = computed(
  () => !searchQuery.isPending.value && items.value.length === 0,
)

function onPageChange(newPage: number) {
  router.push({ path: '/search', query: { ...route.query, page: newPage > 1 ? String(newPage) : undefined } })
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}
</script>

<template>
  <section class="page">
    <header class="page-header">
      <div class="page-eyebrow">Search</div>
      <h1 class="page-title">
        搜尋結果：<span class="page-q">{{ q }}</span>
      </h1>
      <div v-if="!searchQuery.isPending.value" class="result-count">
        共 {{ total }} 件商品
      </div>
    </header>

    <div v-if="searchQuery.isPending.value" class="loading">
      <Loader2 :size="20" />
    </div>

    <div v-else-if="isEmpty" class="empty">
      <p class="empty-title">找不到「{{ q }}」相關商品</p>
      <p class="empty-hint">試試別的關鍵字，或回去看全部商品。</p>
      <RouterLink to="/products" class="empty-cta">回商品列表 →</RouterLink>
    </div>

    <template v-else>
      <ProductGrid :products="items" />
      <div class="page-footer">
        <Pagination
          :page="page"
          :total="total"
          :page-size="24"
          @change="onPageChange"
        />
      </div>
    </template>
  </section>
</template>

<style scoped>
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.page-header {
  margin-bottom: 56px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-line);
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}

.page-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 12px;
}

.page-q {
  color: var(--color-accent);
  font-style: italic;
}

.result-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.loading {
  padding: 96px 0;
  display: flex;
  justify-content: center;
  color: var(--color-ink-muted);
}
.loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5;
  fill: none;
  stroke: currentColor;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  padding: 96px 24px;
  text-align: center;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0 0 24px;
  letter-spacing: 0.04em;
}
.empty-cta {
  display: inline-block;
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}

.page-footer {
  margin-top: 64px;
  display: flex;
  justify-content: center;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 64px; }
  .page-title { font-size: 28px; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .page-title { font-size: 22px; }
}
</style>
