<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import {
  ArrowLeft, Camera, Loader2, Pencil, Send, Upload,
} from 'lucide-vue-next'
import {
  customQueryKeys,
  useCustomRequestDetailQuery,
  useCustomPhotoSignedUrlQuery,
  usePostCustomMessageMutation,
  useUpdateCustomPhotoMutation,
} from '../queries'
import { useCustomRequestSse } from '../composables/useCustomRequestSse'
import { usePendingFormStorage } from '../composables/usePendingFormStorage'
import { uploadCustomPhoto } from '../upload'
import {
  STATUS_LABEL,
  REQUEST_TYPE_LABEL,
  DIFFICULTY_LABEL,
  updateCustomRequestFields,
  type Difficulty,
} from '../api'

import RequestProgressStepper from '../components/RequestProgressStepper.vue'
import MessageTimeline from '../components/MessageTimeline.vue'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const draft = usePendingFormStorage()
const requestId = computed(() => route.params.id as string)

const detailQuery = useCustomRequestDetailQuery(requestId)
const postMsgMut = usePostCustomMessageMutation()
const updatePhotoMut = useUpdateCustomPhotoMutation()

const detail = computed(() => detailQuery.data.value)
const hasPhoto = computed(() => !!detail.value?.photo_url)
const photoSignedUrlQuery = useCustomPhotoSignedUrlQuery(requestId, hasPhoto)
const photoSrc = computed(() => photoSignedUrlQuery.data.value?.url ?? '')

// SSE
const { connected } = useCustomRequestSse(requestId, {
  onMessage: () => scrollToBottom(),
})

// ── 對話 ──────────────────────────────────────────────────────────────────────
const draftMessage = ref('')
const sendError = ref<string | null>(null)
const messagesEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  // 也讓整頁滑到底（雜誌長頁的「最新」即在最下）
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}
watch(() => detail.value?.messages?.length, () => scrollToBottom())

async function sendMessage() {
  const text = draftMessage.value.trim()
  if (!text || postMsgMut.isPending.value) return
  sendError.value = null
  try {
    await postMsgMut.mutateAsync({ requestId: requestId.value, message: text })
    draftMessage.value = ''
  } catch (e) {
    sendError.value = (e as Error).message || '送出失敗'
  }
}

// ── 規格編輯（quote_pending 才能）────────────────────────────────────────────
const editing = ref(false)
const editError = ref<string | null>(null)
const editSaving = ref(false)
const editForm = ref<{
  canvas_w_cm: number | null
  canvas_h_cm: number | null
  difficulty: Difficulty | 'admin_suggest' | null
  customer_notes: string
}>({
  canvas_w_cm: null,
  canvas_h_cm: null,
  difficulty: null,
  customer_notes: '',
})

const DIFFICULTY_OPTIONS: Array<{ value: Difficulty | 'admin_suggest'; label: string }> = [
  { value: 'beginner', label: DIFFICULTY_LABEL.beginner },
  { value: 'elementary', label: DIFFICULTY_LABEL.elementary },
  { value: 'intermediate', label: DIFFICULTY_LABEL.intermediate },
  { value: 'advanced', label: DIFFICULTY_LABEL.advanced },
  { value: 'admin_suggest', label: '讓管理員建議' },
]

function openEdit() {
  if (!detail.value) return
  editForm.value = {
    canvas_w_cm: detail.value.canvas_w_cm,
    canvas_h_cm: detail.value.canvas_h_cm,
    difficulty: (detail.value.difficulty as Difficulty | null) ?? 'admin_suggest',
    customer_notes: detail.value.customer_notes ?? '',
  }
  editError.value = null
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  editError.value = null
}

