<script setup lang="ts">
// 客製照片申請表單（純 form + success state，不含 page chrome）
// 用於 /custom/apply 與 /custom 兩個頁面共用
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  Camera, CheckCircle2, Loader2, Sparkles, Upload, X, Lock,
} from 'lucide-vue-next'
import { useAuthStore } from '@/features/auth/store'
import { useCreateCustomRequestMutation } from '../queries'
import { usePendingFormStorage } from '../composables/usePendingFormStorage'
import { uploadCustomPhoto } from '../upload'
import {
  listCanvasSizes,
  listPhotoPrices,
  DIFFICULTY_LABEL,
} from '../api'
import type {
  CreateCustomRequestPayload, Difficulty, CanvasSize, PhotoPriceRow,
} from '../api'

const props = defineProps<{
  /** 送出後 success state 用的回到首頁路徑（hub 用 /custom，獨立 apply 頁用 /custom/apply 自己） */
  redirectAfter?: 'detail' | 'success-state'
}>()

const PHOTO_MAX_SIZE = 10 * 1024 * 1024
const PHOTO_MAX_SIZE_MB = 10

const router = useRouter()
const auth = useAuthStore()
const createMut = useCreateCustomRequestMutation()
const draft = usePendingFormStorage()

const canvasSizesQuery = useQuery({
  queryKey: ['canvas-sizes'] as const,
  queryFn: listCanvasSizes,
  staleTime: 30 * 60 * 1000,
})
const canvasSizes = computed<CanvasSize[]>(() => canvasSizesQuery.data.value?.items ?? [])

const pricesQuery = useQuery({
  queryKey: ['custom-photo-prices'] as const,
  queryFn: listPhotoPrices,
  staleTime: 30 * 60 * 1000,
})
const photoPrices = computed<PhotoPriceRow[]>(() => pricesQuery.data.value?.items ?? [])

// Form state
const photoUrl = ref<string>('')
const photoPreviewUrl = ref<string>('')
const photoUploading = ref(false)
const photoError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const selectedCanvasId = ref<string | null>(null)
const customCanvasW = ref<number | null>(null)
const customCanvasH = ref<number | null>(null)

const effectiveCanvas = computed<{ w: number; h: number } | null>(() => {
  if (selectedCanvasId.value) {
    const s = canvasSizes.value.find((x) => x.id === selectedCanvasId.value)
    return s ? { w: s.canvas_w_cm, h: s.canvas_h_cm } : null
  }
  if (customCanvasW.value && customCanvasH.value) {
    return { w: customCanvasW.value, h: customCanvasH.value }
  }
  return null
})

const difficulty = ref<Difficulty | null>(null)
const difficultyChoice = ref<Difficulty | 'admin_suggest' | null>(null)
watch(difficultyChoice, (v) => {
  difficulty.value = v === 'admin_suggest' ? null : v
})

const customerNotes = ref<string>('')
const formError = ref<string | null>(null)
const showStashedToast = ref(false)
const submittedRequestId = ref<string | null>(null)
const replyDays = ref<number>(3)

const DIFFICULTIES: Array<{ value: Difficulty | 'admin_suggest'; label: string; hint: string }> = [
  { value: 'beginner', label: DIFFICULTY_LABEL.beginner, hint: '色塊大、好上手' },
  { value: 'elementary', label: DIFFICULTY_LABEL.elementary, hint: '入門再進一級' },
  { value: 'intermediate', label: DIFFICULTY_LABEL.intermediate, hint: '層次更豐富' },
  { value: 'advanced', label: DIFFICULTY_LABEL.advanced, hint: '高細節、考驗耐心' },
  { value: 'admin_suggest', label: '讓管理員建議', hint: '收到照片後幫你推薦' },
]

