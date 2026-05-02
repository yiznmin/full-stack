<script setup lang="ts">
/**
 * MaskEditPage — 路由 /admin/production/jobs/:id/mask
 *
 * 規格依據：
 *   admin_production.md §1.3（兩種選取模式 / 即時預覽 / 撤銷+清除+確認）
 *   04c_production_sam.md §C（debounce 300ms 即時送 sam-mask；確認 = 啟動批次）
 *
 * 流程：
 *   1. 進頁面 → useJobQuery 拉 job + 載入原圖
 *   2. 使用者點 sam_points / polygons → debounce 300ms → POST /sam-mask
 *   3. mask_url 變更 → MaskCanvas 顯示 overlay
 *   4. 「儲存並啟動批次」→ 最後送一次 sam-mask（含進行中 polygon 自動閉合）→ POST /batches/{batch_id}/start
 *
 * 編輯時機：status=pending 才能編輯，其他狀態 isLocked=true（rendering 仍在，但禁用互動）。
 *
 * 鍵盤快捷鍵：
 *   Ctrl+Z 撤銷（含刪除 marker、清除全部 — 都可還原）
 *   Esc 取消當前進行中多邊形
 *   V / P 切換工具
 *   按住 H 暫時隱藏遮罩
 *   +/− 縮放 · 0/1 重置
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, AlertTriangle, Loader2 } from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'

import MaskCanvas from '../components/MaskCanvas.vue'
import MaskToolbar, { type MaskTool } from '../components/MaskToolbar.vue'
import { useMaskActions } from '../composables/useMaskActions'
import { useJobQuery, useStartBatchMutation } from '../queries'
import { getJobSignedUrl, type SamPoint } from '../api'

const route = useRoute()
const router = useRouter()

const jobId = computed(() => String(route.params.jobId))

const jobQuery = useJobQuery(jobId)
const job = computed(() => jobQuery.data.value)

const isLocked = computed(() => job.value?.status !== 'pending')

const samMode = computed<'sam_refine' | 'sam_weighted' | null>(() => {
  const m = job.value?.mode
  if (m === 'sam_refine' || m === 'sam_weighted') return m
  return null
})

// ── 圖片 URL ─────────────────────────────────────────────────────────
const imageDisplayUrl = ref<string | null>(null)
const imageLoadError = ref<string | null>(null)
const imageWidth = ref<number>(0)
const imageHeight = ref<number>(0)

watch(job, async (j) => {
  if (!j || imageDisplayUrl.value) return
  try {
    const resp = await getJobSignedUrl(j.id, 'image')
    if (resp.url) {
      imageDisplayUrl.value = resp.url
      await loadImageDims(resp.url)
    } else {
      imageLoadError.value = '無法取得原圖（image signed URL 為空）'
    }
  } catch (e) {
    imageLoadError.value = (e as { message?: string }).message || '無法取得原圖'
  }
}, { immediate: true })

async function loadImageDims(url: string) {
  return new Promise<void>((resolve, reject) => {
    const img = new window.Image()
    img.onload = () => {
      imageWidth.value = img.naturalWidth
      imageHeight.value = img.naturalHeight
      resolve()
    }
    img.onerror = () => reject(new Error('圖片載入失敗'))
    img.src = url
  })
}

// ── 編輯狀態 — actionStack 邏輯抽到 useMaskActions composable（可被 vitest 測試）───
const tool = ref<MaskTool>('sam')

// onChange callback：所有 commit 動作（addSam / closePolygon / delete / undo）後觸發
// debounce 送 sam-mask（triggerSamMask 在下方定義，這裡只引用）
const actions = useMaskActions({ onChange: () => triggerSamMask() })
const {
  samPoints,
  polygons,
  currentPolygon,
  canUndo,
  addSamPoint,
  addPolygonVertex,
  closePolygon,
  deleteSamPoint,
  deletePolygon,
  undo,
  cancelCurrentPolygon,
} = actions

// clearAll 額外要清 maskUrl（composable 不知道有 mask URL 概念）
function clearAll() {
  actions.clearAll()
  maskUrl.value = null
}

const canConfirm = computed(() => {
  if (isLocked.value) return false
  // 至少有一個 sam_point、一個閉合 polygon、或任何進行中頂點
  // 進行中頂點 < 3 時 confirm() 會跳警告；≥ 3 時會自動閉合
  return (
    samPoints.value.length > 0 ||
    polygons.value.length > 0 ||
    currentPolygon.value.length > 0
  )
})

// 從 server hydrate 既有狀態（只一次，避免 clearAll 後被自動覆蓋）
const hasHydrated = ref(false)
watch(job, (j) => {
  if (!j || hasHydrated.value) return
  const anyJ = j as unknown as {
    sam_points?: SamPoint[]
    polygons?: number[][][]
    mask_url?: string | null
  }
  actions.hydrate({ samPoints: anyJ.sam_points, polygons: anyJ.polygons })
  if (anyJ.mask_url) maskUrl.value = anyJ.mask_url
  hasHydrated.value = true
}, { immediate: true })

// ── 送 sam-mask（debounce 300ms）────────────────────────────────────
const maskUrl = ref<string | null>(null)
const samMaskInflight = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function triggerSamMask() {
  if (!samMode.value) return
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    if (samPoints.value.length === 0 && polygons.value.length === 0) {
      maskUrl.value = null
      return
    }
    samMaskInflight.value = true
    try {
      const { updateSamMask } = await import('../api')
      const resp = await updateSamMask(jobId.value, {
        sam_points: samPoints.value.length ? samPoints.value : undefined,
        polygons: polygons.value.length ? polygons.value : undefined,
        mode: samMode.value!,
      })
      maskUrl.value = resp.mask_url
    } catch (e) {
      apiError.value = `更新 mask 失敗：${(e as { message?: string }).message || ''}`
    } finally {
      samMaskInflight.value = false
    }
  }, 300)
}

// ── confirm + start batch ────────────────────────────────────────────
const startBatchMut = useStartBatchMutation()
const apiError = ref<string | null>(null)

async function confirm() {
  if (!job.value?.batch_id) {
    apiError.value = '此 job 沒有 batch_id，無法啟動'
    return
  }
  // 進行中 polygon 處理：≥ 3 自動閉合；< 3 警告且擋下
  if (currentPolygon.value.length > 0) {
    if (currentPolygon.value.length >= 3) {
      closePolygon()
    } else {
      apiError.value = `進行中的多邊形只有 ${currentPolygon.value.length} 點（需 ≥ 3 才能閉合）。請先 Esc 取消或繼續加點。`
      return
    }
  }
  // flush debounce
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (!isLocked.value && (samPoints.value.length > 0 || polygons.value.length > 0)) {
    try {
      const { updateSamMask } = await import('../api')
      await updateSamMask(jobId.value, {
        sam_points: samPoints.value.length ? samPoints.value : undefined,
        polygons: polygons.value.length ? polygons.value : undefined,
        mode: samMode.value!,
      })
    } catch (e) {
      apiError.value = `儲存 mask 失敗：${(e as { message?: string }).message || ''}`
      return
    }
  }
  try {
    const result = await startBatchMut.mutateAsync(job.value.batch_id)
    if (result.skipped.length > 0) {
      apiError.value = `部分 job 未啟動：${result.skipped.map((s) => s.reason).join('、')}`
    }
    router.push(`/admin/production?batch_id=${job.value.batch_id}`)
  } catch (e) {
    apiError.value = `啟動批次失敗：${(e as { message?: string }).message || ''}`
  }
}

// ── 隱藏遮罩（toolbar 切的持久 + H 按住的暫時）────────────────────
const hideMaskToggle = ref(false)
const hideMaskHold = ref(false)
const hideMask = computed(() => hideMaskToggle.value || hideMaskHold.value)

// ── canvas methods（透過 ref 呼叫 zoom / reset）────────────────────
const canvasRef = ref<InstanceType<typeof MaskCanvas> | null>(null)

function onZoomIn() { canvasRef.value?.zoomIn() }
function onZoomOut() { canvasRef.value?.zoomOut() }
function onResetView() { canvasRef.value?.resetView() }

// ── 鍵盤快捷鍵 ────────────────────────────────────────────────────
function isInputFocused(): boolean {
  const el = document.activeElement as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

function onKeyDown(e: KeyboardEvent) {
  if (isInputFocused()) return
  // Ctrl/Cmd + Z → undo
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
    e.preventDefault()
    if (canUndo.value && !isLocked.value) undo()
    return
  }
  if (e.key === 'Escape') {
    if (currentPolygon.value.length > 0) {
      e.preventDefault()
      cancelCurrentPolygon()
    }
    return
  }
  if (e.key === 'h' || e.key === 'H') {
    hideMaskHold.value = true
    return
  }
  if (e.key === 'v' || e.key === 'V') {
    if (!isLocked.value) tool.value = 'sam'
    return
  }
  if (e.key === 'p' || e.key === 'P') {
    if (!isLocked.value) tool.value = 'polygon'
    return
  }
  if (e.key === '0' || e.key === '1') {
    onResetView()
    return
  }
  if (e.key === '+' || e.key === '=') {
    onZoomIn()
    return
  }
  if (e.key === '-' || e.key === '_') {
    onZoomOut()
    return
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (e.key === 'h' || e.key === 'H') {
    hideMaskHold.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
})
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push(`/admin/production/${jobId}`)"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回任務詳情
    </button>
  </div>

  <PageHeader
    title="編輯遮罩"
    :subtitle="`mode = ${samMode || '—'}，${isLocked ? '已鎖定（status ≠ pending）' : '可編輯'}`"
  />

  <div
    v-if="apiError"
    class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
  >
    <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5" />
    <span class="flex-1">{{ apiError }}</span>
    <button class="text-[12px] underline" @click="apiError = null">關閉</button>
  </div>

  <Card>
    <div v-if="jobQuery.isLoading.value" class="text-center text-ink-muted py-12">
      <Loader2 :size="20" :stroke-width="1.5" class="inline animate-spin mr-2" />
      載入任務資料 ...
    </div>

    <div v-else-if="jobQuery.error.value" class="text-center text-state-danger py-12">
      載入失敗：{{ (jobQuery.error.value as { message?: string }).message }}
    </div>

    <div v-else-if="!samMode" class="text-center text-ink-muted py-12">
      此 job 不是 SAM 模式（mode = {{ job?.mode }}），無需編輯遮罩。
    </div>

    <div v-else>
      <MaskToolbar
        v-model:tool="tool"
        :hide-mask="hideMask"
        :has-mask="!!maskUrl"
        :can-undo="canUndo"
        :can-confirm="canConfirm"
        :is-locked="isLocked || startBatchMut.isPending.value"
        @undo="undo"
        @clear="clearAll"
        @confirm="confirm"
        @zoom-in="onZoomIn"
        @zoom-out="onZoomOut"
        @reset-view="onResetView"
        @update:hide-mask="(v) => (hideMaskToggle = v)"
      />

      <div>
        <div v-if="imageLoadError" class="text-state-danger py-12 text-center">
          {{ imageLoadError }}
        </div>
        <div
          v-else-if="!imageDisplayUrl || imageWidth === 0"
          class="text-ink-muted py-12 text-center"
        >
          <Loader2 :size="20" :stroke-width="1.5" class="inline animate-spin mr-2" />
          載入圖片 ...
        </div>
        <MaskCanvas
          v-else
          ref="canvasRef"
          :image-url="imageDisplayUrl"
          :image-width="imageWidth"
          :image-height="imageHeight"
          :tool="tool"
          :sam-points="samPoints"
          :polygons="polygons"
          :current-polygon="currentPolygon"
          :mask-url="maskUrl"
          :is-locked="isLocked"
          :hide-mask="hideMask"
          :inflight="samMaskInflight"
          @add-sam-point="addSamPoint"
          @add-polygon-vertex="addPolygonVertex"
          @close-polygon="closePolygon"
          @delete-sam-point="deleteSamPoint"
          @delete-polygon="deletePolygon"
        />
      </div>

      <div class="mt-3 flex items-center gap-3 text-[12px] text-ink-muted flex-wrap">
        <span>SAM 點：{{ samPoints.length }}</span>
        <span class="text-line-strong">|</span>
        <span>多邊形：{{ polygons.length }}（進行中 {{ currentPolygon.length }} 點）</span>
        <span
          v-if="currentPolygon.length > 0 && currentPolygon.length < 3"
          class="text-state-warning"
        >
          ⚠ 進行中多邊形 &lt; 3 點，無法閉合（Esc 可取消）
        </span>
        <span class="text-line-strong">|</span>
        <span v-if="maskUrl" class="text-state-success">已生成 mask</span>
        <span v-else class="text-ink-muted/70">尚未生成 mask</span>
      </div>
    </div>
  </Card>
</template>
