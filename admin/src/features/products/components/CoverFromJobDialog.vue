<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, Check, ImageOff, AlertTriangle } from 'lucide-vue-next'

import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'

import { useAvailableJobsQuery } from '../queries'
import type { AvailableJob } from '../api'

const props = defineProps<{
  open: boolean
  /** 編輯模式才帶；建立模式不傳，列出所有候選 */
  productId?: string
}>()

const emit = defineEmits<{
  close: []
  /** 選定後吐 preview_url（已是公開 https）給父層當封面 url */
  pick: [url: string]
}>()

const selectedId = ref<string | null>(null)

const {
  data: jobsData,
  isLoading,
  isError,
  error,
  refetch,
} = useAvailableJobsQuery(() => props.productId, () => props.open)

// 必須兩種 URL 都有才能用（preview 顯示縮圖、cover 寫永久欄位）
const jobs = computed<AvailableJob[]>(() =>
  (jobsData.value?.items ?? []).filter((j) => j.preview_url && j.cover_url),
)

watch(() => props.open, (v) => {
  if (v) selectedId.value = null
})

function pickAndClose() {
  const job = jobs.value.find((j) => j.id === selectedId.value)
  // 寫入 cover_image_url 永久欄位 → 必須用 cover_url（Firebase download URL）
  // 不可用 preview_url（15-min signed URL，會在生產環境 401）
  if (job?.cover_url) {
    emit('pick', job.cover_url)
    emit('close')
  }
}

function specSummary(j: AvailableJob): string {
  return `${j.canvas_w_cm}×${j.canvas_h_cm}cm · ${j.detail} · ${j.difficulty}`
}
</script>

<template>
  <Dialog :open="open" title="從製作任務選封面" size="lg" @close="$emit('close')">
    <div class="space-y-4">
      <p class="text-[12px] text-ink-muted">
        從已通過審核的 production_job 挑一張當封面。
        <span class="text-state-success">「實體色」</span>標籤 = 已完成顏色對應、封面用對應後的物理色版本（更接近顏料畫出來的真實色彩）；
        <span class="text-state-warning">「未對應」</span> = 仍是演算法量化色，建議先完成對應再選。
      </p>

      <div v-if="isLoading" class="py-12 flex justify-center text-ink-muted">
        <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
      </div>

      <div
        v-else-if="isError"
        class="py-6 px-4 text-[13px] text-state-danger border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] rounded-[var(--radius-xs)] flex items-start gap-2"
      >
        <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="font-medium">載入清單失敗</p>
          <p class="text-[12px] text-ink-muted mt-1">
            {{ (error as { message?: string })?.message || '請稍後重試' }}
          </p>
        </div>
        <button type="button" class="text-[12px] underline shrink-0" @click="refetch()">
          重試
        </button>
      </div>

      <div v-else-if="jobs.length === 0" class="py-10 text-center text-[13px] text-ink-muted">
        <p class="mb-1">沒有可用的製作任務</p>
        <p class="text-[12px]">需要 approved=true 且 filled_template_url 不為 null</p>
      </div>

      <div v-else class="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[480px] overflow-y-auto pr-1">
        <button
          v-for="j in jobs"
          :key="j.id"
          type="button"
          class="relative aspect-square rounded-[var(--radius-sm)] border-2 overflow-hidden bg-paper-canvas transition-colors text-left"
          :class="
            selectedId === j.id
              ? 'border-accent'
              : 'border-line-hairline hover:border-line-strong'
          "
          @click="selectedId = j.id"
        >
          <img
            v-if="j.preview_url"
            :src="j.preview_url"
            :alt="specSummary(j)"
            class="w-full h-full object-cover"
          />
          <ImageOff v-else :size="20" :stroke-width="1.25" class="absolute inset-0 m-auto text-ink-muted" />
          <span
            v-if="selectedId === j.id"
            class="absolute top-2 right-2 h-6 w-6 inline-flex items-center justify-center rounded-full bg-accent text-paper-surface"
          >
            <Check :size="14" :stroke-width="2.25" />
          </span>
          <!-- finalize badge：已 finalize 的封面用實體色版本，色彩更接近實物 -->
          <span
            v-if="j.is_finalized"
            class="absolute top-2 left-2 px-1.5 py-0.5 text-[10px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-state-success/90 text-paper-surface"
            title="已對應完成 — 封面用實體色版本，與顏料畫出的色彩一致"
          >實體色</span>
          <span
            v-else
            class="absolute top-2 left-2 px-1.5 py-0.5 text-[10px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-state-warning/80 text-paper-surface"
            title="尚未對應完成 — 封面是演算法量化色，與真實顏料可能有色差"
          >未對應</span>
          <span class="absolute bottom-0 inset-x-0 px-2 py-1 text-[11px] text-paper-surface bg-ink-strong/70 truncate">
            {{ specSummary(j) }}
          </span>
        </button>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" @click="$emit('close')">取消</Button>
      <Button variant="primary" :disabled="!selectedId" @click="pickAndClose">
        套用
      </Button>
    </template>
  </Dialog>
</template>
