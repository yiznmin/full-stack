<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Pencil, Trash2, Loader2, X, Layers, Star } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Input from '@/shared/ui/Input.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Label from '@/shared/ui/Label.vue'
import Button from '@/shared/ui/Button.vue'
import Dialog from '@/shared/ui/Dialog.vue'

import {
  useSeriesQuery,
  useCreateSeriesMutation,
  useUpdateSeriesMutation,
  useDeleteSeriesMutation,
} from '../queries'
import type { Series } from '../api'
import ProductsTabs from '../components/ProductsTabs.vue'
import ThemePicker from '../components/ThemePicker.vue'
import ProductCoverUpload from '../components/ProductCoverUpload.vue'

const { data: series, isLoading } = useSeriesQuery()
const createMut = useCreateSeriesMutation()
const updateMut = useUpdateSeriesMutation()
const deleteMut = useDeleteSeriesMutation()

const dialogOpen = ref(false)
const editing = ref<Series | null>(null)
const formName = ref('')
const formDesc = ref('')
const formThemeId = ref<string | null>(null)
const formIsFeatured = ref(false)
const formCover = ref('')

function openCreate() {
  editing.value = null
  formName.value = ''
  formDesc.value = ''
  formThemeId.value = null
  formIsFeatured.value = false
  formCover.value = ''
  dialogOpen.value = true
}

function openEdit(s: Series) {
  editing.value = s
  formName.value = s.name
  formDesc.value = s.description ?? ''
  formThemeId.value = s.theme_id
  formIsFeatured.value = s.is_featured
  formCover.value = s.sample_cover_image_url ?? ''
  dialogOpen.value = true
}

async function submit() {
  const name = formName.value.trim()
  if (!name) return
  const payload = {
    name,
    description: formDesc.value.trim() || null,
    theme_id: formThemeId.value,
    is_featured: formIsFeatured.value,
    sample_cover_image_url: formCover.value.trim() || null,
  }
  try {
    if (editing.value) {
      await updateMut.mutateAsync({ id: editing.value.id, payload })
    } else {
      await createMut.mutateAsync(payload)
    }
    dialogOpen.value = false
  } catch (e) {
    alert((e as { message?: string }).message || '儲存失敗')
  }
}

async function quickToggleFeatured(s: Series) {
  try {
    await updateMut.mutateAsync({
      id: s.id,
      payload: {
        name: s.name,
        description: s.description,
        theme_id: s.theme_id,
        is_featured: !s.is_featured,
        sample_cover_image_url: s.sample_cover_image_url,
      },
    })
  } catch (e) {
    alert((e as { message?: string }).message || '更新失敗')
  }
}

async function handleDelete(s: Series) {
  if (!confirm(`刪除系列「${s.name}」？`)) return
  try {
    await deleteMut.mutateAsync(s.id)
  } catch (e) {
    const err = e as { status?: number; message?: string }
    if (err.status === 409) {
      alert('此系列下仍有商品，無法刪除。請先把商品移到其他系列或設為無系列。')
    } else {
      alert(err.message || '刪除失敗')
    }
  }
}
</script>

