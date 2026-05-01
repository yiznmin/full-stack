<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, Check, ImageOff, AlertTriangle } from 'lucide-vue-next'

import Dialog from '@/shared/ui/Dialog.vue'
import Input from '@/shared/ui/Input.vue'
import Button from '@/shared/ui/Button.vue'

import { useAddVariantMutation, useAvailableJobsQuery } from '../queries'
import type { AvailableJob } from '../api'

const props = defineProps<{
  open: boolean
  productId: string
}>()

const emit = defineEmits<{
  close: []
  added: []
}>()

// 用 Map 才好保留「選擇順序」與「個別售價」（用 production_job_id 為 key）
const selected = ref<Map<string, number>>(new Map())
const apiError = ref<string | null>(null)
const submitting = ref(false)

const {
  data: jobsData,
  isLoading,
  isError,
  error,
  refetch,
} = useAvailableJobsQuery(() => props.productId, () => props.open)

const jobs = computed<AvailableJob[]>(() => jobsData.value?.items ?? [])

/** 同一張 image_id 的 jobs 分到同一組；image_id=null 各自獨立。 */
const groups = computed(() => {
  const m = new Map<string, AvailableJob[]>()
  for (const j of jobs.value) {
    const key = j.image_id ?? `_solo_${j.id}`
    const arr = m.get(key) ?? []
    arr.push(j)
    m.set(key, arr)
  }
  // 同組內依尺寸由小到大、再依難度排
  for (const arr of m.values()) {
    arr.sort((a, b) =>
      a.canvas_w_cm * a.canvas_h_cm - b.canvas_w_cm * b.canvas_h_cm ||
      a.difficulty.localeCompare(b.difficulty),
    )
  }
  return Array.from(m.values())
})

const selectedCount = computed(() => selected.value.size)

function toggle(job: AvailableJob) {
  const next = new Map(selected.value)
  if (next.has(job.id)) {
    next.delete(job.id)
  } else {
    next.set(job.id, Number(job.price_formula_base))
  }
  selected.value = next
}

function setPrice(jobId: string, value: string) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return
  const next = new Map(selected.value)
  next.set(jobId, n)
  selected.value = next
}

const add = useAddVariantMutation(props.productId)

watch(() => props.open, (v) => {
  if (v) {
    selected.value = new Map()
    apiError.value = null
  }
})

async function submit() {
  if (selected.value.size === 0) return
  apiError.value = null
  submitting.value = true
  try {
    // 逐筆送（後端目前只接單筆）。失敗就停在第一個錯誤。
    for (const [jobId, price] of selected.value) {
      if (price < 1) {
        apiError.value = `售價至少 1 元（job ${jobId.slice(0, 8)}）`
        return
      }
      await add.mutateAsync({ production_job_id: jobId, price })
    }
    emit('added')
    emit('close')
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '加入失敗'
  } finally {
    submitting.value = false
  }
}

function specSummary(j: AvailableJob): string {
  return `${j.canvas_w_cm}×${j.canvas_h_cm}cm · ${j.detail} · ${j.difficulty} · ${j.num_colors_used}色`
}
</script>

<template>
  <Dialog :open="open" title="新增變體" size="xl" @close="$emit('close')">
    <div class="space-y-4">
      <p class="text-[12px] text-ink-muted">
        從已通過審核且尚未綁本商品的 production_job 挑選。同一張原圖的不同規格會分組顯示，可一次勾多個。
      </p>

      <!-- Loading -->
      <div v-if="isLoading" class="py-12 flex justify-center text-ink-muted">
        <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
      </div>

      <!-- Error -->
      <div
        v-else-if="isError"
        class="py-6 px-4 text-[13px] text-state-danger border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] rounded-[var(--radius-xs)] flex items-start gap-2"
      >
        <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="font-medium">載入候選清單失敗</p>
          <p class="text-[12px] text-ink-muted mt-1">
            {{ (error as { message?: string })?.message || '請稍後重試' }}
          </p>
        </div>
        <button type="button" class="text-[12px] underline shrink-0" @click="refetch()">
          重試
        </button>
      </div>

      <!-- Empty -->
      <div v-else-if="jobs.length === 0" class="py-10 text-center text-[13px] text-ink-muted">
        <p class="mb-1">沒有可用的 production_job</p>
        <p class="text-[12px]">
          請先到「製作系統」上傳圖片、跑出 SVG 並 approve；已綁本商品的不會出現。
        </p>
      </div>

      <!-- Picker -->
      <div v-else class="max-h-[480px] overflow-y-auto space-y-4 pr-1">
        <div
          v-for="(group, gi) in groups"
          :key="gi"
          class="rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden"
        >
          <!-- 群組標頭：用第一個 job 的縮圖代表這張原圖 -->
          <div class="px-3 py-2 bg-paper-subtle border-b border-line-hairline flex items-center gap-2">
            <div class="w-8 h-8 rounded border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center shrink-0">
              <img
                v-if="group[0].preview_url"
                :src="group[0].preview_url!"
                alt="原圖"
                class="w-full h-full object-cover"
              />
              <ImageOff v-else :size="14" :stroke-width="1.25" class="text-ink-muted" />
            </div>
            <span class="text-[12px] text-ink-default">
              <span v-if="group[0].image_id">原圖 {{ group[0].image_id.slice(0, 8) }}</span>
              <span v-else class="text-ink-muted italic">獨立任務</span>
              <span class="ml-2 text-ink-muted">{{ group.length }} 個規格</span>
            </span>
          </div>

          <!-- 此原圖底下的每個規格 -->
          <ul class="divide-y divide-line-hairline">
            <li
              v-for="j in group"
              :key="j.id"
              class="px-3 py-2.5 flex items-center gap-3 cursor-pointer hover:bg-paper-canvas transition-colors"
              :class="selected.has(j.id) ? 'bg-accent/[0.04]' : ''"
              @click="toggle(j)"
            >
              <!-- checkbox -->
              <span
                class="w-5 h-5 rounded border-2 inline-flex items-center justify-center shrink-0 transition-colors"
                :class="
                  selected.has(j.id)
                    ? 'border-accent bg-accent text-paper-surface'
                    : 'border-line-strong'
                "
              >
                <Check v-if="selected.has(j.id)" :size="12" :stroke-width="2.5" />
              </span>

              <!-- spec info -->
              <div class="flex-1 min-w-0">
                <p class="text-[13px] text-ink-strong truncate">
                  {{ specSummary(j) }}
                </p>
                <p class="text-[11px] text-ink-muted font-mono mt-0.5">
                  job #{{ j.id.slice(0, 8) }} · 建議價 NT$ {{ Number(j.price_formula_base).toLocaleString() }}
                </p>
              </div>

              <!-- 已勾選後出現售價 input -->
              <div v-if="selected.has(j.id)" class="shrink-0 w-32" @click.stop>
                <Input
                  :model-value="String(selected.get(j.id) ?? '')"
                  type="number"
                  placeholder="售價"
                  @update:model-value="(v) => setPrice(j.id, v)"
                />
              </div>
            </li>
          </ul>
        </div>
      </div>

      <div
        v-if="apiError"
        class="px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
      >
        <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span class="flex-1">{{ apiError }}</span>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="submitting" @click="$emit('close')">取消</Button>
      <Button
        variant="primary"
        :disabled="submitting || selectedCount === 0"
        @click="submit"
      >
        <Loader2 v-if="submitting" :size="14" :stroke-width="1.5" class="animate-spin" />
        加入 {{ selectedCount > 0 ? `${selectedCount} 個變體` : '' }}
      </Button>
    </template>
  </Dialog>
</template>
