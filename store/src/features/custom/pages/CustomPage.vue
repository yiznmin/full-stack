<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  Camera,
  CheckCircle2,
  ImagePlus,
  Loader2,
  MessageSquare,
  Palette,
  Sparkles,
  Upload,
  X,
  Lock,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { useAuthStore } from '@/features/auth/store'
import {
  useCreateCustomRequestMutation,
  useCustomRequestListQuery,
} from '../queries'
import { usePendingFormStorage } from '../composables/usePendingFormStorage'
import { uploadCustomPhoto } from '../upload'
import {
  listCustomCases,
  listCanvasSizes,
  listPhotoPrices,
  STATUS_LABEL,
  DIFFICULTY_LABEL,
} from '../api'
import type {
  CreateCustomRequestPayload,
  Difficulty,
  CustomCase,
  CanvasSize,
  PhotoPriceRow,
} from '../api'
import CaseDetailDialog from '../components/CaseDetailDialog.vue'

const PHOTO_MAX_SIZE = 10 * 1024 * 1024  // 10 MB（規格 store_custom.md L34）
const PHOTO_MAX_SIZE_MB = 10

const router = useRouter()
const auth = useAuthStore()
const createMut = useCreateCustomRequestMutation()
const draft = usePendingFormStorage()

// 案例靈感（公開）— 取最新 6 件
const casesQuery = useQuery({
  queryKey: ['custom-cases', { page_size: 6 }] as const,
  queryFn: () => listCustomCases({ page: 1, page_size: 6 }),
  staleTime: 5 * 60 * 1000,
})
const cases = computed(() => casesQuery.data.value?.items ?? [])

// Canvas sizes（公開）— 動態載入
const canvasSizesQuery = useQuery({
  queryKey: ['canvas-sizes'] as const,
  queryFn: listCanvasSizes,
  staleTime: 30 * 60 * 1000,
})
const canvasSizes = computed<CanvasSize[]>(() => canvasSizesQuery.data.value?.items ?? [])

// 客製照片參考定價（公開）— 用於 PriceRangeHint
const pricesQuery = useQuery({
  queryKey: ['custom-photo-prices'] as const,
  queryFn: listPhotoPrices,
  staleTime: 30 * 60 * 1000,
})
const photoPrices = computed<PhotoPriceRow[]>(() => pricesQuery.data.value?.items ?? [])

// 已登入：顯示自己的進行中申請（不包含已完成）
const myListQuery = useCustomRequestListQuery(() => ({ page: 1, page_size: 5 }))
const inflightRequests = computed(() =>
  (myListQuery.data.value?.items ?? []).filter(
    (r) => r.status !== 'quote_confirmed' && r.status !== 'quote_rejected',
  ),
)

// ── 案例詳情 dialog ────────────────────────────────────────────────────────
const activeCase = ref<CustomCase | null>(null)
function openCase(c: CustomCase) { activeCase.value = c }
function closeCase() { activeCase.value = null }
function consultCase(c: CustomCase) {
  // 從 dialog 點「諮詢類似規格」 → 預填 + 滾到表單 + 關閉
  if (c.canvas_w_cm && c.canvas_h_cm) {
    selectedCanvasId.value = matchCanvasIdByDimensions(c.canvas_w_cm, c.canvas_h_cm) ?? null
    if (!selectedCanvasId.value) {
      // 案例尺寸不在 active sizes 中 — 仍記下尺寸，提示客戶
      customCanvasW.value = c.canvas_w_cm
      customCanvasH.value = c.canvas_h_cm
    }
  }
  if (c.difficulty) difficulty.value = c.difficulty as Difficulty
  customerNotes.value =
    `希望做出類似「${c.title}」風格的作品。\n` +
    (customerNotes.value ? `\n${customerNotes.value}` : '')
  closeCase()
  setTimeout(() => {
    document.getElementById('apply-form')?.scrollIntoView({ behavior: 'smooth' })
  }, 100)
}

function matchCanvasIdByDimensions(w: number, h: number): string | null {
  const m = canvasSizes.value.find((s) => s.canvas_w_cm === w && s.canvas_h_cm === h)
  return m ? m.id : null
}

