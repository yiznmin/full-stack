<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Package, Plus, Pencil, Trash2, Star } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import AppSearchInput from '@/shared/components/AppSearchInput.vue'
import AppDataTable, { type Column } from '@/shared/components/AppDataTable.vue'
import AppPagination from '@/shared/components/AppPagination.vue'
import Button from '@/shared/ui/Button.vue'
import Select from '@/shared/ui/Select.vue'

import { useProductsQuery, useDeleteProductMutation } from '../queries'
import { updateProduct, getProduct } from '../api'
import type { ProductListItem, ProductStatus } from '../api'
import ProductsTabs from '../components/ProductsTabs.vue'

const router = useRouter()

const search = ref('')
const status = ref<'' | ProductStatus>('')
const page = ref(1)
const pageSize = 20

const params = computed(() => ({
  search: search.value || undefined,
  status: status.value || undefined,
  page: page.value,
  page_size: pageSize,
}))

const { data, isLoading, isError, error } = useProductsQuery(params)

const items = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

const statusOptions = [
  { value: '', label: '全部狀態' },
  { value: 'draft', label: '草稿' },
  { value: 'on_sale', label: '上架中' },
  { value: 'off_sale', label: '已下架' },
]

const statusLabels: Record<ProductStatus, { label: string; cls: string }> = {
  draft: {
    label: '草稿',
    cls: 'bg-[var(--color-state-info)]/[0.10] text-state-info',
  },
  on_sale: {
    label: '上架中',
    cls: 'bg-[var(--color-state-success)]/[0.10] text-state-success',
  },
  off_sale: {
    label: '已下架',
    cls: 'bg-paper-subtle text-ink-muted',
  },
}

const columns: Column<ProductListItem>[] = [
  { key: 'cover', label: '封面', width: '64px' },
  { key: 'title', label: '商品名稱' },
  { key: 'series', label: '系列', width: '140px' },
  { key: 'status', label: '狀態', width: '100px' },
  { key: 'variants', label: '變體', width: '70px', align: 'right' },
  { key: 'updated', label: '最後更新', width: '160px' },
  { key: 'actions', label: '', width: '120px', align: 'right' },
]

const del = useDeleteProductMutation()
const deletingId = ref<string | null>(null)
const togglingId = ref<string | null>(null)

async function toggleFeatured(row: ProductListItem) {
  togglingId.value = row.id
  try {
    // 拿完整 product detail（API 需要完整 payload，包含 description / tags 等）
    const detail = await getProduct(row.id)
    await updateProduct(row.id, {
      title: detail.title,
      description: detail.description ?? '',
      cover_image_url: detail.cover_image_url,
      series_id: detail.series_id,
      series_order: detail.series_order ?? 0,
      status: detail.status,
      is_featured: !detail.is_featured,
      tag_ids: detail.tags.map((t) => t.id),
    })
    // 重撈 list（不依賴 cache，避免 stale）
    location.reload()
  } catch (e) {
    alert((e as { message?: string }).message || '切換失敗')
  } finally {
    togglingId.value = null
  }
}

async function handleDelete(row: ProductListItem) {
  if (!confirm(`確定刪除「${row.title}」？`)) return
  deletingId.value = row.id
  try {
    await del.mutateAsync(row.id)
  } catch (e) {
    const err = e as { status?: number; message?: string }
    // 409 直接顯示 backend 訊息（會具體說明是因為「上架中」還是「變體仍啟用」）
    alert(err.message || '刪除失敗')
  } finally {
    deletingId.value = null
  }
}

function goEdit(id: string) {
  router.push(`/admin/products/${id}`)
}