async function saveEdit() {
  if (!detail.value) return
  editSaving.value = true
  editError.value = null
  const payload: Record<string, unknown> = {}
  const f = editForm.value
  if (f.canvas_w_cm !== detail.value.canvas_w_cm) payload.canvas_w_cm = f.canvas_w_cm
  if (f.canvas_h_cm !== detail.value.canvas_h_cm) payload.canvas_h_cm = f.canvas_h_cm
  const newDifficulty = f.difficulty === 'admin_suggest' ? null : f.difficulty
  if (newDifficulty !== detail.value.difficulty) payload.difficulty = newDifficulty
  if (f.customer_notes !== (detail.value.customer_notes ?? '')) {
    payload.customer_notes = f.customer_notes.trim() || null
  }
  try {
    await updateCustomRequestFields(requestId.value, payload)
    queryClient.invalidateQueries({ queryKey: customQueryKeys.detail(requestId.value) })
    editing.value = false
  } catch (e) {
    const err = e as Error & { code?: string; status?: number }
    if (err.code === 'REQUEST_LOCKED_AFTER_NEGOTIATING' || err.status === 409) {
      editError.value = '申請已進入洽談階段，無法修改。'
    } else {
      editError.value = err.message || '更新失敗'
    }
  } finally {
    editSaving.value = false
  }
}

// ── 重新上傳照片 ──────────────────────────────────────────────────────────────
const photoInput = ref<HTMLInputElement | null>(null)
const photoUploading = ref(false)
const photoError = ref<string | null>(null)

function triggerPhotoUpload() {
  photoInput.value?.click()
}

async function onPhotoChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    photoError.value = '檔案超過 10MB'
    return
  }
  if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
    photoError.value = '只接受 JPEG / PNG'
    return
  }
  photoError.value = null
  photoUploading.value = true
  try {
    const path = await uploadCustomPhoto(file)
    await updatePhotoMut.mutateAsync({ requestId: requestId.value, photo_url: path })
  } catch (err) {
    photoError.value = (err as Error).message || '更新照片失敗'
  } finally {
    photoUploading.value = false
    if (photoInput.value) photoInput.value.value = ''
  }
}

// ── 重新申請（過期 / 拒絕後）─────────────────────────────────────────────────
function reapplyFromExpired() {
  if (!detail.value) return
  draft.save({
    request_type: 'custom_photo',
    photo_url: null,
    ref_product_id: null,
    canvas_w_cm: detail.value.canvas_w_cm,
    canvas_h_cm: detail.value.canvas_h_cm,
    difficulty: detail.value.difficulty as Difficulty | null,
    detail: null,
    customer_notes: detail.value.customer_notes,
    parent_request_id: detail.value.id,
  })
  router.push({ path: '/custom/apply', query: { from: 'expired' } })
}