const priceHint = computed<{ exact?: number; min?: number; max?: number; reason?: string } | null>(() => {
  const c = effectiveCanvas.value
  const prices = photoPrices.value
  if (prices.length === 0) {
    return { reason: '尚未公開定價，送出後管理員會給您正式報價。' }
  }
  if (!c) {
    const all = prices.map((p) => p.price).filter((x): x is number => x != null)
    if (all.length === 0) return null
    return { min: Math.min(...all), max: Math.max(...all), reason: '依尺寸與難度區間。' }
  }
  const matches = prices.filter((p) => p.canvas_w === c.w && p.canvas_h === c.h)
  if (matches.length === 0) {
    return { reason: '此尺寸暫無公開定價，送出後管理員會給您正式報價。' }
  }
  if (difficulty.value) {
    const exact = matches.find((p) => p.difficulty === difficulty.value)
    if (exact?.price) return { exact: exact.price }
  }
  const all = matches.map((p) => p.price).filter((x): x is number => x != null)
  if (all.length === 0) return { reason: '此尺寸暫無公開定價。' }
  return { min: Math.min(...all), max: Math.max(...all) }
})

const formValid = computed(() => !!photoUrl.value)

function matchCanvasIdByDimensions(w: number, h: number): string | null {
  const m = canvasSizes.value.find((s) => s.canvas_w_cm === w && s.canvas_h_cm === h)
  return m ? m.id : null
}

function triggerFile() {
  if (!auth.isLoggedIn) return
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > PHOTO_MAX_SIZE) {
    photoError.value = `檔案超過 ${PHOTO_MAX_SIZE_MB}MB`
    return
  }
  if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
    photoError.value = '只接受 JPEG / PNG'
    return
  }
  photoError.value = null
  photoUploading.value = true
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value)
  photoPreviewUrl.value = URL.createObjectURL(file)
  try {
    const path = await uploadCustomPhoto(file)
    photoUrl.value = path
  } catch (err) {
    photoError.value = (err as Error).message || '上傳失敗'
    photoUrl.value = ''
    URL.revokeObjectURL(photoPreviewUrl.value)
    photoPreviewUrl.value = ''
  } finally {
    photoUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function clearPhoto() {
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value)
  photoUrl.value = ''
  photoPreviewUrl.value = ''
  photoError.value = null
}

function buildPayload(): CreateCustomRequestPayload {
  const c = effectiveCanvas.value
  return {
    request_type: 'custom_photo',
    photo_url: photoUrl.value || null,
    ref_product_id: null,
    canvas_w_cm: c?.w ?? null,
    canvas_h_cm: c?.h ?? null,
    difficulty: difficulty.value,
    detail: null,
    customer_notes: customerNotes.value.trim() || null,
    parent_request_id: null,
  }
}

