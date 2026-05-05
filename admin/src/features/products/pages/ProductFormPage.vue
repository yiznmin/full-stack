<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { Loader2, ChevronLeft, FileText, Image as ImageIcon, Wrench } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Select from '@/shared/ui/Select.vue'
import Button from '@/shared/ui/Button.vue'

import {
  useProductQuery,
  useCreateProductMutation,
  useUpdateProductMutation,
} from '../queries'
import { productSchema, type ProductFormValues } from '../schemas'
import ProductCoverUpload from '../components/ProductCoverUpload.vue'
import SeriesPicker from '../components/SeriesPicker.vue'
import TagsMultiSelect from '../components/TagsMultiSelect.vue'
import ProductVariantsTab from '../components/ProductVariantsTab.vue'
import ProductImagesTab from '../components/ProductImagesTab.vue'
import OrderImpactWarningDialog from '../components/OrderImpactWarningDialog.vue'

const route = useRoute()
const router = useRouter()

const productId = computed(() =>
  typeof route.params.id === 'string' ? route.params.id : undefined,
)
const isCreate = computed(() => !productId.value)

const { data: existing, isLoading: loadingExisting } = useProductQuery(productId)

const createMut = useCreateProductMutation()
const updateMut = useUpdateProductMutation()

// tab 可從 query 帶入（建立商品後 redirect 進來會帶 ?tab=variants）
const initialTab = (typeof route.query.tab === 'string' && ['basic', 'variants', 'images'].includes(route.query.tab))
  ? route.query.tab as 'basic' | 'variants' | 'images'
  : 'basic'
const tab = ref<'basic' | 'variants' | 'images'>(initialTab)
const apiError = ref<string | null>(null)

const { handleSubmit, errors, defineField, setValues, values } = useForm<ProductFormValues>({
  validationSchema: toTypedSchema(productSchema),
  initialValues: {
    title: '',
    description: '',
    cover_image_url: '',
    series_id: null,
    series_order: 0,
    status: 'draft',
    tag_ids: [],
  },
})

const [title, titleAttrs] = defineField('title')
const [description, descriptionAttrs] = defineField('description')
const [coverImageUrl] = defineField('cover_image_url')
const [seriesId] = defineField('series_id')
const [tagIds] = defineField('tag_ids')
const [status] = defineField('status')

watch(existing, (next) => {
  if (next) {
    setValues({
      title: next.title,
      description: next.description ?? '',
      cover_image_url: next.cover_image_url,
      series_id: next.series_id,
      series_order: next.series_order ?? 0,
      status: next.status,
      tag_ids: (next.tags ?? []).map((t) => t.id),
    })
  }
}, { immediate: true })

const statusOptions = [
  { value: 'draft', label: '草稿（前台不顯示）' },
  { value: 'on_sale', label: '上架中' },
  { value: 'off_sale', label: '已下架' },
]

// 進行中訂單警告（只在從 on_sale 切到 off_sale 時觸發）
const warningOpen = ref(false)
const pendingSubmit = ref<(() => void) | null>(null)

async function doSubmit(payload: ProductFormValues) {
  apiError.value = null
  try {
    if (isCreate.value) {
      const created = await createMut.mutateAsync(payload as never)
      // 建立後跳到變體 tab，admin 自己按「新增變體」開 picker（不自動彈窗）
      router.replace(`/admin/products/${created.id}?tab=variants`)
    } else if (productId.value) {
      await updateMut.mutateAsync({ id: productId.value, payload: payload as never })
    }
  } catch (e) {
    const err = e as { status?: number; message?: string }
    apiError.value = err.message || '儲存失敗'
  }
}

const onSubmit = handleSubmit((vals) => {
  // 若由 on_sale 改成 off_sale，先彈警告（暫時不查實際進行中訂單數，只用 status 變化判斷）
  if (existing.value?.status === 'on_sale' && vals.status === 'off_sale') {
    pendingSubmit.value = () => doSubmit(vals)
    warningOpen.value = true
    return
  }
  doSubmit(vals)
})