// ── 顯示輔助 ──────────────────────────────────────────────────────────────────
function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('zh-TW', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

const isEditable = computed(() => detail.value?.status === 'quote_pending')

const expiresIn = computed(() => {
  const d = detail.value
  if (!d || d.status !== 'quote_sent' || !d.quote_expires_at) return null
  const ms = new Date(d.quote_expires_at).getTime() - Date.now()
  if (ms <= 0) return '已逾期'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return h > 0 ? `${h} 小時 ${m} 分後到期` : `${m} 分鐘後到期`
})

// ── Banner 設計（依 status）──────────────────────────────────────────────────
type BannerKind = 'revision' | 'quoted' | 'confirmed' | 'archived' | null

const banner = computed<{
  kind: BannerKind
  title: string
  body?: string
  ctaLabel?: string
  ctaTo?: () => void
} | null>(() => {
  const d = detail.value
  if (!d) return null

  switch (d.status) {
    case 'draft_revision':
      return {
        kind: 'revision',
        title: `已要求修改（${d.revision_count}/3）`,
        body: '我們收到您的修改要求，正在重新製作。',
      }
    case 'quote_sent':
      return {
        kind: 'quoted',
        title: '報價已送達',
        body: expiresIn.value
          ? `請於 ${expiresIn.value}前完成確認。`
          : '請於有效期限內完成確認。',
        ctaLabel: '前往報價頁',
        ctaTo: () => goToQuote(),
      }
    case 'quote_confirmed':
      return d.order_id ? {
        kind: 'confirmed',
        title: '已成立訂單',
        body: '請完成付款以進入製作流程。',
        ctaLabel: '前往訂單付款',
        ctaTo: () => router.push({ name: 'order-detail', params: { id: d.order_id! } }),
      } : null
    case 'quote_rejected':
      return {
        kind: 'archived',
        title: '此申請已關閉（您拒絕了報價）',
        body: '如仍想下單，可重新申請。',
        ctaLabel: '重新申請',
        ctaTo: () => router.push('/custom/apply'),
      }
    case 'quote_expired':
      return {
        kind: 'archived',
        title: '報價已逾期',
        body: '逾 24 小時未確認，本申請已封存。',
        ctaLabel: '重新申請（預填上次資料）',
        ctaTo: () => reapplyFromExpired(),
      }
    default:
      return null
  }
})

function goToQuote() {
  const t = detail.value?.quote_token
  if (t) {
    router.push(`/custom/quote/${encodeURIComponent(t)}`)
    return
  }
  // 通常是頁面 cache 舊版本（quote_token 是新增欄位）。
  // eslint-disable-next-line no-console
  console.error('[goToQuote] no quote_token in detail:', detail.value)
  alert(
    '無法取得報價連結。請按 Ctrl+Shift+R 強制重整頁面再試一次。\n'
    + '（若仍不行請告知工程師：detail.quote_token 為空）',
  )
}

const composerVisible = computed(() =>
  ['quote_pending', 'negotiating', 'quote_sent', 'draft_revision'].includes(
    detail.value?.status ?? '',
  ),
)
</script>

<template>
  <main class="page">
    <RouterLink to="/custom/requests" class="back-link">
      <ArrowLeft :size="14" />
      返回申請列表
    </RouterLink>

    <div v-if="detailQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" />
      載入中…
    </div>
    <div v-else-if="detailQuery.isError.value" class="state error">
      <p>{{ (detailQuery.error.value as Error)?.message ?? '載入失敗' }}</p>
      <button class="btn-ghost" @click="router.push('/custom/requests')">回到列表</button>
    </div>

    <template v-else-if="detail">
      <!-- ── Page Header ────────────────────────────────────────────── -->
      <header class="hd">
        <div class="hd-meta">
          <span class="hd-no">No. {{ detail.id.slice(0, 8).toUpperCase() }}</span>
          <span class="hd-dot" />
          <span class="hd-type">{{ REQUEST_TYPE_LABEL[detail.request_type] }}</span>
          <span class="hd-line" />
          <span
            class="sse-dot"
            :class="connected ? 'is-on' : 'is-off'"
            :title="connected ? '即時連線中' : '連線中斷，重整頁面'"
          >
            <span class="sse-pulse" />
            {{ connected ? '即時連線' : '已離線' }}
          </span>
        </div>
        <h1 class="hd-title">客製申請</h1>
        <p class="hd-sub">
          提交於 {{ fmtDateTime(detail.created_at) }}　·　目前狀態：
          <strong>{{ STATUS_LABEL[detail.status] }}</strong>
        </p>
      </header>

      <!-- ── 進度條 ──────────────────────────────────────────────────── -->
      <RequestProgressStepper :status="detail.status" class="stepper" />

      <!-- ── 狀態 Banner ─────────────────────────────────────────────── -->
      <aside v-if="banner" class="banner" :class="`banner-${banner.kind}`">
        <div class="banner-text">
          <h3 class="banner-title">{{ banner.title }}</h3>
          <p v-if="banner.body" class="banner-body">{{ banner.body }}</p>
        </div>
        <button
          v-if="banner.ctaLabel && banner.ctaTo"
          type="button"
          class="banner-cta"
          @click="banner.ctaTo"
        >
          {{ banner.ctaLabel }} →
        </button>
      </aside>

      <!-- ── 申請快照（照片 + 規格）─────────────────────────────────── -->
      <section class="snapshot">
        <h2 class="sec-title">
          <span class="sec-no">01</span>
          <span>申請快照</span>
        </h2>

        <div class="snapshot-grid">
          <!-- 照片 -->
          <figure v-if="detail.photo_url" class="photo-card">
            <div class="photo-frame">
              <Loader2 v-if="photoSignedUrlQuery.isLoading.value" :size="20" class="spin photo-loading" />
              <img v-else-if="photoSrc" :src="photoSrc" :alt="`申請照片 ${detail.id.slice(0,8)}`" />
              <p v-else class="photo-private-hint">
                照片無法顯示<br>
                <small>（私密儲存）</small>
              </p>
            </div>
            <figcaption class="photo-cap">
              <Camera :size="11" :stroke-width="1.5" />
              客戶照片　·　私密
            </figcaption>
            <div v-if="isEditable" class="photo-actions">
              <input
                ref="photoInput"
                type="file"
                accept="image/jpeg,image/png"
                class="hidden-input"
                @change="onPhotoChange"
              />
              <button
                type="button"
                class="btn-ghost-sm"
                :disabled="photoUploading"
                @click="triggerPhotoUpload"
              >
                <Loader2 v-if="photoUploading" :size="12" class="spin" />
                <Upload v-else :size="12" :stroke-width="1.5" />
                重新上傳
              </button>
              <p v-if="photoError" class="error">{{ photoError }}</p>
            </div>
          </figure>

          <!-- 規格 -->
          <article class="spec-card">
            <header class="spec-head">
              <h3>規格</h3>
              <button v-if="isEditable && !editing" class="btn-ghost-sm" @click="openEdit">
                <Pencil :size="11" :stroke-width="1.5" />
                修改
              </button>
            </header>

            <dl v-if="!editing" class="spec-dl">
              <div class="spec-row">
                <dt>畫布尺寸</dt>
                <dd v-if="detail.canvas_w_cm">
                  {{ detail.canvas_w_cm }} × {{ detail.canvas_h_cm }} cm
                </dd>
                <dd v-else class="muted">未指定（讓管理員建議）</dd>
              </div>
              <div class="spec-row">
                <dt>難易度</dt>
                <dd v-if="detail.difficulty">
                  {{ DIFFICULTY_LABEL[detail.difficulty as Difficulty] }}
                </dd>
                <dd v-else class="muted">讓管理員建議</dd>
              </div>
              <div v-if="detail.customer_notes" class="spec-row">
                <dt>備註</dt>
                <dd class="multiline">{{ detail.customer_notes }}</dd>
              </div>
              <div v-if="detail.quoted_price" class="spec-row spec-price">
                <dt>報價金額</dt>
                <dd>NT$ {{ detail.quoted_price.toLocaleString() }}</dd>
              </div>
            </dl>

            <form v-else class="edit-form" @submit.prevent="saveEdit">
              <label class="field">
                <span class="field-lb">畫布尺寸（cm）</span>
                <span class="field-row">
                  <input v-model.number="editForm.canvas_w_cm" type="number" min="20" max="120" class="num" />
                  <span class="cross">×</span>
                  <input v-model.number="editForm.canvas_h_cm" type="number" min="20" max="120" class="num" />
                </span>
              </label>
              <label class="field">
                <span class="field-lb">難易度</span>
                <select v-model="editForm.difficulty" class="select">
                  <option v-for="d in DIFFICULTY_OPTIONS" :key="d.value" :value="d.value">
                    {{ d.label }}
                  </option>
                </select>
              </label>
              <label class="field">
                <span class="field-lb">備註</span>
                <textarea v-model="editForm.customer_notes" rows="3" class="textarea" />
              </label>
              <p v-if="editError" class="error">{{ editError }}</p>
              <div class="edit-actions">
                <button type="button" class="btn-ghost-sm" @click="cancelEdit">取消</button>
                <button type="submit" class="btn-primary-sm" :disabled="editSaving">
                  <Loader2 v-if="editSaving" :size="12" class="spin" />
                  儲存修改
                </button>
              </div>
            </form>
          </article>
        </div>
      </section>

      <!-- ── 對話 Timeline ───────────────────────────────────────────── -->
      <section class="thread">
        <h2 class="sec-title">
          <span class="sec-no">02</span>
          <span>對話紀錄</span>
        </h2>
        <div ref="messagesEl" class="msg-scroll">
          <MessageTimeline
            :messages="detail.messages"
            :quoted-price="detail.quoted_price"
            :quote-sent-at="detail.quoted_at"
            :quote-expires-at="detail.quote_expires_at"
            @go-to-quote="goToQuote"
          />
        </div>

        <form v-if="composerVisible" class="composer" @submit.prevent="sendMessage">
          <textarea
            v-model="draftMessage"
            rows="2"
            placeholder="補充說明或回覆訊息（Ctrl/⌘+Enter 送出）"
            @keydown.ctrl.enter="sendMessage"
            @keydown.meta.enter="sendMessage"
          />
          <button
            type="submit"
            class="composer-send"
            :disabled="!draftMessage.trim() || postMsgMut.isPending.value"
          >
            <Loader2 v-if="postMsgMut.isPending.value" :size="14" class="spin" />
            <Send v-else :size="14" :stroke-width="1.5" />
            傳送
          </button>
        </form>
        <p v-else class="closed-hint">此申請已關閉，無法繼續發訊息。</p>
        <p v-if="sendError" class="error">{{ sendError }}</p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  text-decoration: none;
  margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 16px;
  color: var(--color-ink-muted);
}
.state.error { flex-direction: column; }