// ── 表單狀態 ───────────────────────────────────────────────────────────────
// photoUrl: firebase_path（私密路徑）；photoPreviewUrl: 本地 blob url 預覽
const photoUrl = ref<string>('')
const photoPreviewUrl = ref<string>('')
const photoUploading = ref(false)
const photoError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

// 畫布尺寸（選填）：可選 active sizes 之一，或自訂尺寸
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

// 難度（選填，可送 null）
const difficulty = ref<Difficulty | null>(null)
const difficultyChoice = ref<Difficulty | 'admin_suggest' | null>(null)
watch(difficultyChoice, (v) => {
  difficulty.value = v === 'admin_suggest' ? null : v
})

const customerNotes = ref<string>('')
const formError = ref<string | null>(null)

// 規格：custom_photo 不問細緻度（pricing_formula.md 明確）

const DIFFICULTIES: Array<{ value: Difficulty | 'admin_suggest'; label: string; hint: string }> = [
  { value: 'beginner', label: DIFFICULTY_LABEL.beginner, hint: '色塊大、好上手' },
  { value: 'elementary', label: DIFFICULTY_LABEL.elementary, hint: '入門再進一級' },
  { value: 'intermediate', label: DIFFICULTY_LABEL.intermediate, hint: '層次更豐富' },
  { value: 'advanced', label: DIFFICULTY_LABEL.advanced, hint: '高細節、考驗耐心' },
  { value: 'admin_suggest', label: '讓管理員建議', hint: '收到照片後幫你推薦' },
]

// PriceRangeHint：依 canvas + difficulty 計算參考價
const priceHint = computed<{ exact?: number; min?: number; max?: number; reason?: string } | null>(() => {
  const c = effectiveCanvas.value
  const prices = photoPrices.value
  if (prices.length === 0) {
    return { reason: '尚未公開定價，送出後管理員會給您正式報價。' }
  }
  if (!c) {
    // 無尺寸 → 顯示總體區間
    const all = prices.map((p) => p.price).filter((x): x is number => x != null)
    if (all.length === 0) return null
    return { min: Math.min(...all), max: Math.max(...all), reason: '依尺寸與難度區間。' }
  }
  // 有尺寸 → 找該尺寸所有難度的價格
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

// 表單有效性：規格說「畫布尺寸選填」+ 難度選填（含「讓管理員建議」），所以只剩照片必填
const formValid = computed(() => !!photoUrl.value)

// ── 表單行為 ───────────────────────────────────────────────────────────────

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
    detail: null,  // custom_photo 不問細緻度
    customer_notes: customerNotes.value.trim() || null,
    parent_request_id: null,
  }
}

// 送出後 success state
const submittedRequestId = ref<string | null>(null)
const replyDays = ref<number>(3)  // 從 system_settings 拿到的回覆天數

