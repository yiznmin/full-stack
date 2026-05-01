<script setup lang="ts">
import { ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import { Loader2, AlertTriangle, ImageOff } from 'lucide-vue-next'

import type { CopyCandidate } from '../api_mapping'
import { useCopyCandidatesQuery } from '../queries_mapping'

const props = defineProps<{
  open: boolean
  jobId: string
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [sourceJobId: string]
}>()

const selectedId = ref<string | null>(null)

watch(() => props.open, (o) => {
  if (o) selectedId.value = null
})

const { data, isLoading, isError } = useCopyCandidatesQuery(
  () => props.jobId,
  () => props.open,
)

function relationLabel(r: CopyCandidate['relation']): string {
  return r === 'same_batch' ? '同批次' : '同原圖'
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-TW', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function submit() {
  if (selectedId.value) emit('confirm', selectedId.value)
}
</script>

<template>
  <Dialog :open="open" title="從其他 job 複製對應" size="lg" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <p class="text-ink-default">
        系統列出與本 job <strong>同批次</strong>或<strong>同原圖</strong>且已完成顏色對應的 job 供選擇。
      </p>
      <p class="text-[12px] text-ink-muted flex items-start gap-1">
        <AlertTriangle :size="12" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span>複製後仍需手動點「完成對應」才會觸發 required_ml 計算。</span>
      </p>

      <!-- 載入中 -->
      <div v-if="isLoading" class="py-6 text-center text-ink-muted">
        <Loader2 :size="20" :stroke-width="1.5" class="animate-spin inline mr-1" />
        載入候選 job…
      </div>

      <!-- 錯誤 -->
      <p v-else-if="isError" class="text-state-danger text-[12px]">
        載入失敗，請重新開啟對話框
      </p>

      <!-- 空清單 -->
      <p v-else-if="!data || data.items.length === 0" class="py-6 text-center text-ink-muted text-[12px]">
        沒有同批次或同原圖且已完成對應的 job 可供複製。
      </p>

      <!-- 候選清單 -->
      <ul v-else class="space-y-2 max-h-[400px] overflow-auto">
        <li
          v-for="c in data.items"
          :key="c.job_id"
          class="rounded-[var(--radius-sm)] border-2 cursor-pointer transition-all p-2 flex gap-3"
          :class="
            selectedId === c.job_id
              ? 'border-accent bg-accent/5'
              : 'border-line-hairline hover:border-accent/40'
          "
          @click="selectedId = c.job_id"
        >
          <!-- 縮圖 -->
          <div class="w-20 h-20 shrink-0 rounded border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center">
            <img
              v-if="c.filled_template_url"
              :src="c.filled_template_url"
              alt="預覽"
              class="w-full h-full object-cover"
            />
            <ImageOff v-else :size="20" :stroke-width="1.25" class="text-ink-muted" />
          </div>

          <!-- 描述 -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono text-[11px] text-ink-muted">{{ c.job_id.slice(0, 8) }}</span>
              <span class="text-[11px] px-1.5 rounded bg-accent/10 text-accent">
                {{ relationLabel(c.relation) }}
              </span>
            </div>
            <div class="text-[12px] text-ink-default">
              <span>{{ c.canvas_w_cm }}×{{ c.canvas_h_cm }} cm</span>
              <span class="mx-1.5 text-ink-muted">·</span>
              <span>{{ c.detail }} / {{ c.difficulty }}</span>
              <span v-if="c.num_colors_used !== null" class="mx-1.5 text-ink-muted">·</span>
              <span v-if="c.num_colors_used !== null">{{ c.num_colors_used }} 色</span>
            </div>
            <div class="text-[11px] text-ink-muted mt-0.5">
              建立 {{ fmtDate(c.created_at) }}
            </div>
          </div>
        </li>
      </ul>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button
        variant="primary"
        :disabled="pending || !selectedId"
        @click="submit"
      >
        <Loader2 v-if="pending" :size="14" :stroke-width="1.5" class="animate-spin" />
        確認複製
      </Button>
    </template>
  </Dialog>
</template>