.spin { animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Header ─────────────────────────────────────────────────────────── */
.hd {
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-line);
}
.hd-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.hd-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.hd-dot {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--color-accent);
}
.hd-type {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
}
.hd-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, var(--color-line), transparent 80%);
  min-width: 32px;
}

.sse-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid;
}
.sse-dot.is-on {
  color: var(--color-fresh);
  border-color: var(--color-fresh-soft);
  background: var(--color-fresh-tint);
}
.sse-dot.is-off {
  color: var(--color-ink-muted);
  border-color: var(--color-line);
  background: var(--color-paper-surface);
}
.sse-pulse {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.sse-dot.is-on .sse-pulse {
  animation: pulse-dot 1.6s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.4; }
}

.hd-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 32px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.hd-sub {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0;
  letter-spacing: 0.04em;
}
.hd-sub strong {
  font-weight: 500;
  color: var(--color-ink-default);
}

/* ── Stepper ─────────────────────────────────────────────────────── */
.stepper { margin-bottom: 32px; }

/* ── Banner ──────────────────────────────────────────────────────── */
.banner {
  margin: 0 0 36px;
  padding: 22px 24px;
  border: 1px solid;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}
.banner-text { flex: 1; min-width: 220px; }
.banner-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.04em;
  margin: 0 0 6px;
}
.banner-body {
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
  color: var(--color-ink-default);
}
.banner-cta {
  display: inline-flex;
  align-items: center;
  padding: 11px 22px;
  border: 0;
  border-radius: var(--radius-xs);
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  font-family: var(--font-cn-serif);
  font-size: 13px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 150ms;
}
.banner-cta:hover { background: var(--color-accent-deep); }