function confirmWarning() {
  warningOpen.value = false
  pendingSubmit.value?.()
  pendingSubmit.value = null
}
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/products')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回列表
    </button>
  </div>

  <PageHeader
    :title="isCreate ? '新增商品' : '編輯商品'"
    :subtitle="isCreate ? '建立新商品上架' : (existing?.title || '載入中...')"
  >
    <template #actions>
      <Button
        variant="primary"
        :disabled="createMut.isPending.value || updateMut.isPending.value"
        @click="onSubmit"
      >
        <Loader2
          v-if="createMut.isPending.value || updateMut.isPending.value"
          :size="14" :stroke-width="1.5" class="animate-spin"
        />
        {{ isCreate ? '建立商品' : '儲存變更' }}
      </Button>
    </template>
  </PageHeader>

  <!-- Tabs (only show for edit mode; create starts with basic only) -->
  <nav v-if="!isCreate" class="flex items-center gap-1 mb-6 border-b border-line-hairline">
    <button
      v-for="t in [
        { id: 'basic', label: '基本資訊', icon: FileText },
        { id: 'variants', label: '變體', icon: Wrench },
        { id: 'images', label: '圖片', icon: ImageIcon },
      ]"
      :key="t.id"
      type="button"
      class="inline-flex items-center gap-1.5 h-10 px-4 text-[13px] border-b-2 -mb-px transition-colors"
      :class="
        tab === t.id
          ? 'border-accent text-ink-strong font-medium'
          : 'border-transparent text-ink-muted hover:text-ink-strong'
      "
      @click="tab = t.id as 'basic' | 'variants' | 'images'"
    >
      <component :is="t.icon" :size="14" :stroke-width="1.5" />
      {{ t.label }}
    </button>
  </nav>

  <div
    v-if="apiError"
    class="mb-5 px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    {{ apiError }}
  </div>

  <!-- Basic info tab -->
  <div v-if="tab === 'basic'" class="grid grid-cols-1 lg:grid-cols-3 gap-5">
    <!-- Left: text fields -->
    <Card class="lg:col-span-2">
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-5">基本資訊</h2>

      <div class="space-y-5">
        <div>
          <Label for="p-title">商品名稱</Label>
          <Input
            id="p-title"
            v-model="title"
            v-bind="titleAttrs"
            placeholder="例：京都楓葉 30×40"
            :invalid="!!errors.title"
          />
          <p v-if="errors.title" class="mt-1 text-[12px] text-state-danger">{{ errors.title }}</p>
        </div>

        <div>
          <Label for="p-desc">商品描述</Label>
          <Textarea
            id="p-desc"
            v-model="description"
            v-bind="descriptionAttrs"
            :rows="6"
            placeholder="商品介紹、適合擺設情境、繪製注意事項..."
            :invalid="!!errors.description"
            :maxlength="2000"
          />
          <p v-if="errors.description" class="mt-1 text-[12px] text-state-danger">{{ errors.description }}</p>
          <p v-else class="mt-1 text-[11px] text-ink-muted text-right">{{ (description || '').length }} / 2000</p>
        </div>

        <div>
          <Label for="p-status">狀態</Label>
          <Select id="p-status" v-model="status" :options="statusOptions" />
        </div>

        <div>
          <label class="flex items-center gap-2 cursor-pointer text-[13px] text-ink-default">
            <input
              type="checkbox"
              v-model="isFeatured"
              class="w-[16px] h-[16px] accent-[var(--color-accent)] cursor-pointer"
            />
            <span>設為精選商品（store 端「精選商品」入口、系列詳情 Pick 區塊會優先顯示）</span>
          </label>
        </div>
      </div>
    </Card>

    <!-- Right: cover, series, tags -->
    <div class="space-y-5">
      <Card>
        <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">封面圖</h2>
        <ProductCoverUpload
          v-model="coverImageUrl"
          :invalid="!!errors.cover_image_url"
          :product-id="productId"
        />
        <p v-if="errors.cover_image_url" class="mt-2 text-[12px] text-state-danger">
          {{ errors.cover_image_url }}
        </p>
      </Card>

      <Card>
        <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">系列</h2>
        <SeriesPicker v-model="seriesId" />
      </Card>

      <Card>
        <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">標籤</h2>
        <TagsMultiSelect v-model="tagIds" />
      </Card>
    </div>
  </div>

  <!-- Variants tab -->
  <div v-else-if="tab === 'variants' && productId">
    <ProductVariantsTab :product-id="productId" />
  </div>

  <!-- Images tab -->
  <div v-else-if="tab === 'images' && productId">
    <ProductImagesTab :product-id="productId" />
  </div>

  <OrderImpactWarningDialog
    :open="warningOpen"
    @close="warningOpen = false; pendingSubmit = null"
    @confirm="confirmWarning"
  />

  <div v-if="loadingExisting && !isCreate" class="text-ink-muted text-[13px] py-6">
    載入中...
  </div>
</template>
