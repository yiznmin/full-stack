<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Plus, Pencil, Trash2, Eye, EyeOff, Loader2, Sparkles,
  Upload, X, Wand2, Camera,
} from 'lucide-vue-next'
import { useQuery } from '@tanstack/vue-query'

import Button from '@/shared/ui/Button.vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import AppDataTable, { type Column } from '@/shared/components/AppDataTable.vue'

import {
  useCaseCategoriesQuery,
  useCreateCaseMutation,
  useCustomCasesQuery,
  useDeleteCaseMutation,
  useToggleCasePublishMutation,
  useUpdateCaseMutation,
} from '../queries'
import {
  DIFFICULTY_LABEL,
  uploadCaseImage,
  listAvailableJobsForCase,
  copyJobImageToCase,
  type CustomCase,
  type Difficulty,
  type AvailableJob,
} from '../api'

const { data, isLoading } = useCustomCasesQuery()
const { data: categoriesData } = useCaseCategoriesQuery()
const createMut = useCreateCaseMutation()
const updateMut = useUpdateCaseMutation()
const toggleMut = useToggleCasePublishMutation()
const deleteMut = useDeleteCaseMutation()

const items = computed(() => data.value?.items ?? [])

const dialogOpen = ref(false)
const editing = ref<CustomCase | null>(null)
const apiError = ref<string | null>(null)

// form fields
// preview_url：本地 blob URL（瞬間可見，避開 Firebase eventual consistency）
// image_url：Firebase 永久 URL（送 backend 用）
// 編輯模式時 preview_url 為空，<img> fallback 用 image_url 直接顯示
const fImages = ref<{ image_url: string; preview_url?: string }[]>([])
const fTitle = ref('')
const fDescription = ref('')
const fCategoryId = ref<string>('')
const fCanvasW = ref('')
const fCanvasH = ref('')
const fDifficulty = ref<string>('')
const fIsPublished = ref(false)

// 圖片上傳狀態
const fileInput = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const uploadError = ref<string | null>(null)

// 紀錄哪些 URL 載失敗（key = url）— 失敗時前端顯示診斷資訊
const brokenImageUrls = ref<Set<string>>(new Set())
function markBroken(url: string) {
  brokenImageUrls.value.add(url)
}
function isBroken(url: string): boolean {
  return brokenImageUrls.value.has(url)
}

// 從 production_job 帶入 dialog
const jobPickerOpen = ref(false)
const jobsQuery = useQuery({
  queryKey: ['available-jobs-for-case'] as const,
  queryFn: listAvailableJobsForCase,
  enabled: jobPickerOpen,
  staleTime: 30 * 1000,
})
const jobs = computed<AvailableJob[]>(() =>
  (jobsQuery.data.value?.items ?? []).filter((j) => j.preview_url && j.cover_url),
)
const selectedJobId = ref<string | null>(null)

