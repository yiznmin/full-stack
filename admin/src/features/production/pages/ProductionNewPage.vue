<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  Upload,
  Image as ImageIcon,
  Plus,
  Trash2,
  Send,
  Sparkles,
  AlertTriangle,
} from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'
import Select from '@/shared/ui/Select.vue'
import Input from '@/shared/ui/Input.vue'

import { useCreateJobsMutation } from '../queries'
import { validateCombos } from '../utils/validateCombos'
import {
  CANVAS_SIZES,
  DETAIL_LABEL,
  DIFFICULTY_LABEL,
  createImage,
  recommendCanvasSizes,
  requestUploadProductionImage,
  startBatch,
  updateSamMask,
  type CanvasSizeSuggestion,
  type CreateJobsRequest,
  type Detail,
  type Difficulty,
  type Mode,
  type SamPoint,
} from '../api'
import { fetchPhotoSignedUrl, useCustomRequestsQuery } from '@/features/custom_requests/queries'

const route = useRoute()
const router = useRouter()

const createJobsMut = useCreateJobsMutation()

// ── Source ────────────────────────────────────────────────────────────
const source = ref<'image' | 'custom_request'>('image')
const apiError = ref<string | null>(null)

// 上傳
const fileInput = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const uploadedImageId = ref<string | null>(null)
const uploadedImageUrl = ref<string | null>(null)
const uploadedFilename = ref<string | null>(null)
const recommendedSizes = ref<CanvasSizeSuggestion[]>([])

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 20 * 1024 * 1024) {
    apiError.value = '檔案超過 20MB'
    return
  }
  if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
    apiError.value = '只接受 JPEG / PNG'
    return
  }
  apiError.value = null
  isUploading.value = true

  // 用 blob URL 做即時預覽（不依賴 signed URL TTL，上傳成功立即看得到）
  const blobUrl = URL.createObjectURL(file)
  uploadedImageUrl.value = blobUrl
  uploadedFilename.value = file.name

  try {
    // 1) 取 signed URL
    const sign = await requestUploadProductionImage({
      filename: file.name,
      content_type: file.type as 'image/jpeg' | 'image/png',
      size: file.size,
    })

    // 2) PUT 直傳 GCS
    const putRes = await fetch(sign.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type },
      body: file,
    })
    if (!putRes.ok) throw new Error('Firebase 直傳失敗')

    // 3) 讀圖片寬高
    const dims = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const img = new window.Image()
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
      img.onerror = reject
      img.src = blobUrl
    })

    // 4) 落地 metadata（後端需要的 original_url 是 GCS 路徑用簽章 URL，
    // 這裡傳 sign.public_url 給後端記錄；但前端 preview 仍用 blob URL）
    const meta = await createImage({
      original_url: sign.public_url,
      filename: file.name,
      width: dims.width,
      height: dims.height,
    })
    uploadedImageId.value = meta.id

    // 5) 取系統推薦尺寸（依圖片比例從 17 種標準畫布挑 3 個最接近）
    try {
      const rec = await recommendCanvasSizes(dims.width, dims.height, 3)
      recommendedSizes.value = rec.items
      // 自動把第一組組合的 canvas 換成第一個推薦
      if (rec.items.length > 0 && combos.value.length > 0) {
        const top = rec.items[0]
        combos.value[0].canvas_size = `${top.w}x${top.h}`
      }
    } catch {
      // 推薦失敗不阻擋流程
      recommendedSizes.value = []
    }
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '上傳失敗'
    uploadedImageUrl.value = null
    uploadedFilename.value = null
    URL.revokeObjectURL(blobUrl)
  } finally {
    isUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

// 客製申請候選
const customCandidatesQuery = useCustomRequestsQuery(() => ({
  // 只列「未送過報價」的（quote_pending / negotiating / draft_revision）
  // status 篩選後端目前單值，要拿 3 個只能 client filter
  page_size: 100,
}))

const customCandidates = computed(() => {
  const items = customCandidatesQuery.data.value?.items ?? []
  const allowed = new Set(['quote_pending', 'negotiating', 'draft_revision'])
  return items.filter((c) => allowed.has(c.status))
})

const selectedCustomRequestId = ref<string | null>(null)
const selectedCustomRequest = computed(() =>
  customCandidates.value.find((c) => c.id === selectedCustomRequestId.value),
)

// 從 ?customRequestId=xxx 帶入：客製訂單詳情頁的「前往製作」按鈕跳過來時，
// 自動切到客製來源並預選對應申請。客戶填的尺寸/難度會顯示在預覽卡片上，
// admin 可參考後手動設 combo（一張原圖可同時跑多組規格）
const incomingCustomRequestId = (typeof route.query.customRequestId === 'string')
  ? route.query.customRequestId
  : null

if (incomingCustomRequestId) {
  source.value = 'custom_request'
  selectedCustomRequestId.value = incomingCustomRequestId
}

// 選了客製申請就抓 photo signed URL 顯示
const customPhotoUrl = ref<string | null>(null)
const customPhotoLoading = ref(false)
const customPhotoMissing = ref(false)

watch(selectedCustomRequestId, async (id) => {
  customPhotoUrl.value = null
  customPhotoMissing.value = false
  if (!id) return
  customPhotoLoading.value = true
  try {
    const r = await fetchPhotoSignedUrl(id)
    customPhotoUrl.value = r.url
  } catch (e) {
    const err = e as { status?: number }
    if (err.status === 404) customPhotoMissing.value = true
    else apiError.value = (e as { message?: string }).message || '取得照片失敗'
  } finally {
    customPhotoLoading.value = false
  }
})

const customOptions = computed(() => {
  const opts = [{ value: '', label: '— 請選擇客製申請 —' }]
  for (const c of customCandidates.value) {
    opts.push({
      value: c.id,
      label: `#${c.id.slice(0, 8)} · ${c.user_name} · ${c.status === 'quote_pending' ? '等待報價' : c.status === 'negotiating' ? '洽談中' : '需修改'}`,
    })
  }
  return opts
})

// ── 批次組合表 ────────────────────────────────────────────────────────
interface ComboRow {
  canvas_size: string  // 'WxH' 字串
  difficulty: Difficulty
  detail: Detail
  mode: Mode
  /** sam_refine 用：必須 > 0 */
  extra_colors: number
  /** sam_weighted 用：0.5-0.8 */
  weight_ratio: number
}

const combos = ref<ComboRow[]>([
  {
    canvas_size: '30x40',
    difficulty: 'intermediate',
    detail: 'standard',
    mode: 'standard',
    extra_colors: 3,
    weight_ratio: 0.65,
  },
])

const modeOptions: { value: Mode; label: string }[] = [
  { value: 'standard', label: '標準' },
  { value: 'sam_refine', label: 'SAM 細化（subject mask）' },
  { value: 'sam_weighted', label: 'SAM 加權（subject vs bg）' },
]

const hasSamMode = computed(() => combos.value.some((c) => c.mode !== 'standard'))

function addCombo() {
  if (combos.value.length >= 10) {
    apiError.value = '單批最多 10 組'
    return
  }
  const last = combos.value[combos.value.length - 1]
  combos.value.push({ ...last })
}

function removeCombo(idx: number) {
  if (combos.value.length === 1) return
  combos.value.splice(idx, 1)
}

const canvasOptions = CANVAS_SIZES.map((s) => ({
  value: `${s.w}x${s.h}`,
  label: s.label,
}))

const difficultyOptions: { value: Difficulty; label: string }[] = [
  { value: 'beginner', label: DIFFICULTY_LABEL.beginner },
  { value: 'elementary', label: DIFFICULTY_LABEL.elementary },
  { value: 'intermediate', label: DIFFICULTY_LABEL.intermediate },
  { value: 'advanced', label: DIFFICULTY_LABEL.advanced },
]

const detailOptions: { value: Detail; label: string }[] = [
  { value: 'rough', label: DETAIL_LABEL.rough },
  { value: 'standard', label: DETAIL_LABEL.standard },
  { value: 'detailed', label: DETAIL_LABEL.detailed },
  { value: 'premium', label: DETAIL_LABEL.premium },
]

// ── 提交 ──────────────────────────────────────────────────────────────
// 驗證邏輯抽到 utils/validateCombos（給 vitest 測），這裡 wrap 為 reactive computed
const comboValidationError = computed<string | null>(() => validateCombos(combos.value))

const canSubmit = computed(() => {
  if (combos.value.length === 0) return false
  if (source.value === 'image' && !uploadedImageId.value) return false
  if (source.value === 'custom_request' && !selectedCustomRequestId.value) return false
  if (comboValidationError.value) return false
  return true
})

async function submit() {
  if (!canSubmit.value) return
  apiError.value = null

  const payload: CreateJobsRequest = {
    image_id: source.value === 'image' ? uploadedImageId.value : null,
    custom_request_id: source.value === 'custom_request' ? selectedCustomRequestId.value : null,
    jobs: combos.value.map((c) => {
      const [w, h] = c.canvas_size.split('x').map(Number)
      const job: CreateJobsRequest['jobs'][number] = {
        detail: c.detail,
        difficulty: c.difficulty,
        mode: c.mode,
        canvas_w_cm: w,
        canvas_h_cm: h,
      }
      if (c.mode === 'sam_refine') job.extra_colors = c.extra_colors
      if (c.mode === 'sam_weighted') job.weight_ratio = c.weight_ratio
      return job
    }),
  }

  try {
    const res = await createJobsMut.mutateAsync(payload)
    // 任一 SAM mode → 跳第一筆的 mask 編輯頁
    // （v1 spec 要求：先擋多筆 SAM，但若用戶送了多筆，導去第一筆的 mask 編輯頁，
    // 編完啟動批次時 backend 會反映哪些 job 缺 mask；這層邏輯交給 MaskEditPage 處理。）
    if (hasSamMode.value && res.job_ids.length > 0) {
      router.push(`/admin/production/${res.job_ids[0]}/mask`)
    } else if (res.batch_id) {
      router.push(`/admin/production?batch_id=${res.batch_id}`)
    } else {
      router.push(`/admin/production/${res.job_ids[0]}`)
    }
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '建立失敗'
  }
}
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/production')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回任務列表
    </button>
  </div>

  <PageHeader title="新增製作任務" subtitle="上傳圖片或從客製申請帶入照片，設定批次組合" />

  <div
    v-if="apiError"
    class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
  >
    <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5" />
    <span class="flex-1">{{ apiError }}</span>
    <button class="text-[12px] underline" @click="apiError = null">關閉</button>
  </div>

  <div class="space-y-5">
    <!-- Section 1：來源 -->
    <Card>
      <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">1. 來源</h2>

      <div class="flex gap-2 mb-5">
        <button
          type="button"
          class="flex-1 px-4 py-3 border rounded-[var(--radius-xs)] text-[13px] transition-colors"
          :class="source === 'image' ? 'border-accent bg-[var(--color-accent)]/[0.04] text-ink-strong' : 'border-line-hairline text-ink-muted hover:bg-paper-subtle'"
          @click="source = 'image'"
        >
          <ImageIcon :size="16" :stroke-width="1.5" class="inline mr-1.5" />
          上傳新圖片
        </button>
        <button
          type="button"
          class="flex-1 px-4 py-3 border rounded-[var(--radius-xs)] text-[13px] transition-colors"
          :class="source === 'custom_request' ? 'border-accent bg-[var(--color-accent)]/[0.04] text-ink-strong' : 'border-line-hairline text-ink-muted hover:bg-paper-subtle'"
          @click="source = 'custom_request'"
        >
          <Sparkles :size="16" :stroke-width="1.5" class="inline mr-1.5" />
          從客製申請帶入
        </button>
      </div>

      <!-- 上傳 -->
      <div v-if="source === 'image'">
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png"
          class="hidden"
          @change="onFileChange"
        />
        <div
          v-if="!uploadedImageId && !isUploading"
          class="aspect-[4/3] flex flex-col items-center justify-center gap-3 border-2 border-dashed border-line-strong rounded-[var(--radius-sm)] bg-paper-surface text-ink-muted"
        >
          <ImageIcon :size="32" :stroke-width="1.25" />
          <p class="text-[13px]">JPEG / PNG，最大 20MB</p>
          <Button variant="secondary" @click="fileInput?.click()">
            <Upload :size="14" :stroke-width="1.5" />
            選檔上傳
          </Button>
        </div>
        <div
          v-else-if="isUploading"
          class="aspect-[4/3] flex flex-col items-center justify-center gap-2 border border-line-hairline rounded-[var(--radius-sm)] bg-paper-subtle"
        >
          <Loader2 :size="24" :stroke-width="1.5" class="animate-spin text-ink-muted" />
          <span class="text-[13px] text-ink-muted">上傳中...（直傳 Firebase）</span>
        </div>
        <div
          v-else
          class="aspect-[4/3] relative rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-canvas"
        >
          <img
            v-if="uploadedImageUrl"
            :src="uploadedImageUrl"
            alt="已上傳圖片"
            class="w-full h-full object-contain"
          />
          <div class="absolute top-2 left-2 px-2 h-7 inline-flex items-center text-[12px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-state-success/20 text-state-success">
            ✓ 已上傳：{{ uploadedFilename }}
          </div>
          <button
            type="button"
            class="absolute top-2 right-2 h-7 px-2 inline-flex items-center gap-1 text-[12px] rounded-[var(--radius-xs)] bg-paper-surface/90 text-ink-muted hover:text-ink-strong"
            @click="uploadedImageId = null; uploadedImageUrl = null; uploadedFilename = null"
          >
            重新上傳
          </button>
        </div>
      </div>

      <!-- 從客製申請 -->
      <div v-else>
        <div v-if="customCandidatesQuery.isLoading.value" class="py-8 flex justify-center text-ink-muted">
          <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
        </div>
        <div v-else-if="customCandidates.length === 0" class="py-8 text-center text-ink-muted text-[13px]">
          目前沒有「等待報價 / 洽談中 / 需修改」狀態的客製申請。
        </div>
        <div v-else class="space-y-3">
          <Select v-model="selectedCustomRequestId" :options="customOptions" />
          <div
            v-if="selectedCustomRequest"
            class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle text-[13px] space-y-3"
          >
            <div>
              <p class="text-ink-strong font-medium">{{ selectedCustomRequest.user_name }}</p>
              <p class="text-ink-muted text-[12px]">{{ selectedCustomRequest.user_email }}</p>
              <p class="text-[12px] text-ink-default mt-1">
                申請於 {{ new Date(selectedCustomRequest.created_at).toLocaleString('zh-TW') }}
              </p>
            </div>

            <!-- 客製照片預覽 -->
            <div
              class="aspect-[4/3] rounded-[var(--radius-xs)] border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center"
            >
              <Loader2
                v-if="customPhotoLoading"
                :size="24" :stroke-width="1.5"
                class="animate-spin text-ink-muted"
              />
              <img
                v-else-if="customPhotoUrl"
                :src="customPhotoUrl"
                alt="客戶上傳照片"
                class="w-full h-full object-contain"
              />
              <div v-else-if="customPhotoMissing" class="text-center px-4 text-ink-muted">
                <ImageIcon :size="24" :stroke-width="1.25" class="mx-auto mb-1" />
                <p class="text-[12px]">客戶尚未上傳照片</p>
              </div>
              <div v-else class="text-center px-4 text-ink-muted">
                <ImageIcon :size="24" :stroke-width="1.25" class="mx-auto mb-1" />
                <p class="text-[12px]">照片無法顯示</p>
              </div>
            </div>
          </div>
          <p class="text-[12px] text-ink-muted">
            ⚠️ 送出後客製申請會自動轉為「洽談中」（若原為「等待報價」），且申請內容鎖定。
          </p>
        </div>
      </div>
    </Card>

    <!-- Section 2：批次組合 -->
    <Card>
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
          2. 批次組合
          <span class="ml-2 text-[12px] text-ink-muted font-sans">{{ combos.length }} 組</span>
        </h2>
        <Button variant="secondary" :disabled="combos.length >= 10" @click="addCombo">
          <Plus :size="14" :stroke-width="1.5" />
          新增組合
        </Button>
      </div>

      <!-- 系統推薦尺寸（依上傳圖片比例）-->
      <div
        v-if="recommendedSizes.length > 0"
        class="mb-4 p-3 border border-accent/30 bg-[var(--color-accent)]/[0.04] rounded-[var(--radius-xs)]"
      >
        <p class="text-[12px] text-ink-strong mb-2">
          <Sparkles :size="12" :stroke-width="1.5" class="inline mr-1 text-accent" />
          系統推薦尺寸（依圖片比例最接近）— 點選快速套用到所有組合
        </p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="r in recommendedSizes"
            :key="`${r.w}x${r.h}`"
            type="button"
            class="px-3 h-9 inline-flex items-center gap-2 rounded-[var(--radius-xs)] border border-line-strong bg-paper-surface text-[13px] text-ink-default hover:bg-paper-subtle transition-colors"
            @click="combos.forEach((c) => (c.canvas_size = `${r.w}x${r.h}`))"
          >
            <span class="font-mono">{{ r.w }} × {{ r.h }} cm</span>
            <span class="text-[11px] text-ink-muted">{{ Math.round(r.ratio_match * 100) }}% 相符</span>
          </button>
        </div>
      </div>

      <div class="space-y-2">
        <div
          v-for="(c, idx) in combos"
          :key="idx"
          class="border border-line-hairline rounded-[var(--radius-xs)]"
        >
          <div class="grid grid-cols-1 md:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 p-3">
            <div>
              <label class="block text-[11px] text-ink-muted mb-1">畫布尺寸</label>
              <Select v-model="c.canvas_size" :options="canvasOptions" />
            </div>
            <div>
              <label class="block text-[11px] text-ink-muted mb-1">難易度</label>
              <Select v-model="c.difficulty" :options="difficultyOptions" />
            </div>
            <div>
              <label class="block text-[11px] text-ink-muted mb-1">細緻度</label>
              <Select v-model="c.detail" :options="detailOptions" />
            </div>
            <div>
              <label class="block text-[11px] text-ink-muted mb-1">模式</label>
              <Select v-model="c.mode" :options="modeOptions" />
            </div>
            <button
              type="button"
              class="h-9 w-9 mt-[22px] inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:bg-[var(--color-state-danger)]/[0.10] hover:text-state-danger transition-colors disabled:opacity-30"
              :disabled="combos.length === 1"
              aria-label="移除"
              @click="removeCombo(idx)"
            >
              <Trash2 :size="14" :stroke-width="1.5" />
            </button>
          </div>
          <!-- SAM mode 額外欄位 -->
          <div
            v-if="c.mode === 'sam_refine'"
            class="px-3 pb-3 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-2 items-center"
          >
            <label class="text-[12px] text-ink-muted">extra_colors（SAM 區域額外色數）</label>
            <Input
              v-model.number="c.extra_colors"
              type="number"
              min="1"
              max="20"
              placeholder="例如 3"
            />
          </div>
          <div
            v-else-if="c.mode === 'sam_weighted'"
            class="px-3 pb-3 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-2 items-center"
          >
            <label class="text-[12px] text-ink-muted">weight_ratio（subject 權重，0.5–0.8）</label>
            <Input
              v-model.number="c.weight_ratio"
              type="number"
              min="0.5"
              max="0.8"
              step="0.05"
              placeholder="例如 0.65"
            />
          </div>
        </div>
      </div>

      <p class="mt-3 text-[12px] text-ink-muted">
        多組會共用同一個 batch_id，依序進入 Celery 佇列處理（不並發）。任一組失敗 → 後續未跑的組會自動取消。
      </p>
      <p
        v-if="hasSamMode"
        class="mt-2 text-[12px] text-ink-muted bg-[var(--color-accent)]/[0.04] border border-accent/20 px-3 py-2 rounded-[var(--radius-xs)]"
      >
        <Sparkles :size="12" :stroke-width="1.5" class="inline mr-1 text-accent" />
        SAM 模式：送出後會跳到「編輯遮罩」頁，在圖上標出主體（左鍵前景／右鍵背景），標完點「儲存並啟動批次」即進 Celery 處理。
      </p>
      <p
        v-if="comboValidationError"
        class="mt-2 text-[12px] text-state-danger"
      >
        ⚠️ {{ comboValidationError }}
      </p>
    </Card>

    <!-- 送出 -->
    <div class="flex justify-end">
      <Button
        variant="primary"
        :disabled="!canSubmit || createJobsMut.isPending.value"
        @click="submit"
      >
        <Loader2 v-if="createJobsMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
        <Send v-else :size="14" :stroke-width="1.5" />
        送出 {{ combos.length }} 組任務
      </Button>
    </div>
  </div>
</template>