<template>
  <PageHeader title="商品管理" subtitle="商品 / 系列 / 標籤">
    <template #actions>
      <Button variant="primary" @click="openCreate">
        <Plus :size="14" :stroke-width="1.75" />
        新增系列
      </Button>
    </template>
  </PageHeader>

  <ProductsTabs class="mb-6" />

  <div v-if="isLoading" class="py-12 flex justify-center text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
  </div>

  <div
    v-else-if="!series || series.length === 0"
    class="bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)] py-16 flex flex-col items-center text-center"
  >
    <Layers :size="32" :stroke-width="1.25" class="text-aux-rice-mid mb-3" />
    <p class="text-[13px] text-ink-muted mb-1">尚無系列</p>
    <Button variant="primary" class="mt-4" @click="openCreate">
      <Plus :size="14" :stroke-width="1.75" />
      建立第一個系列
    </Button>
  </div>

  <Card v-else :padded="false">
    <ul>
      <li
        v-for="s in series"
        :key="s.id"
        class="flex items-start gap-4 px-6 py-4 border-b border-line-hairline last:border-0 hover:bg-paper-subtle transition-colors"
      >
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline gap-2 flex-wrap">
            <p class="text-[14px] font-medium text-ink-strong">{{ s.name }}</p>
            <span
              v-if="s.is_featured"
              class="text-[11px] px-1.5 h-[18px] inline-flex items-center gap-0.5 rounded-[var(--radius-xs)] bg-[var(--color-state-warning)]/[0.12] text-state-warning"
              title="精選系列"
            >
              <Star :size="10" :stroke-width="1.75" fill="currentColor" />精選
            </span>
            <span
              v-if="s.theme_name"
              class="text-[11px] px-1.5 h-[18px] inline-flex items-center rounded-[var(--radius-xs)] bg-accent-tint text-ink-strong"
            >
              {{ s.theme_name }}
            </span>
          </div>
          <p v-if="s.description" class="text-[12px] text-ink-muted mt-1">{{ s.description }}</p>
        </div>
        <span v-if="s.product_count !== undefined" class="text-[12px] text-ink-muted font-mono">
          {{ s.product_count }} 商品
        </span>
        <div class="flex items-center gap-1">
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] transition-colors"
            :class="s.is_featured
              ? 'text-state-warning hover:bg-[var(--color-state-warning)]/[0.10]'
              : 'text-ink-muted hover:bg-paper-subtle hover:text-state-warning'"
            :title="s.is_featured ? '取消精選' : '設為精選'"
            @click="quickToggleFeatured(s)"
          >
            <Star :size="14" :stroke-width="1.5" :fill="s.is_featured ? 'currentColor' : 'none'" />
          </button>
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-paper-subtle hover:text-ink-strong transition-colors"
            @click="openEdit(s)"
          >
            <Pencil :size="14" :stroke-width="1.5" />
          </button>
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-[var(--color-state-danger)]/[0.10] hover:text-state-danger transition-colors"
            @click="handleDelete(s)"
          >
            <Trash2 :size="14" :stroke-width="1.5" />
          </button>
        </div>
      </li>
    </ul>
  </Card>

  <Dialog
    :open="dialogOpen"
    :title="editing ? '編輯系列' : '新增系列'"
    @close="dialogOpen = false"
  >
    <div class="space-y-4">
      <div>
        <Label for="s-name">系列名稱</Label>
        <Input id="s-name" v-model="formName" placeholder="例：京都四季" />
      </div>
      <div>
        <Label for="s-desc">說明（選填）</Label>
        <Textarea id="s-desc" v-model="formDesc" :rows="3" />
      </div>
      <div>
        <Label>主題（選填）</Label>
        <ThemePicker v-model="formThemeId" />
      </div>
      <div>
        <label class="flex items-center gap-2 cursor-pointer text-[13px] text-ink-default">
          <input
            type="checkbox"
            v-model="formIsFeatured"
            class="w-[16px] h-[16px] accent-[var(--color-accent)] cursor-pointer"
          />
          <span>設為精選系列（store 端「精選系列」入口會顯示）</span>
        </label>
      </div>
      <div>
        <Label>系列封面（選填，用於 store SeriesDetailPage hero）</Label>
        <ProductCoverUpload v-model="formCover" />
        <p class="text-[11px] text-ink-muted mt-1.5 leading-[1.6]">
          沒設時前端會 fallback 到第一個商品的封面圖。
        </p>
      </div>
    </div>
    <template #footer>
      <Button variant="secondary" @click="dialogOpen = false">取消</Button>
      <Button
        variant="primary"
        :disabled="!formName.trim() || createMut.isPending.value || updateMut.isPending.value"
        @click="submit"
      >
        儲存
      </Button>
    </template>
  </Dialog>
</template>