function goNew() {
  router.push('/admin/products/new')
}

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<template>
  <PageHeader title="商品管理" subtitle="管理上架商品、變體、系列與標籤">
    <template #actions>
      <Button variant="primary" @click="goNew">
        <Plus :size="14" :stroke-width="1.75" />
        新增商品
      </Button>
    </template>
  </PageHeader>

  <ProductsTabs class="mb-6" />

  <!-- Filter bar -->
  <section class="flex flex-col sm:flex-row gap-3 mb-5">
    <div class="flex-1 sm:max-w-[360px]">
      <AppSearchInput
        v-model="search"
        placeholder="搜尋商品名稱..."
      />
    </div>
    <div class="sm:w-[180px]">
      <Select v-model="status" :options="statusOptions" />
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
    empty-text="尚無商品"
    :empty-icon="Package"
    @row-click="(r) => goEdit(r.id)"
  >
    <template #cell-cover="{ row }">
      <img
        v-if="row.cover_image_url"
        :src="row.cover_image_url"
        alt=""
        class="w-12 h-12 object-cover rounded-[var(--radius-xs)] border border-line-hairline"
      />
      <div
        v-else
        class="w-12 h-12 bg-paper-subtle rounded-[var(--radius-xs)] border border-line-hairline"
      />
    </template>

    <template #cell-title="{ row }">
      <div class="flex items-center gap-2">
        <span class="font-medium text-ink-strong">{{ row.title }}</span>
        <span
          v-if="row.is_featured"
          class="text-[11px] px-1.5 h-[18px] inline-flex items-center gap-0.5 rounded-[var(--radius-xs)] bg-[var(--color-state-warning)]/[0.12] text-state-warning"
          title="精選商品"
        >
          <Star :size="10" :stroke-width="1.75" fill="currentColor" />精選
        </span>
      </div>
    </template>

    <template #cell-series="{ row }">
      <span :class="row.series_name ? 'text-ink-default' : 'text-ink-muted'">
        {{ row.series_name || '—' }}
      </span>
    </template>

    <template #cell-status="{ row }">
      <span
        class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)]"
        :class="statusLabels[row.status as ProductStatus].cls"
      >
        {{ statusLabels[row.status as ProductStatus].label }}
      </span>
    </template>

    <template #cell-variants="{ row }">
      <span class="font-mono text-[13px]">{{ row.variant_count }}</span>
    </template>

    <template #cell-updated="{ row }">
      <span class="text-ink-muted text-[12px] font-mono">{{ formatDate(row.updated_at) }}</span>
    </template>

    <template #cell-actions="{ row }">
      <div class="flex items-center justify-end gap-1" @click.stop>
        <button
          type="button"
          class="h-8 w-8 flex items-center justify-center rounded-[var(--radius-xs)] transition-colors disabled:opacity-50"
          :class="row.is_featured
            ? 'text-state-warning hover:bg-[var(--color-state-warning)]/[0.10]'
            : 'text-ink-muted hover:bg-paper-subtle hover:text-state-warning'"
          :title="row.is_featured ? '取消精選' : '設為精選'"
          :disabled="togglingId === row.id"
          @click="toggleFeatured(row)"
        >
          <Star :size="14" :stroke-width="1.5" :fill="row.is_featured ? 'currentColor' : 'none'" />
        </button>
        <button
          type="button"
          class="h-8 w-8 flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-paper-subtle hover:text-ink-strong transition-colors"
          aria-label="編輯"
          @click="goEdit(row.id)"
        >
          <Pencil :size="14" :stroke-width="1.5" />
        </button>
        <button
          type="button"
          class="h-8 w-8 flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-[var(--color-state-danger)]/[0.10] hover:text-state-danger transition-colors disabled:opacity-50"
          :disabled="deletingId === row.id"
          aria-label="刪除"
          @click="handleDelete(row)"
        >
          <Trash2 :size="14" :stroke-width="1.5" />
        </button>
      </div>
    </template>

    <template #empty-action>
      <Button variant="primary" class="mt-5" @click="goNew">
        <Plus :size="14" :stroke-width="1.75" />
        新增第一個商品
      </Button>
    </template>
  </AppDataTable>

  <AppPagination
    v-if="total > pageSize"
    v-model:page="page"
    :page-size="pageSize"
    :total="total"
  />
</template>