async function submit() {
  formError.value = null
  if (!auth.isLoggedIn) {
    draft.save({ ...buildPayload(), photo_url: null })
    showStashedToast.value = true
    setTimeout(() => {
      router.push({
        path: '/login',
        query: { redirect: window.location.pathname + '?from=draft' },
      })
    }, 800)
    return
  }
  if (!formValid.value) {
    formError.value = '請先上傳照片'
    return
  }
  try {
    const created = await createMut.mutateAsync(buildPayload())
    submittedRequestId.value = created.id
    setTimeout(() => {
      document.getElementById('success-anchor')?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  } catch (err) {
    formError.value = (err as Error).message || '送出失敗，請稍後再試'
  }
}

async function tryAutoResume() {
  if (!auth.isLoggedIn) return
  const params = new URLSearchParams(window.location.search)
  const from = params.get('from')
  if (from !== 'draft' && from !== 'expired') return
  const saved = draft.load()
  if (!saved) return
  if (saved.canvas_w_cm && saved.canvas_h_cm) {
    const matchedId = matchCanvasIdByDimensions(saved.canvas_w_cm, saved.canvas_h_cm)
    if (matchedId) selectedCanvasId.value = matchedId
    else {
      customCanvasW.value = saved.canvas_w_cm
      customCanvasH.value = saved.canvas_h_cm
    }
  }
  if (saved.difficulty) {
    difficultyChoice.value = saved.difficulty as Difficulty
    difficulty.value = saved.difficulty
  }
  customerNotes.value = saved.customer_notes || ''
  draft.clear()
  formError.value = from === 'expired'
    ? '已套用上次申請的規格與備註，請重新上傳照片。'
    : '已自動回填您的資料，請選擇照片後送出。'
}

function applyQueryPrefill() {
  const params = new URLSearchParams(window.location.search)
  const ref_w = Number(params.get('ref_canvas_w_cm'))
  const ref_h = Number(params.get('ref_canvas_h_cm'))
  const ref_diff = params.get('ref_difficulty')
  const ref_title = params.get('ref_case_title')
  if (ref_w && ref_h && canvasSizes.value.length > 0) {
    const matchedId = matchCanvasIdByDimensions(ref_w, ref_h)
    if (matchedId) selectedCanvasId.value = matchedId
    else {
      customCanvasW.value = ref_w
      customCanvasH.value = ref_h
    }
  }
  if (ref_diff) {
    difficultyChoice.value = ref_diff as Difficulty
    difficulty.value = ref_diff as Difficulty
  }
  if (ref_title && !customerNotes.value) {
    customerNotes.value = `希望做出類似「${ref_title}」風格的作品。`
  }
}

/** 給同頁案例 modal 直接呼叫，不需 URL query 跳轉 */
function applyCaseInspiration(c: { canvas_w_cm?: number | null; canvas_h_cm?: number | null; difficulty?: string | null; title?: string }) {
  if (c.canvas_w_cm && c.canvas_h_cm) {
    const matchedId = matchCanvasIdByDimensions(c.canvas_w_cm, c.canvas_h_cm)
    if (matchedId) selectedCanvasId.value = matchedId
    else {
      customCanvasW.value = c.canvas_w_cm
      customCanvasH.value = c.canvas_h_cm
    }
  }
  if (c.difficulty) {
    difficultyChoice.value = c.difficulty as Difficulty
    difficulty.value = c.difficulty as Difficulty
  }
  if (c.title) {
    customerNotes.value =
      `希望做出類似「${c.title}」風格的作品。\n` +
      (customerNotes.value ? `\n${customerNotes.value}` : '')
  }
}

defineExpose({ applyCaseInspiration })

watch(
  [() => auth.bootstrapped, canvasSizes],
  ([booted, sizes]) => {
    if (booted && sizes.length > 0) {
      tryAutoResume()
      applyQueryPrefill()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value)
})
</script>

<template>
  <div class="apply-form-root">
    <!-- Success state -->
    <div v-if="submittedRequestId" id="success-anchor" class="success-state">
      <CheckCircle2 :size="40" :stroke-width="1.2" class="success-icon" />
      <h3>申請已送出</h3>
      <p>管理員將於 {{ replyDays }} 個工作天內回覆報價。</p>
      <p class="success-hint">您可在「我的申請」頁追蹤進度，新訊息將即時通知。</p>
      <div class="success-actions">
        <RouterLink
          :to="{ name: 'custom-request-detail', params: { id: submittedRequestId } }"
          class="btn-primary"
        >
          查看申請詳情
        </RouterLink>
        <RouterLink to="/custom/requests" class="btn-secondary">
          前往我的申請列表
        </RouterLink>
      </div>

      <div class="next-steps">
        <h4 class="next-title">接下來會發生什麼</h4>
        <ol class="next-list">
          <li>
            <span class="next-no">01</span>
            <div class="next-text">
              <strong>製作初稿與報價</strong>
              <span>1–3 個工作天，完成後 Email + 站內通知</span>
            </div>
          </li>
          <li>
            <span class="next-no">02</span>
            <div class="next-text">
              <strong>確認報價</strong>
              <span>24 小時內回覆，可加入購物車或要求修改</span>
            </div>
          </li>
          <li>
            <span class="next-no">03</span>
            <div class="next-text">
              <strong>製作與出貨</strong>
              <span>付款後 5–10 工作天完成、寄送</span>
            </div>
          </li>
        </ol>
        <RouterLink to="/custom-process" class="next-full">
          看完整訂製流程 →
        </RouterLink>
      </div>
    </div>

    <form v-else class="form" @submit.prevent="submit">
      <!-- Step 1: 照片 -->
      <fieldset class="field">
        <legend class="field-legend">
          <span class="field-no">01</span>上傳您的照片
          <span class="field-required">*</span>
        </legend>
        <p class="field-hint">JPEG / PNG，最大 {{ PHOTO_MAX_SIZE_MB }} MB。建議使用構圖清楚、解析度足夠的照片。</p>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png"
          class="hidden"
          :disabled="!auth.isLoggedIn"
          @change="onFileChange"
        />
        <div v-if="!auth.isLoggedIn" class="photo-empty photo-locked">
          <Lock :size="22" :stroke-width="1.4" class="photo-empty-icon" />
          <p>需登入才能上傳照片</p>
          <p class="photo-empty-hint">您可以先填規格與備註，送出時引導您登入</p>
        </div>
        <div v-else-if="!photoUrl && !photoUploading" class="photo-empty" @click="triggerFile">
          <Camera :size="28" :stroke-width="1.25" class="photo-empty-icon" />
          <p>點擊這裡上傳照片</p>
          <p class="photo-empty-hint">或拖曳到此</p>
        </div>
        <div v-else-if="photoUploading" class="photo-uploading">
          <Loader2 :size="20" class="spin" /> <p>上傳中…</p>
        </div>
        <div v-else class="photo-preview">
          <img :src="photoPreviewUrl" alt="預覽" />
          <button type="button" class="photo-clear" @click="clearPhoto" aria-label="清除照片">
            <X :size="16" />
          </button>
          <button type="button" class="photo-replace" @click="triggerFile">
            <Upload :size="14" :stroke-width="1.5" /> 重新上傳
          </button>
        </div>
        <p v-if="photoError" class="error">{{ photoError }}</p>
      </fieldset>

      <!-- Step 2: 尺寸 -->
      <fieldset class="field">
        <legend class="field-legend">
          <span class="field-no">02</span>畫布尺寸偏好
          <span class="field-optional">（選填）</span>
        </legend>
        <p class="field-hint">未選擇時，管理員將根據照片建議合適的尺寸。</p>
        <div v-if="canvasSizesQuery.isPending.value" class="loading-row">
          <Loader2 :size="14" class="spin" /> 載入尺寸中…
        </div>
        <div v-else class="size-grid">
          <button
            v-for="s in canvasSizes"
            :key="s.id"
            type="button"
            class="size-chip"
            :class="{ active: selectedCanvasId === s.id }"
            @click="selectedCanvasId = (selectedCanvasId === s.id ? null : s.id); customCanvasW = null; customCanvasH = null"
          >
            {{ s.display_name }}
          </button>
        </div>
      </fieldset>

      <!-- Step 3: 難度 -->
      <fieldset class="field">
        <legend class="field-legend">
          <span class="field-no">03</span>難度
          <span class="field-optional">（選填）</span>
        </legend>
        <div class="level-grid">
          <button
            v-for="d in DIFFICULTIES"
            :key="d.value"
            type="button"
            class="level-chip"
            :class="{ active: difficultyChoice === d.value }"
            @click="difficultyChoice = (difficultyChoice === d.value ? null : d.value)"
          >
            <strong>{{ d.label }}</strong>
            <span>{{ d.hint }}</span>
          </button>
        </div>
      </fieldset>

      <!-- 參考價 -->
      <div v-if="priceHint" class="price-hint">
        <Sparkles :size="14" :stroke-width="1.6" />
        <div class="price-hint-text">
          <strong>參考價格：</strong>
          <template v-if="priceHint.exact">NT$ {{ priceHint.exact.toLocaleString() }}</template>
          <template v-else-if="priceHint.min != null && priceHint.max != null">
            NT$ {{ priceHint.min.toLocaleString() }} – {{ priceHint.max.toLocaleString() }}
          </template>
          <template v-else-if="priceHint.reason">{{ priceHint.reason }}</template>
          <p class="price-hint-note" v-if="priceHint.exact || (priceHint.min != null && priceHint.max != null)">
            實際金額由管理員依照片複雜度報價，此為公開參考。
          </p>
        </div>
      </div>

      <!-- Step 4: 備註 -->
      <fieldset class="field">
        <legend class="field-legend">
          <span class="field-no">04</span>給我們的備註
          <span class="field-optional">（選填）</span>
        </legend>
        <p class="field-hint">想保留 / 強化什麼細節？想避免哪些元素？任何特殊需求都可以說。</p>
        <textarea
          v-model="customerNotes"
          rows="4"
          placeholder="例：希望突顯左側人物的笑容，背景簡化為大色塊。"
          class="textarea"
          maxlength="2000"
        ></textarea>
      </fieldset>

      <p v-if="formError" class="info-msg">{{ formError }}</p>

      <div class="submit-row">
        <button type="submit" class="btn-primary" :disabled="createMut.isPending.value">
          <Loader2 v-if="createMut.isPending.value" :size="16" class="spin" />
          <Sparkles v-else :size="16" :stroke-width="1.5" />
          {{ auth.isLoggedIn ? '送出申請' : '送出申請（先登入）' }}
        </button>
        <p class="submit-hint">送出後我們會在 1–3 個工作天內回覆報價，並透過 Email 與站內訊息通知您。</p>
      </div>
    </form>

    <Transition name="toast">
      <div v-if="showStashedToast" class="toast">
        資料已暫存，請登入後自動送出，無需重新填寫
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.apply-form-root { width: 100%; }

.form { display: flex; flex-direction: column; gap: 40px; }
.field { border: 0; padding: 0; margin: 0; }
.field-legend {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-cn-serif); font-weight: 300; font-size: 19px;
  color: var(--color-ink-strong); letter-spacing: 0.04em; margin-bottom: 12px;
}
.field-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; color: var(--color-fresh); padding: 2px 8px; border: 1px solid var(--color-line); border-radius: 2px; }
.field-required { color: var(--color-accent); margin-left: 2px; }
.field-optional { font-family: var(--font-mono); font-size: 10px; color: var(--color-ink-muted); letter-spacing: 0.12em; }
.field-hint { font-size: 13px; color: var(--color-ink-muted); margin: 0 0 16px; letter-spacing: 0.02em; }