async function submit() {
  formError.value = null

  // 未登入：把規格 / 備註存到 sessionStorage（規格 §Q2-B：照片要登入後再選），導去登入頁
  if (!auth.isLoggedIn) {
    draft.save({
      ...buildPayload(),
      photo_url: null,  // 照片不暫存（規格要求）
    })
    // toast 顯示提示
    showStashedToast.value = true
    setTimeout(() => {
      router.push({
        path: '/login',
        query: { redirect: '/custom?from=draft' },
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
    // 不直接跳轉，先顯示 success state（規格 §47：「申請已送出，管理員將於 X 個工作天內回覆報價」）
    setTimeout(() => {
      document.getElementById('success-anchor')?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  } catch (err) {
    formError.value = (err as Error).message || '送出失敗，請稍後再試'
  }
}

const showStashedToast = ref(false)

// 登入回填 — 若 query 有 from=draft 且 sessionStorage 有資料 → 自動補回（不自動送出，因為照片需要重新上傳）
async function tryAutoResume() {
  if (!auth.isLoggedIn) return
  const params = new URLSearchParams(window.location.search)
  if (params.get('from') !== 'draft' && params.get('from') !== 'expired') return
  const saved = draft.load()
  if (!saved) return
  // 補回 UI 狀態：只有規格 / 備註 / 難度，照片要重上傳
  if (saved.canvas_w_cm && saved.canvas_h_cm) {
    const matchedId = matchCanvasIdByDimensions(saved.canvas_w_cm, saved.canvas_h_cm)
    if (matchedId) {
      selectedCanvasId.value = matchedId
    } else {
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
  // 提示：請重新上傳照片
  if (params.get('from') === 'expired') {
    formError.value = '已套用上次申請的規格與備註，請重新上傳照片。'
  } else {
    formError.value = '已自動回填您的資料，請選擇照片後送出。'
  }
}

// 等 canvasSizes 載入完才嘗試 resume（matchCanvasIdByDimensions 需要 sizes）
watch(
  [() => auth.bootstrapped, canvasSizes],
  ([booted, sizes]) => {
    if (booted && sizes.length > 0) tryAutoResume()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value)
})
</script>

<template>
  <main class="custom-page">
    <!-- ── HERO ──────────────────────────────────────────────────────── -->
    <section class="hero">
      <div class="hero-inner">
        <div class="kicker">
          <span class="kicker-no">No. 07</span>
          <span class="kicker-dot"></span>
          <span class="kicker-chapter">Custom · 客製化</span>
        </div>
        <h1 class="hero-title">把你的回憶<br />做成一幅畫</h1>
        <p class="hero-desc">
          上傳一張照片，我們將它轉換為數字油畫模板。<br />
          回覆報價約 1–3 個工作天。
        </p>
      </div>
    </section>

    <!-- ── 已登入：進行中申請 ────────────────────────────────────── -->
    <section v-if="inflightRequests.length > 0" class="inflight">
      <SectionMasthead
        no="01"
        chapter="In progress"
        title="進行中的申請"
        link-text="查看全部 →"
        link-to="/custom/requests"
      />
      <ul class="inflight-list">
        <li v-for="req in inflightRequests" :key="req.id" class="inflight-item">
          <RouterLink :to="{ name: 'custom-request-detail', params: { id: req.id } }">
            <div class="inflight-status">{{ STATUS_LABEL[req.status] }}</div>
            <div class="inflight-meta">
              <span>{{ new Date(req.created_at).toLocaleDateString('zh-TW') }}</span>
              <span v-if="req.quoted_price">NT$ {{ req.quoted_price }}</span>
            </div>
          </RouterLink>
        </li>
      </ul>
    </section>

    <!-- ── 案例靈感 ─────────────────────────────────────────────────── -->
    <section v-if="cases.length > 0" class="cases">
      <SectionMasthead
        no="02"
        chapter="Inspiration"
        title="客製案例參考"
        caption="From our archive"
      />
      <div class="case-grid">
        <article
          v-for="c in cases"
          :key="c.id"
          class="case-card"
          @click="openCase(c)"
        >
          <div class="case-img">
            <img :src="c.image_url" :alt="c.title" loading="lazy" />
          </div>
          <div class="case-meta">
            <h3>{{ c.title }}</h3>
            <p v-if="c.canvas_w_cm" class="case-spec">
              {{ c.canvas_w_cm }}×{{ c.canvas_h_cm }} cm
              <span v-if="c.difficulty"> · {{ DIFFICULTY_LABEL[c.difficulty as Difficulty] || c.difficulty }}</span>
            </p>
          </div>
          <span class="case-cta">查看詳情 →</span>
        </article>
      </div>
    </section>

    <!-- ── 4-step process ───────────────────────────────────────────── -->
    <section class="process">
      <SectionMasthead no="03" chapter="How it works" title="客製流程" />
      <ol class="steps">
        <li class="step">
          <div class="step-icon"><ImagePlus :size="20" :stroke-width="1.4" /></div>
          <div class="step-no">01</div>
          <h3>提交申請</h3>
          <p>上傳照片、選擇尺寸與難度，留下備註。</p>
        </li>
        <li class="step">
          <div class="step-icon"><MessageSquare :size="20" :stroke-width="1.4" /></div>
          <div class="step-no">02</div>
          <h3>回覆報價</h3>
          <p>1–3 個工作天內，我們透過 Email 通知您報價結果。</p>
        </li>
        <li class="step">
          <div class="step-icon"><CheckCircle2 :size="20" :stroke-width="1.4" /></div>
          <div class="step-no">03</div>
          <h3>確認下單</h3>
          <p>查看降解析度浮水印預覽圖，滿意後 24 小時內付款。</p>
        </li>
        <li class="step">
          <div class="step-icon"><Palette :size="20" :stroke-width="1.4" /></div>
          <div class="step-no">04</div>
          <h3>專屬製作</h3>
          <p>付款後正式進入製作排程，原寸高解析數字稿親手交付。</p>
        </li>
      </ol>
    </section>

    <!-- ── 申請表單 ──────────────────────────────────────────────────── -->
    <section class="form-section" id="apply-form">
      <SectionMasthead
        no="04"
        chapter="Apply"
        title="開始申請"
        caption="Bring your photo to canvas"
      />

      <!-- 已送出 success state -->
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

          <!-- 未登入：照片區塊 disabled + 提示（規格 §3.2 Q2-B）-->
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
            <Loader2 :size="20" class="spin" />
            <p>上傳中…</p>
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

        <!-- Step 2: 尺寸（選填）-->
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

        <!-- Step 3: 難度（選填，含「讓管理員建議」）-->
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

        <!-- 參考價格區間 -->
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
          ></textarea>
        </fieldset>

        <!-- 錯誤提示 / 回填提示 -->
        <p v-if="formError" class="info-msg">{{ formError }}</p>

        <!-- Submit -->
        <div class="submit-row">
          <button
            type="submit"
            class="btn-primary"
            :disabled="createMut.isPending.value"
          >
            <Loader2 v-if="createMut.isPending.value" :size="16" class="spin" />
            <Sparkles v-else :size="16" :stroke-width="1.5" />
            {{ auth.isLoggedIn ? '送出申請' : '送出申請（先登入）' }}
          </button>
          <p class="submit-hint">
            送出後我們會在 1–3 個工作天內回覆報價，並透過 Email 與站內訊息通知您。
          </p>
        </div>
      </form>
    </section>

    <!-- 暫存提示 toast -->
    <Transition name="toast">
      <div v-if="showStashedToast" class="toast">
        資料已暫存，請登入後自動送出，無需重新填寫
      </div>
    </Transition>

    <!-- 案例詳情 modal -->
    <CaseDetailDialog
      :case-data="activeCase"
      @close="closeCase"
      @consult="consultCase"
    />
  </main>
</template>

<style scoped>
.custom-page {
  max-width: 1080px; margin: 0 auto;
  padding: 32px 24px 96px;
}

.hero {
  padding: 80px 0 56px;
  border-bottom: 1px solid var(--color-line);
  margin-bottom: 64px;
}
.hero-inner { max-width: 720px; }
.kicker {
  display: flex; align-items: center; gap: 10px; margin-bottom: 24px;
}
.kicker-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); }
.kicker-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.kicker-chapter { font-family: var(--font-display); font-style: italic; font-size: 14px; color: var(--color-accent); }
.hero-title {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: clamp(36px, 5vw, 56px); letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 24px; line-height: 1.25;
}
.hero-desc { font-size: 16px; color: var(--color-ink-default); letter-spacing: 0.02em; line-height: 1.8; margin: 0; }

.inflight { margin-bottom: 64px; }
.inflight-list {
  list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.inflight-item a {
  display: block; padding: 20px;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  text-decoration: none; color: var(--color-ink-strong);
  transition: border-color 150ms;
}
.inflight-item a:hover { border-color: var(--color-accent); }
.inflight-status { font-family: var(--font-cn-serif); font-size: 17px; margin-bottom: 8px; }
.inflight-meta {
  display: flex; gap: 12px;
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.1em; color: var(--color-ink-muted);
}

.cases { margin-bottom: 80px; }
.case-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px;
}
.case-card {
  position: relative; cursor: pointer;
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  overflow: hidden; background: #FFF;
  transition: border-color 200ms, transform 200ms;
}
.case-card:hover { border-color: var(--color-accent); transform: translateY(-2px); }
.case-card:hover .case-cta { opacity: 1; transform: translateY(0); }
.case-img { aspect-ratio: 4 / 3; overflow: hidden; background: var(--color-paper-surface, #FCF7E5); }
.case-img img { width: 100%; height: 100%; object-fit: cover; }
.case-meta { padding: 14px 16px 12px; border-top: 1px solid var(--color-line); }
.case-meta h3 {
  font-family: var(--font-cn-serif); font-weight: 400;
  font-size: 15px; color: var(--color-ink-strong); margin: 0 0 4px;
}
.case-spec {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--color-ink-muted); margin: 0; letter-spacing: 0.06em;
}
.case-cta {
  position: absolute; bottom: 12px; right: 14px;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--color-accent-deep);
  background: var(--color-paper-surface, #FCF7E5);
  padding: 4px 10px; border-radius: 999px;
  opacity: 0; transform: translateY(4px);
  transition: opacity 200ms, transform 200ms;
}

.process { margin-bottom: 80px; }
.steps { list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 32px; }
.step { padding: 28px 24px 24px; border-top: 1px solid var(--color-line); }
.step-icon {
  width: 40px; height: 40px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line);
  border-radius: 50%; margin-bottom: 16px;
  color: var(--color-accent-deep);
}
.step-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); margin-bottom: 8px; }
.step h3 { font-family: var(--font-cn-serif); font-weight: 300; font-size: 19px; letter-spacing: 0.04em; margin: 0 0 8px; color: var(--color-ink-strong); }
.step p { font-size: 14px; color: var(--color-ink-muted); line-height: 1.7; margin: 0; }

.form-section { margin-bottom: 64px; }
.form { display: flex; flex-direction: column; gap: 40px; }
.field { border: 0; padding: 0; margin: 0; }
.field-legend {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-cn-serif); font-weight: 300; font-size: 19px;
  color: var(--color-ink-strong); letter-spacing: 0.04em;
  margin-bottom: 12px;
}
.field-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; color: var(--color-fresh); padding: 2px 8px; border: 1px solid var(--color-line); border-radius: 2px; }
.field-required { color: var(--color-accent); margin-left: 2px; }
.field-optional { font-family: var(--font-mono); font-size: 10px; color: var(--color-ink-muted); letter-spacing: 0.12em; }
.field-hint { font-size: 13px; color: var(--color-ink-muted); margin: 0 0 16px; letter-spacing: 0.02em; }

.hidden { display: none; }
.loading-row { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-ink-muted); }