.banner-revision {
  background: var(--color-paper-surface);
  border-color: var(--color-state-warning);
}
.banner-revision .banner-title { color: var(--color-state-warning); }

.banner-quoted {
  background: var(--color-fresh-tint);
  border-color: var(--color-fresh);
}
.banner-quoted .banner-title { color: var(--color-fresh); }

.banner-confirmed {
  background: var(--color-accent-tint);
  border-color: var(--color-accent);
}
.banner-confirmed .banner-title { color: var(--color-accent-deep); }

.banner-archived {
  background: var(--color-paper-deep);
  border-color: var(--color-line);
  color: var(--color-ink-muted);
}
.banner-archived .banner-title { color: var(--color-ink-default); }
.banner-archived .banner-cta { background: var(--color-accent-deep); }

/* ── Section title ───────────────────────────────────────────────── */
.sec-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin: 0 0 20px;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}
.sec-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
}

/* ── Snapshot ────────────────────────────────────────────────────── */
.snapshot {
  border-top: 1px solid var(--color-line);
  padding-top: 32px;
  margin-bottom: 48px;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 32px;
  align-items: start;
}

.photo-card {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.photo-frame {
  aspect-ratio: 4 / 3;
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-paper-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  filter: sepia(0.07) saturate(0.92);
}
.photo-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.photo-loading { color: var(--color-ink-muted); }
.photo-private-hint {
  font-size: 12px;
  color: var(--color-ink-muted);
  text-align: center;
  margin: 0;
  padding: 16px;
  letter-spacing: 0.04em;
}
.photo-private-hint small {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
}
.photo-cap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.photo-actions { margin-top: 4px; }
.hidden-input { display: none; }

.spec-card {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 24px;
}
.spec-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.spec-head h3 {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.spec-dl { margin: 0; display: flex; flex-direction: column; gap: 14px; }
.spec-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 12px;
  align-items: baseline;
}
.spec-row dt {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.spec-row dd {
  font-size: 14px;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0;
}
.spec-row dd.muted { color: var(--color-ink-muted); }
.spec-row dd.multiline { white-space: pre-wrap; line-height: 1.7; }
.spec-price dd {
  font-family: var(--font-mono);
  font-size: 17px;
  color: var(--color-ink-strong);
}

/* edit form */
.edit-form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-lb {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.field-row { display: inline-flex; align-items: center; gap: 10px; }
.num, .select, .textarea {
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-canvas);
  border-radius: var(--radius-xs);
  padding: 8px 12px;
  font: inherit;
  font-size: 13px;
  color: var(--color-ink-default);
}
.num { width: 96px; }
.select { width: 100%; }
.textarea { width: 100%; resize: vertical; }
.num:focus, .select:focus, .textarea:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}
.cross { color: var(--color-ink-muted); }
.edit-actions { display: flex; justify-content: flex-end; gap: 8px; }

.btn-ghost-sm {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--color-line);
  background: transparent;
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-size: 12px;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
}
.btn-ghost-sm:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.btn-ghost-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary-sm {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border: 0;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-size: 12px;
  letter-spacing: 0.04em;
}
.btn-primary-sm:hover { background: var(--color-accent-deep); }
.btn-primary-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border: 1px solid var(--color-ink-strong);
  background: transparent;
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-size: 13px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
  margin-top: 12px;
}