.hidden { display: none; }
.loading-row { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-ink-muted); }

.photo-empty {
  border: 1.5px dashed var(--color-line);
  background: var(--color-paper-surface);
  border-radius: var(--radius-sm); aspect-ratio: 4 / 3; max-width: 480px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; cursor: pointer; transition: border-color 150ms, background 150ms;
}
.photo-empty:hover { border-color: var(--color-accent); background: var(--color-paper-deep); }
.photo-empty.photo-locked { cursor: not-allowed; opacity: 0.7; }
.photo-empty.photo-locked:hover { border-color: var(--color-line); background: var(--color-paper-surface); }
.photo-empty p { margin: 0; font-size: 14px; color: var(--color-ink-default); }
.photo-empty-hint { font-size: 12px; color: var(--color-ink-muted); }
.photo-empty-icon { color: var(--color-accent); }

.photo-uploading { display: flex; align-items: center; gap: 12px; padding: 32px; max-width: 480px; background: var(--color-paper-surface); border: 1px solid var(--color-line); border-radius: var(--radius-sm); }
.photo-preview { position: relative; max-width: 480px; border: 1px solid var(--color-line); border-radius: var(--radius-sm); overflow: hidden; }
.photo-preview img { width: 100%; display: block; }
.photo-clear { position: absolute; top: 12px; right: 12px; width: 32px; height: 32px; border: 0; background: rgba(255, 255, 255, 0.92); border-radius: 50%; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; color: var(--color-ink-strong); }
.photo-replace { position: absolute; bottom: 12px; right: 12px; display: inline-flex; align-items: center; gap: 6px; padding: 8px 12px; font-size: 12px; background: rgba(255, 255, 255, 0.92); border: 1px solid var(--color-line); border-radius: var(--radius-xs); cursor: pointer; color: var(--color-ink-strong); }