.photo-empty {
  border: 1.5px dashed var(--color-line-strong, #BFAD8C);
  background: var(--color-paper-surface, #FCF7E5);
  border-radius: var(--radius-sm);
  aspect-ratio: 4 / 3; max-width: 480px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; cursor: pointer; transition: border-color 150ms, background 150ms;
}
.photo-empty:hover {
  border-color: var(--color-accent); background: var(--color-paper-subtle, #FAF4DD);
}
.photo-empty.photo-locked { cursor: not-allowed; opacity: 0.7; }
.photo-empty.photo-locked:hover { border-color: var(--color-line-strong, #BFAD8C); background: var(--color-paper-surface, #FCF7E5); }
.photo-empty p { margin: 0; font-size: 14px; color: var(--color-ink-default); }
.photo-empty-hint { font-size: 12px; color: var(--color-ink-muted); }
.photo-empty-icon { color: var(--color-accent); }

.photo-uploading {
  display: flex; align-items: center; gap: 12px;
  padding: 32px; max-width: 480px;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
}
.photo-preview { position: relative; max-width: 480px; border: 1px solid var(--color-line); border-radius: var(--radius-sm); overflow: hidden; }
.photo-preview img { width: 100%; display: block; }
.photo-clear {
  position: absolute; top: 12px; right: 12px;
  width: 32px; height: 32px; border: 0; background: rgba(255, 255, 255, 0.9);
  border-radius: 50%; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--color-ink-strong);
}
.photo-replace {
  position: absolute; bottom: 12px; right: 12px;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 12px; font-size: 12px;
  background: rgba(255, 255, 255, 0.92); border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); cursor: pointer; color: var(--color-ink-strong);
}

.size-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
.size-chip, .level-chip {
  background: transparent; cursor: pointer;
  padding: 14px 12px; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-family: inherit;
  color: var(--color-ink-default); font-size: 14px;
  transition: border-color 150ms, color 150ms, background 150ms;
}
.size-chip:hover, .level-chip:hover {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.size-chip.active, .level-chip.active {
  border-color: var(--color-accent-deep);
  background: var(--color-paper-surface, #FCF7E5);
  color: var(--color-accent-deep);
}
.level-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.level-chip { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; text-align: left; }
.level-chip strong { font-family: var(--font-cn-serif); font-weight: 400; font-size: 15px; }
.level-chip span { font-size: 12px; color: var(--color-ink-muted); }

.price-hint {
  display: flex; gap: 12px; align-items: flex-start;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line);
  border-left: 3px solid var(--color-accent);
  border-radius: var(--radius-xs);
  padding: 14px 18px;
}
.price-hint > svg { color: var(--color-accent); margin-top: 2px; flex-shrink: 0; }
.price-hint-text { flex: 1; font-size: 14px; color: var(--color-ink-default); line-height: 1.6; }
.price-hint-text strong { color: var(--color-accent-deep); }
.price-hint-note { font-size: 11px; color: var(--color-ink-muted); margin: 4px 0 0; font-style: italic; }

.textarea {
  width: 100%; padding: 12px 14px;
  font: inherit; font-size: 14px; line-height: 1.7;
  color: var(--color-ink-default);
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  resize: vertical; min-height: 96px;
}
.textarea:focus { outline: none; border-color: var(--color-accent); background: var(--color-paper-base, #F7F1E3); }

.error { font-size: 13px; color: #B85B58; margin: 8px 0 0; }
.info-msg {
  padding: 12px 16px; margin: 0;
  background: rgba(212, 165, 116, 0.12);
  border: 1px solid rgba(212, 165, 116, 0.4);
  border-radius: var(--radius-xs);
  font-size: 13px; color: #8B6232;
}

.submit-row { display: flex; flex-direction: column; align-items: stretch; gap: 12px;
  padding-top: 24px; border-top: 1px solid var(--color-line); }
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  align-self: flex-start;
  padding: 14px 28px; min-width: 200px;
  background: var(--color-accent-deep); color: #FCF7E5;
  border: 0; border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 15px; letter-spacing: 0.08em;
  cursor: pointer; transition: background 150ms; text-decoration: none;
}
.btn-primary:hover:not(:disabled) { background: var(--color-accent); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 12px 24px; cursor: pointer;
  background: transparent; color: var(--color-ink-default);
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 14px; letter-spacing: 0.06em;
  text-decoration: none;
}
.btn-secondary:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }

.submit-hint { font-size: 12px; color: var(--color-ink-muted); margin: 0; }

/* success state */
.success-state {
  text-align: center; padding: 48px 24px;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
}
.success-icon { color: #5A7A4F; margin-bottom: 16px; }
.success-state h3 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 28px; letter-spacing: 0.04em; margin: 0 0 12px;
  color: var(--color-ink-strong);
}
.success-state p { margin: 0 0 6px; font-size: 15px; color: var(--color-ink-default); line-height: 1.7; }
.success-hint { font-size: 13px !important; color: var(--color-ink-muted) !important; }
.success-actions { display: flex; gap: 12px; justify-content: center; margin-top: 24px; flex-wrap: wrap; }

/* toast */
.toast {
  position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%);
  background: var(--color-accent-deep); color: #FCF7E5;
  padding: 14px 24px; border-radius: var(--radius-sm);
  font-family: var(--font-cn-serif); font-size: 14px; letter-spacing: 0.04em;
  box-shadow: 0 8px 24px rgba(43, 36, 27, 0.18);
  z-index: 60;
}
.toast-enter-active, .toast-leave-active { transition: opacity 200ms, transform 200ms; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 8px); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
