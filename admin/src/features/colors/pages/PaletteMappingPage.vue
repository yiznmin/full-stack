<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  CheckCircle2,
  Copy,
  AlertTriangle,
  Sparkles,
} from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'

import {
  useCompleteMappingsMutation,
  useCopyMappingsMutation,
  usePaletteMappingsQuery,
  useUpdateMappingMutation,
} from '../queries_mapping'
import { rgbToHex } from '../api'
import type { PaletteMapping } from '../api_mapping'

import PhysicalColorPickerDialog from '../components/PhysicalColorPickerDialog.vue'
import CopyMappingsDialog from '../components/CopyMappingsDialog.vue'
import PalettePreviewCanvas from '../components/PalettePreviewCanvas.vue'

import { useJobQuery } from '@/features/production/queries'

const route = useRoute()
const router = useRouter()

const jobId = computed(() => (typeof route.params.jobId === 'string' ? route.params.jobId : ''))

const { data, isLoading, isError, error } = usePaletteMappingsQuery(jobId)
const updateMut = useUpdateMappingMutation(jobId.value)
const copyMut = useCopyMappingsMutation(jobId.value)
const completeMut = useCompleteMappingsMutation(jobId.value)

const mappings = computed(() => data.value?.mappings ?? [])

// 抓 filled_template_url 給 canvas 預覽用
const { data: jobData } = useJobQuery(jobId)
const filledTemplateUrl = computed(() => jobData.value?.filled_template_url ?? null)

function onCanvasPick(templateId: number) {
  const m = mappings.value.find((x) => x.template_id === templateId)
  if (m) openPicker(m)
}

const apiError = ref<string | null>(null)
const completeResult = ref<{
  all_stocked: boolean
  shortage_colors: { template_id: number; physical_color_id: string; code: string; name: string }[]
} | null>(null)

// ── Picker dialog ─────────────────────────────────────────────────────
const pickerOpen = ref(false)
const pickerMapping = ref<PaletteMapping | null>(null)

function openPicker(m: PaletteMapping) {
  pickerMapping.value = m
  pickerOpen.value = true
}

async function onPickPhysicalColor(physicalColorId: string) {
  if (!pickerMapping.value) return
  apiError.value = null
  try {
    await updateMut.mutateAsync({
      templateId: pickerMapping.value.template_id,
      physicalColorId,
    })
    pickerOpen.value = false
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '更新對應失敗'
  }
}

// ── Copy dialog ───────────────────────────────────────────────────────
const copyOpen = ref(false)

async function onConfirmCopy(sourceJobId: string) {
  apiError.value = null
  try {
    await copyMut.mutateAsync(sourceJobId)
    copyOpen.value = false
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '複製失敗'
  }
}

// ── Complete ──────────────────────────────────────────────────────────
const allMapped = computed(
  () => mappings.value.length > 0 && mappings.value.every((m) => m.physical_color),
)