.size-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
.size-chip, .level-chip { background: transparent; cursor: pointer; padding: 14px 12px; border: 1px solid var(--color-line); border-radius: var(--radius-xs); font-family: inherit; color: var(--color-ink-default); font-size: 14px; transition: border-color 150ms, color 150ms, background 150ms; }
.size-chip:hover, .level-chip:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.size-chip.active, .level-chip.active { border-color: var(--color-accent-deep); background: var(--color-paper-surface); color: var(--color-accent-deep); }
.level-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.level-chip { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; text-align: left; }
.level-chip strong { font-family: var(--font-cn-serif); font-weight: 400; font-size: 15px; }
.level-chip span { font-size: 12px; color: var(--color-ink-muted); }

.price-hint { display: flex; gap: 12px; align-items: flex-start; background: var(--color-paper-surface); border: 1px solid var(--color-line); border-left: 3px solid var(--color-accent); border-radius: var(--radius-xs); padding: 14px 18px; }
.price-hint > svg { color: var(--color-accent); margin-top: 2px; flex-shrink: 0; }
.price-hint-text { flex: 1; font-size: 14px; color: var(--color-ink-default); line-height: 1.6; }
.price-hint-text strong { color: var(--color-accent-deep); }
.price-hint-note { font-size: 11px; color: var(--color-ink-muted); margin: 4px 0 0; font-style: italic; }