function triggerFile() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files || files.length === 0) return

  uploadError.value = null
  isUploading.value = true
  try {
    // 支援一次選多張，按順序 append 到 fImages 後面
    for (const file of Array.from(files)) {
      if (file.size > 20 * 1024 * 1024) {
        uploadError.value = `${file.name} 超過 20MB，已跳過`
        continue
      }
      if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
        uploadError.value = `${file.name} 非 JPEG/PNG，已跳過`
        continue
      }
      // 沿用 production page 模式：blob URL 用於 dialog 內預覽（瞬間可見，
      // 不受 Firebase 傳播延遲影響）；Firebase URL 只用於送 backend。
      const previewUrl = URL.createObjectURL(file)
      const firebaseUrl = await uploadCaseImage(file)
      fImages.value.push({ image_url: firebaseUrl, preview_url: previewUrl })
    }
  } catch (err) {
    uploadError.value = (err as { message?: string }).message || '上傳失敗'
  } finally {
    isUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function removeImage(idx: number) {
  // 釋放 blob URL（避免記憶體洩漏）
  const removed = fImages.value[idx]
  if (removed?.preview_url) URL.revokeObjectURL(removed.preview_url)
  fImages.value.splice(idx, 1)
}

function moveImage(idx: number, dir: -1 | 1) {
  const target = idx + dir
  if (target < 0 || target >= fImages.value.length) return
  const arr = fImages.value
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
}

function openJobPicker() {
  selectedJobId.value = null
  jobPickerOpen.value = true
}

const isCopyingFromJob = ref(false)
async function pickJob() {
  const job = jobs.value.find((j) => j.id === selectedJobId.value)
  if (!job?.cover_url) return

  // production_jobs/** 不公開讀，必須 server-side copy 到 case_images/
  // 才能用作前端 <img> 載入的封面。
  isCopyingFromJob.value = true
  uploadError.value = null
  try {
    const publicUrl = await copyJobImageToCase(job.cover_url)
    // 同時用 preview_url（job picker 顯示時的 signed URL）做瞬間預覽，
    // image_url 用 server-side copy 出來的永久 case_images URL
    fImages.value.push({
      image_url: publicUrl,
      preview_url: job.preview_url || undefined,
    })
    if (!fCanvasW.value) fCanvasW.value = String(job.canvas_w_cm)
    if (!fCanvasH.value) fCanvasH.value = String(job.canvas_h_cm)
    if (!fDifficulty.value) fDifficulty.value = job.difficulty
    jobPickerOpen.value = false
  } catch (err) {
    uploadError.value = (err as { message?: string }).message || '複製失敗'
  } finally {
    isCopyingFromJob.value = false
  }
}

watch(
  [() => dialogOpen.value, () => editing.value],
  () => {
    if (dialogOpen.value) {
      // 開啟前先釋放上一輪 blob URLs（避免重複開關累積）
      for (const img of fImages.value) {
        if (img.preview_url) URL.revokeObjectURL(img.preview_url)
      }
      const e = editing.value
      // 編輯模式：用 backend 回的 images 陣列；建立模式：空
      // 後端有 backfill，舊案例不會出現「沒 images 但有 image_url」的狀況
      if (e?.images && e.images.length > 0) {
        fImages.value = e.images
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((i) => ({ image_url: i.image_url }))
      } else if (e?.image_url) {
        fImages.value = [{ image_url: e.image_url }]
      } else {
        fImages.value = []
      }
      fTitle.value = e?.title ?? ''
      fDescription.value = e?.description ?? ''
      fCategoryId.value = e?.category_id ?? ''
      fCanvasW.value = e?.canvas_w_cm ? String(e.canvas_w_cm) : ''
      fCanvasH.value = e?.canvas_h_cm ? String(e.canvas_h_cm) : ''
      fDifficulty.value = e?.difficulty ?? ''
      fIsPublished.value = e?.is_published ?? false
      apiError.value = null
      uploadError.value = null
    }
  },
)

const categoryOptions = computed(() => [
  { value: '', label: '— 未分類 —' },
  ...(categoriesData.value?.items ?? []).map((c) => ({ value: c.id, label: c.name })),
])

const difficultyOptions = [
  { value: '', label: '— 未指定 —' },
  { value: 'beginner', label: DIFFICULTY_LABEL.beginner },
  { value: 'elementary', label: DIFFICULTY_LABEL.elementary },
  { value: 'intermediate', label: DIFFICULTY_LABEL.intermediate },
  { value: 'advanced', label: DIFFICULTY_LABEL.advanced },
]

function openCreate() {
  editing.value = null
  dialogOpen.value = true
}

function openEdit(c: CustomCase) {
  editing.value = c
  dialogOpen.value = true
}

async function submit() {
  apiError.value = null
  if (fImages.value.length === 0) {
    apiError.value = '至少需要一張圖片'
    return
  }
  if (!fTitle.value.trim()) {
    apiError.value = '標題為必填'
    return
  }
  const payload = {
    title: fTitle.value,
    description: fDescription.value || null,
    category_id: fCategoryId.value || null,
    canvas_w_cm: fCanvasW.value ? Number(fCanvasW.value) : null,
    canvas_h_cm: fCanvasH.value ? Number(fCanvasH.value) : null,
    difficulty: (fDifficulty.value || null) as Difficulty | null,
    is_published: fIsPublished.value,
    // 只送 image_url 給 backend，preview_url 是本地 blob URL 不送
    images: fImages.value.map((i) => ({ image_url: i.image_url })),
  }
  try {
    if (editing.value) {
      await updateMut.mutateAsync({ id: editing.value.id, payload })
    } else {
      await createMut.mutateAsync(payload)
    }
    dialogOpen.value = false
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '儲存失敗'
  }
}

async function togglePublish(c: CustomCase) {
  try {
    await toggleMut.mutateAsync(c.id)
  } catch (e) {
    alert((e as { message?: string }).message || '切換失敗')
  }
}

async function remove(c: CustomCase) {
  if (!confirm(`刪除「${c.title}」？此操作無法復原。`)) return
  try {
    await deleteMut.mutateAsync(c.id)
  } catch (e) {
    alert((e as { message?: string }).message || '刪除失敗')
  }
}

const columns: Column<CustomCase>[] = [
  { key: 'image', label: '預覽', width: '64px' },
  { key: 'title', label: '標題' },
  { key: 'category', label: '分類', width: '110px' },
  { key: 'spec', label: '規格', width: '160px' },
  { key: 'published', label: '上架', width: '80px', align: 'center' },
  { key: 'actions', label: '', width: '120px', align: 'right' },
]

const categoryById = computed(() => {
  const m: Record<string, string> = {}
  for (const c of categoriesData.value?.items ?? []) m[c.id] = c.name
  return m
})
</script>

<template>
  <div class="flex items-center justify-end mb-3">
    <Button variant="primary" @click="openCreate">
      <Plus :size="14" :stroke-width="1.75" />
      新增案例
    </Button>
  </div>

  <AppDataTable
    :columns="columns"
    :rows="items"
    :loading="isLoading"
    :row-key="(r) => r.id"
    empty-text="尚無案例"
    :empty-icon="Sparkles"
  >
    <template #cell-image="{ row }">
      <img
        v-if="row.image_url && !isBroken(row.image_url)"
        :src="row.image_url"
        alt=""
        class="w-12 h-12 object-contain rounded-[var(--radius-xs)] border border-line-hairline bg-paper-surface"
        @error="markBroken(row.image_url)"
      />
      <div
        v-else-if="row.image_url"
        class="w-12 h-12 inline-flex items-center justify-center rounded-[var(--radius-xs)] border border-state-danger/40 bg-[var(--color-state-danger)]/[0.08] text-state-danger text-[10px]"
        :title="row.image_url"
      >
        ⚠
      </div>
    </template>
    <template #cell-title="{ row }">
      <span class="font-medium text-ink-strong">{{ row.title }}</span>
    </template>
    <template #cell-category="{ row }">
      <span class="text-[12px] text-ink-default">
        {{ row.category_id ? categoryById[row.category_id] || '—' : '未分類' }}
      </span>
    </template>
    <template #cell-spec="{ row }">
      <span class="text-[12px] text-ink-muted">
        <span v-if="row.canvas_w_cm">{{ row.canvas_w_cm }}×{{ row.canvas_h_cm }} cm</span>
        <span v-if="row.difficulty"> · {{ DIFFICULTY_LABEL[row.difficulty as Difficulty] }}</span>
      </span>
    </template>
    <template #cell-published="{ row }">
      <button
        type="button"
        class="inline-flex items-center px-2 h-[20px] text-[11px] rounded-[var(--radius-xs)]"
        :class="
          row.is_published
            ? 'bg-[var(--color-state-success)]/[0.10] text-state-success'
            : 'bg-paper-subtle text-ink-muted'
        "
        @click="togglePublish(row)"
      >
        <Eye v-if="row.is_published" :size="11" :stroke-width="1.5" class="mr-1" />
        <EyeOff v-else :size="11" :stroke-width="1.5" class="mr-1" />
        {{ row.is_published ? '上架中' : '下架' }}
      </button>
    </template>
    <template #cell-actions="{ row }">
      <div class="flex items-center justify-end gap-1">
        <button
          type="button"
          class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle"
          @click="openEdit(row)"
        >
          <Pencil :size="14" :stroke-width="1.5" />
        </button>
        <button
          type="button"
          class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-state-danger hover:bg-[var(--color-state-danger)]/[0.10]"
          @click="remove(row)"
        >
          <Trash2 :size="14" :stroke-width="1.5" />
        </button>
      </div>
    </template>
  </AppDataTable>

  <Dialog
    :open="dialogOpen"
    :title="editing ? '編輯案例' : '新增案例'"
    size="lg"
    @close="dialogOpen = false"
  >
    <div class="space-y-4 text-[13px]">
      <p
        v-if="apiError"
        class="px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[12px] rounded-[var(--radius-xs)]"
      >{{ apiError }}</p>

      <div>
        <div class="flex items-center justify-between mb-2">
          <Label>成品圖（拖曳順序，第一張為封面）</Label>
          <span class="text-[11px] text-ink-muted">{{ fImages.length }} 張</span>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png"
          multiple
          class="hidden"
          @change="onFileChange"
        />

        <!-- 圖片網格 -->
        <ul v-if="fImages.length > 0" class="grid grid-cols-3 gap-2 mb-2">
          <li
            v-for="(img, idx) in fImages"
            :key="`${idx}-${img.image_url}`"
            class="relative aspect-[4/3] rounded-[var(--radius-xs)] overflow-hidden border"
            :class="idx === 0 ? 'border-accent-deep ring-1 ring-accent-deep/30' : 'border-line-hairline'"
          >
            <img
              v-if="!isBroken(img.preview_url || img.image_url)"
              :src="img.preview_url || img.image_url"
              :alt="`圖 ${idx + 1}`"
              class="w-full h-full object-contain bg-paper-surface"
              @error="markBroken(img.preview_url || img.image_url)"
            />
            <div
              v-else
              class="w-full h-full bg-[var(--color-state-danger)]/[0.06] flex flex-col items-center justify-center gap-1 p-2"
            >
              <span class="text-[10px] text-state-danger font-medium">⚠ 載入失敗</span>
              <code
                class="text-[8px] text-ink-muted text-center break-all leading-tight"
                :title="img.image_url"
              >{{ img.image_url.length > 50 ? img.image_url.slice(0, 50) + '…' : img.image_url }}</code>
            </div>
            <!-- 封面標記 -->
            <span
              v-if="idx === 0"
              class="absolute top-1.5 left-1.5 text-[9px] tracking-[0.18em] uppercase bg-accent-deep text-paper-canvas px-1.5 py-0.5 rounded"
            >Cover</span>
            <!-- 順序編號 -->
            <span
              v-else
              class="absolute top-1.5 left-1.5 text-[10px] font-mono bg-white/80 text-ink-strong px-1.5 py-0.5 rounded"
            >{{ idx + 1 }}</span>
            <!-- 動作 buttons（hover 才顯示）-->
            <div class="absolute inset-0 bg-ink-strong/0 hover:bg-ink-strong/40 transition-colors group">
              <div class="absolute bottom-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  class="h-6 w-6 inline-flex items-center justify-center rounded bg-white/95 text-ink-strong"
                  :disabled="idx === 0"
                  :class="idx === 0 ? 'opacity-30 cursor-not-allowed' : ''"
                  title="往前"
                  @click="moveImage(idx, -1)"
                >‹</button>
                <button
                  type="button"
                  class="h-6 w-6 inline-flex items-center justify-center rounded bg-white/95 text-ink-strong"
                  :disabled="idx === fImages.length - 1"
                  :class="idx === fImages.length - 1 ? 'opacity-30 cursor-not-allowed' : ''"
                  title="往後"
                  @click="moveImage(idx, 1)"
                >›</button>
                <button
                  type="button"
                  class="h-6 w-6 inline-flex items-center justify-center rounded bg-white/95 text-state-danger"
                  title="刪除"
                  @click="removeImage(idx)"
                >
                  <X :size="12" />
                </button>
              </div>
            </div>
          </li>
        </ul>

        <!-- 空狀態 -->
        <div
          v-else-if="!isUploading"
          class="w-full aspect-[4/3] flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-[var(--radius-sm)] bg-paper-surface text-ink-muted border-line-hairline mb-2"
        >
          <Camera :size="24" :stroke-width="1.25" class="text-ink-muted" />
          <p class="text-[12px]">尚未加入任何圖片</p>
        </div>

        <!-- uploading -->
        <div
          v-if="isUploading"
          class="flex items-center justify-center gap-2 py-3 mb-2 text-[12px] text-ink-muted"
        >
          <Loader2 :size="14" class="animate-spin" /> 上傳中…
        </div>

        <!-- 加圖按鈕列 -->
        <div class="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            class="h-9 px-3 inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] border border-line text-[12px] text-ink-default hover:bg-paper-subtle transition-colors"
            :disabled="isUploading"
            @click="triggerFile"
          >
            <Upload :size="13" :stroke-width="1.5" />
            上傳新圖（可多選）
          </button>
          <button
            type="button"
            class="h-9 px-3 inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] border border-line text-[12px] text-ink-default hover:bg-paper-subtle transition-colors"
            :disabled="isUploading"
            @click="openJobPicker"
          >
            <Wand2 :size="13" :stroke-width="1.5" />
            從製作任務帶入（含規格）
          </button>
        </div>
        <p v-if="uploadError" class="text-[12px] text-state-danger mt-1">{{ uploadError }}</p>
      </div>
      <div>
        <Label>標題</Label>
        <Input v-model="fTitle" />
      </div>
      <div>
        <Label>說明（選填）</Label>
        <Textarea v-model="fDescription" :rows="3" />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <Label>分類</Label>
          <Select v-model="fCategoryId" :options="categoryOptions" />
        </div>
        <div>
          <Label>難易度</Label>
          <Select v-model="fDifficulty" :options="difficultyOptions" />
        </div>
        <div>
          <Label>畫布寬（cm，選填）</Label>
          <Input v-model="fCanvasW" type="number" min="1" />
        </div>
        <div>
          <Label>畫布高（cm，選填）</Label>
          <Input v-model="fCanvasH" type="number" min="1" />
        </div>
      </div>
      <label class="flex items-center gap-2">
        <input v-model="fIsPublished" type="checkbox" />
        <span class="text-ink-strong">立即上架（前台公開顯示）</span>
      </label>
    </div>
    <template #footer>
      <Button
        variant="secondary"
        :disabled="createMut.isPending.value || updateMut.isPending.value"
        @click="dialogOpen = false"
      >取消</Button>
      <Button
        variant="primary"
        :disabled="createMut.isPending.value || updateMut.isPending.value"
        @click="submit"
      >
        <Loader2
          v-if="createMut.isPending.value || updateMut.isPending.value"
          :size="14" :stroke-width="1.5" class="animate-spin"
        />
        {{ editing ? '儲存' : '建立' }}
      </Button>
    </template>
  </Dialog>

  <!-- 從 production_job 帶入 -->
  <Dialog
    :open="jobPickerOpen"
    title="從製作任務帶入規格 + 封面"
    size="lg"
    @close="jobPickerOpen = false"
  >
    <div class="space-y-3">
      <p class="text-[12px] text-ink-muted">
        選一筆已完成的 production_job，自動帶入畫布尺寸、難度，並用該 job 產出圖當案例封面。
      </p>
      <div v-if="jobsQuery.isPending.value" class="py-12 text-center text-ink-muted text-[13px]">
        <Loader2 :size="16" class="inline-block animate-spin mr-1" /> 載入中…
      </div>
      <div v-else-if="jobs.length === 0" class="py-12 text-center text-ink-muted text-[13px]">
        目前沒有可選的 job（需 approved + 有產出圖）
      </div>
      <ul v-else class="grid grid-cols-3 gap-3 max-h-[480px] overflow-y-auto">
        <li
          v-for="j in jobs"
          :key="j.id"
          class="border rounded-[var(--radius-sm)] overflow-hidden cursor-pointer transition-colors"
          :class="selectedJobId === j.id ? 'border-accent-deep' : 'border-line-hairline hover:border-line'"
          @click="selectedJobId = j.id"
        >
          <div class="aspect-[4/3] bg-paper-subtle">
            <img v-if="j.preview_url" :src="j.preview_url" :alt="`job ${j.id}`" class="w-full h-full object-contain" />
          </div>
          <div class="p-2 text-[11px]">
            <div class="text-ink-strong">{{ j.canvas_w_cm }}×{{ j.canvas_h_cm }} cm</div>
            <div class="text-ink-muted">
              {{ DIFFICULTY_LABEL[j.difficulty as Difficulty] }} · {{ j.num_colors_used }} 色
            </div>
          </div>
        </li>
      </ul>
    </div>
    <template #footer>
      <Button
        variant="secondary"
        :disabled="isCopyingFromJob"
        @click="jobPickerOpen = false"
      >取消</Button>
      <Button
        variant="primary"
        :disabled="!selectedJobId || isCopyingFromJob"
        @click="pickJob"
      >
        <Loader2 v-if="isCopyingFromJob" :size="14" :stroke-width="1.5" class="animate-spin" />
        {{ isCopyingFromJob ? '複製到公開區…' : '套用此 job' }}
      </Button>
    </template>
  </Dialog>
</template>