async function complete() {
  apiError.value = null
  completeResult.value = null
  try {
    const r = await completeMut.mutateAsync()
    completeResult.value = r
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '完成對應失敗'
  }
}
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push(`/admin/production/${jobId}`)"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回製作詳情
    </button>
  </div>

  <header class="mb-7 pb-5 border-b border-line-hairline flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
    <div>
      <h1 class="font-display text-ink-strong text-[24px] leading-[32px]">
        顏色對應工作台
        <span class="ml-2 font-mono text-[18px] text-ink-muted">#{{ jobId.slice(0, 8) }}</span>
      </h1>
      <p class="mt-1 text-[13px] text-ink-muted">
        把演算法產出的調色盤對應到實體色（60 色色盤）
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2 shrink-0">
      <Button variant="secondary" @click="copyOpen = true">
        <Copy :size="14" :stroke-width="1.5" />
        從其他 job 複製
      </Button>
      <Button
        variant="primary"
        :disabled="completeMut.isPending.value || !allMapped"
        @click="complete"
      >
        <Loader2 v-if="completeMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
        <CheckCircle2 v-else :size="14" :stroke-width="1.5" />
        完成對應（{{ mappings.filter((m) => m.physical_color).length }} / {{ mappings.length }}）
      </Button>
    </div>
  </header>

  <div
    v-if="apiError"
    class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
  >
    <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5" />
    <span class="flex-1">{{ apiError }}</span>
    <button class="text-[12px] underline" @click="apiError = null">關閉</button>
  </div>

  <div
    v-if="completeResult"
    class="mb-5 p-4 border rounded-[var(--radius-xs)]"
    :class="
      completeResult.all_stocked
        ? 'border-state-success/40 bg-[var(--color-state-success)]/[0.06] text-state-success'
        : 'border-state-warning/40 bg-[var(--color-state-warning)]/[0.06] text-state-warning'
    "
  >
    <p v-if="completeResult.all_stocked" class="text-[13px] flex items-center gap-2">
      <CheckCircle2 :size="14" :stroke-width="1.5" />
      <span>對應完成、所有顏色庫存充足，可進入商品上架流程。</span>
    </p>
    <div v-else>
      <p class="text-[13px] flex items-center gap-2">
        <AlertTriangle :size="14" :stroke-width="1.5" />
        <span>
          對應完成，但 {{ completeResult.shortage_colors.length }} 色庫存不足。
          商品可上架，前台會顯示「預購」狀態。
        </span>
      </p>
      <ul class="mt-2 text-[12px] space-y-0.5">
        <li v-for="s in completeResult.shortage_colors" :key="s.physical_color_id">
          · 色號 {{ s.code }} {{ s.name }}（template #{{ s.template_id }}）
        </li>
      </ul>
    </div>
  </div>

  <div v-if="isLoading" class="py-20 flex justify-center text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
  </div>

  <div
    v-else-if="isError"
    class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗：{{ (error as { message?: string })?.message ?? '未知錯誤' }}
  </div>

  <Card v-else-if="mappings.length === 0" class="text-center py-12">
    <Sparkles :size="32" :stroke-width="1.25" class="mx-auto mb-3 text-aux-rice-mid" />
    <p class="text-[13px] text-ink-muted">此 job 尚無調色盤資料（製作未完成？）</p>
  </Card>

  <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-5">
    <!-- 左：canvas 預覽 -->
    <Card>
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-3">即時預覽</h2>
      <PalettePreviewCanvas
        :image-url="filledTemplateUrl"
        :mappings="mappings"
        @pick-template="onCanvasPick"
      />
    </Card>

    <!-- 右：調色盤對應表 -->
    <Card>
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">
        調色盤
        <span class="ml-2 text-[12px] text-ink-muted font-sans">{{ mappings.length }} 色</span>
      </h2>
      <div class="space-y-2 max-h-[600px] overflow-y-auto">
        <div
          v-for="m in mappings"
          :key="m.template_id"
          class="p-3 border border-line-hairline rounded-[var(--radius-xs)] flex items-center gap-3 cursor-pointer hover:bg-paper-subtle transition-colors"
          @click="openPicker(m)"
        >
          <div class="text-center shrink-0">
            <div
              class="w-10 h-10 rounded-[var(--radius-xs)] border border-line-hairline"
              :style="{ backgroundColor: rgbToHex(m.algorithm_rgb) }"
            />
            <p class="mt-1 text-[10px] text-ink-muted">#{{ m.template_id }}</p>
          </div>

          <span class="text-ink-muted text-[12px] shrink-0">→</span>

          <div v-if="m.physical_color" class="flex-1 min-w-0 flex items-center gap-2">
            <div
              class="w-10 h-10 rounded-[var(--radius-xs)] border border-line-hairline shrink-0"
              :style="{ backgroundColor: rgbToHex(m.physical_color.rgb) }"
            />
            <div class="flex-1 min-w-0">
              <p class="text-[12px] font-mono text-ink-strong">
                {{ m.physical_color.code }}
                <span
                  v-if="m.mapped_by === 'system'"
                  class="ml-1 text-[10px] text-ink-muted"
                >（自動）</span>
              </p>
              <p class="text-[12px] text-ink-default truncate">{{ m.physical_color.name }}</p>
              <p class="text-[10px]" :class="m.physical_color.stock_ml === 0 ? 'text-state-danger' : 'text-ink-muted'">
                庫存 {{ m.physical_color.stock_ml }} ml
                <span v-if="m.required_ml"> · 需 {{ m.required_ml }} ml</span>
              </p>
            </div>
          </div>
          <div v-else class="flex-1 text-[12px] text-state-warning">尚未對應</div>
        </div>
      </div>
    </Card>
  </div>

  <!-- Dialogs -->
  <PhysicalColorPickerDialog
    v-if="pickerMapping"
    :open="pickerOpen"
    :algorithm-rgb="pickerMapping.algorithm_rgb"
    :current-id="pickerMapping.physical_color?.id ?? null"
    @close="pickerOpen = false"
    @pick="onPickPhysicalColor"
  />

  <CopyMappingsDialog
    :open="copyOpen"
    :job-id="jobId"
    :pending="copyMut.isPending.value"
    @close="copyOpen = false"
    @confirm="onConfirmCopy"
  />
</template>