.textarea { width: 100%; padding: 12px 14px; font: inherit; font-size: 14px; line-height: 1.7; color: var(--color-ink-default); background: var(--color-paper-surface); border: 1px solid var(--color-line); border-radius: var(--radius-sm); resize: vertical; min-height: 96px; }
.textarea:focus { outline: none; border-color: var(--color-accent); background: var(--color-paper-canvas); }

.error { font-size: 13px; color: var(--color-accent-wine); margin: 8px 0 0; }
.info-msg { padding: 12px 16px; margin: 0; background: var(--color-accent-tint); border: 1px solid var(--color-accent-soft); border-radius: var(--radius-xs); font-size: 13px; color: var(--color-accent-deep); }

.submit-row { display: flex; flex-direction: column; align-items: stretch; gap: 12px; padding-top: 24px; border-top: 1px solid var(--color-line); }
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  align-self: flex-start; padding: 14px 28px; min-width: 200px;
  background: var(--color-accent-deep); color: var(--color-paper-canvas); border: 0; border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 15px; letter-spacing: 0.08em;
  cursor: pointer; transition: background 150ms; text-decoration: none;
}
.btn-primary:hover:not(:disabled) { background: var(--color-accent); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 12px 24px; cursor: pointer; background: transparent;
  color: var(--color-ink-default); border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-family: var(--font-cn-serif);
  font-size: 14px; letter-spacing: 0.06em; text-decoration: none;
}
.btn-secondary:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.submit-hint { font-size: 12px; color: var(--color-ink-muted); margin: 0; }

.success-state { text-align: center; padding: 48px 24px; background: var(--color-paper-surface); border: 1px solid var(--color-line); border-radius: var(--radius-sm); }
.success-icon { color: var(--color-fresh); margin-bottom: 16px; }
.success-state h3 { font-family: var(--font-cn-serif); font-weight: 300; font-size: 28px; letter-spacing: 0.04em; margin: 0 0 12px; color: var(--color-ink-strong); }
.success-state p { margin: 0 0 6px; font-size: 15px; color: var(--color-ink-default); line-height: 1.7; }
.success-hint { font-size: 13px !important; color: var(--color-ink-muted) !important; }
.success-actions { display: flex; gap: 12px; justify-content: center; margin-top: 24px; flex-wrap: wrap; }

.next-steps {
  margin-top: 40px;
  padding-top: 32px;
  border-top: 1px solid var(--color-line-subtle);
  text-align: left;
}
.next-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 18px;
  text-align: center;
}
.next-list {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.next-list li {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.next-no {
  flex-shrink: 0;
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 22px;
  color: var(--color-accent);
  line-height: 1;
  width: 32px;
  text-align: center;
}
.next-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.next-text strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.next-text span {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.next-full {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 2px;
  margin-top: 4px;
}
.next-full:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

.toast { position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%); background: var(--color-accent-deep); color: var(--color-paper-canvas); padding: 14px 24px; border-radius: var(--radius-sm); font-family: var(--font-cn-serif); font-size: 14px; letter-spacing: 0.04em; box-shadow: 0 8px 24px rgba(43, 36, 27, 0.18); z-index: 60; }
.toast-enter-active, .toast-leave-active { transition: opacity 200ms, transform 200ms; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 8px); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