/* ── Thread ──────────────────────────────────────────────────────── */
.thread {
  border-top: 1px solid var(--color-line);
  padding-top: 32px;
}
.msg-scroll {
  max-height: 560px;
  overflow-y: auto;
  padding: 4px 4px 8px;
  margin-bottom: 16px;
}
.msg-scroll::-webkit-scrollbar { width: 6px; }
.msg-scroll::-webkit-scrollbar-thumb {
  background: var(--color-line-subtle);
  border-radius: 3px;
}

.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: end;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 14px;
}
.composer textarea {
  border: 0;
  background: transparent;
  resize: vertical;
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-ink-default);
  min-height: 56px;
  padding: 4px;
}
.composer textarea:focus { outline: none; }

.composer-send {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border: 0;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-size: 13px;
  letter-spacing: 0.06em;
}
.composer-send:hover { background: var(--color-accent-deep); }
.composer-send:disabled { opacity: 0.5; cursor: not-allowed; }

.closed-hint {
  text-align: center;
  padding: 18px 12px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0;
}

.error {
  color: var(--color-state-danger);
  font-size: 12px;
  margin: 8px 0 0;
}

@media (max-width: 767px) {
  .hd-title { font-size: 26px; }
  .snapshot-grid { grid-template-columns: 1fr; gap: 24px; }
  .photo-card { max-width: 320px; }
}
</style>
