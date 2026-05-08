<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import {
  ArrowLeft, Camera, Clock, ImageIcon, Loader2, Pencil, Send, Upload, X,
} from 'lucide-vue-next'
import {
  customQueryKeys,
  useCustomRequestDetailQuery,
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
  type CustomRequestDetail,
} from '../api'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const draft = usePendingFormStorage()
const requestId = computed(() => route.params.id as string)

const detailQuery = useCustomRequestDetailQuery(requestId)
const postMsgMut = usePostCustomMessageMutation()
const updatePhotoMut = useUpdateCustomPhotoMutation()

const detail = computed(() => detailQuery.data.value)

// SSE 即時訂閱
const { connected } = useCustomRequestSse(requestId, {
  onMessage: () => scrollToBottom(),
  onStatusChanged: () => { /* auto-invalidate handled in composable */ },
  onQuoteSent: () => { /* auto-invalidate */ },
})

// ── 訊息對話 ──────────────────────────────────────────────────────────────
const draftMessage = ref('')
const sendError = ref<string | null>(null)
const messagesEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
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

// ── quote_pending 修改規格（規格 store_orders.md L100-122）─────────────────
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

// ── 重新上傳照片（quote_pending 才能）─────────────────────────────────────
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

// ── 過期重新申請 — 預填上次資料到 sessionStorage 後跳 /custom ─────────────
function reapplyFromExpired() {
  if (!detail.value) return
  draft.save({
    request_type: 'custom_photo',
    photo_url: null,  // 不複用舊 photo_path（私密路徑可能已失效）
    ref_product_id: null,
    canvas_w_cm: detail.value.canvas_w_cm,
    canvas_h_cm: detail.value.canvas_h_cm,
    difficulty: detail.value.difficulty as Difficulty | null,
    detail: null,
    customer_notes: detail.value.customer_notes,
    parent_request_id: detail.value.id,
  })
  router.push({ path: '/custom', query: { from: 'expired' } })
}

// ── 顯示輔助 ──────────────────────────────────────────────────────────────
function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('zh-TW', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

const statusBanner = computed<{ tone: string; text: string } | null>(() => {
  const d = detail.value
  if (!d) return null
  switch (d.status) {
    case 'quote_pending':
      return { tone: 'pending', text: '已收到您的申請。我們將在 1–3 個工作天內回覆報價。' }
    case 'negotiating':
      return { tone: 'progress', text: '我們正在依您的需求製作測試稿。' }
    case 'quote_sent':
      return { tone: 'action', text: '報價已送達！請於有效期限內確認（從 Email 開啟報價連結）。' }
    case 'quote_confirmed':
      return { tone: 'ok', text: '已成立訂單。請完成付款。' }
    case 'quote_rejected':
      return { tone: 'danger', text: '您已拒絕此報價，本申請已關閉。' }
    case 'quote_expired':
      return { tone: 'danger', text: '報價已逾期。如仍想下單，請重新申請。' }
    case 'draft_revision':
      return { tone: 'progress', text: '我們收到您的修改要求，正在重新製作。' }
  }
  return null
})

const isEditable = computed(() => detail.value?.status === 'quote_pending')

const expiresAt = computed(() => {
  const d = detail.value
  if (d?.status !== 'quote_sent') return null
  return d.quote_expires_at ? new Date(d.quote_expires_at) : null
})
const expiresIn = computed(() => {
  const ea = expiresAt.value
  if (!ea) return null
  const ms = ea.getTime() - Date.now()
  if (ms <= 0) return '已逾期'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return h > 0 ? `${h} 小時 ${m} 分後到期` : `${m} 分鐘後到期`
})

onBeforeUnmount(() => {
  // 清除 photo input ref
})
</script>

<template>
  <main class="page">
    <RouterLink to="/custom/requests" class="back-link">
      <ArrowLeft :size="14" /> 返回申請列表
    </RouterLink>

    <div v-if="detailQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入中…
    </div>
    <div v-else-if="detailQuery.isError.value" class="state error">
      <p>{{ (detailQuery.error.value as Error)?.message ?? '載入失敗' }}</p>
      <button @click="router.push('/custom/requests')">回到列表</button>
    </div>

    <template v-else-if="detail">
      <header class="hd">
        <div class="hd-meta">
          <span class="hd-no">{{ REQUEST_TYPE_LABEL[detail.request_type] }}</span>
          <span class="hd-dot"></span>
          <span class="hd-date">{{ fmtDateTime(detail.created_at) }}</span>
          <span v-if="connected" class="hd-live" title="即時連線中">●</span>
        </div>
        <h1 class="hd-title">客製申請</h1>
        <div class="status" :class="`tone-${statusBanner?.tone ?? 'neutral'}`">
          {{ STATUS_LABEL[detail.status] }}
        </div>
      </header>

      <!-- 狀態 banner -->
      <div v-if="statusBanner" class="banner" :class="`banner-${statusBanner.tone}`">
        <p>{{ statusBanner.text }}</p>
        <p v-if="expiresIn" class="banner-sub">
          <Clock :size="12" /> {{ expiresIn }}
        </p>
        <RouterLink v-if="detail.status === 'quote_confirmed' && detail.order_id"
          :to="{ name: 'order-detail', params: { id: detail.order_id } }"
          class="banner-cta"
        >
          前往訂單付款 →
        </RouterLink>
        <button
          v-if="detail.status === 'quote_expired'"
          class="banner-cta"
          @click="reapplyFromExpired"
        >
          重新申請（預填上次資料） →
        </button>
        <RouterLink
          v-else-if="detail.status === 'quote_rejected'"
          to="/custom"
          class="banner-cta"
        >
          重新申請 →
        </RouterLink>
      </div>

      <!-- 照片預覽 + 重新上傳（quote_pending 才顯示重上傳按鈕）-->
      <section v-if="detail.photo_url" class="photo-block">
        <h2>申請照片</h2>
        <div class="photo-frame">
          <img :src="detail.photo_url.startsWith('http') ? detail.photo_url : ''" alt="申請照片" />
          <p v-if="!detail.photo_url.startsWith('http')" class="photo-private-hint">
            照片已私密儲存（只有您和管理員看得到）
          </p>
        </div>
        <div v-if="isEditable" class="photo-actions">
          <input
            ref="photoInput"
            type="file"
            accept="image/jpeg,image/png"
            class="hidden"
            @change="onPhotoChange"
          />
          <button
            type="button"
            class="btn-ghost"
            :disabled="photoUploading"
            @click="triggerPhotoUpload"
          >
            <Loader2 v-if="photoUploading" :size="14" class="spin" />
            <Upload v-else :size="14" />
            重新上傳照片
          </button>
          <p v-if="photoError" class="error">{{ photoError }}</p>
        </div>
      </section>

      <!-- 申請規格（含 quote_pending 修改 UI）-->
      <section class="spec">
        <div class="spec-hd">
          <h2>申請規格</h2>
          <button v-if="isEditable && !editing" class="btn-ghost-sm" @click="openEdit">
            <Pencil :size="12" /> 修改
          </button>
        </div>

        <!-- 唯讀視圖 -->
        <dl v-if="!editing">
          <div v-if="detail.canvas_w_cm">
            <dt>畫布尺寸</dt>
            <dd>{{ detail.canvas_w_cm }}×{{ detail.canvas_h_cm }} cm</dd>
          </div>
          <div v-else>
            <dt>畫布尺寸</dt>
            <dd class="muted">未指定（讓管理員建議）</dd>
          </div>
          <div>
            <dt>難度</dt>
            <dd v-if="detail.difficulty">{{ DIFFICULTY_LABEL[detail.difficulty as Difficulty] || detail.difficulty }}</dd>
            <dd v-else class="muted">讓管理員建議</dd>
          </div>
          <div v-if="detail.customer_notes">
            <dt>備註</dt>
            <dd class="multiline">{{ detail.customer_notes }}</dd>
          </div>
          <div v-if="detail.quoted_price">
            <dt>報價金額</dt>
            <dd class="price">NT$ {{ detail.quoted_price.toLocaleString() }}</dd>
          </div>
        </dl>

        <!-- 編輯視圖 -->
        <form v-else class="edit-form" @submit.prevent="saveEdit">
          <label class="field-row">
            <span class="field-label">畫布尺寸（cm）</span>
            <span class="field-input-row">
              <input type="number" v-model.number="editForm.canvas_w_cm" min="20" max="120" />
              <span class="cross">×</span>
              <input type="number" v-model.number="editForm.canvas_h_cm" min="20" max="120" />
            </span>
          </label>
          <label class="field-row">
            <span class="field-label">難度</span>
            <select v-model="editForm.difficulty" class="select">
              <option v-for="d in DIFFICULTY_OPTIONS" :key="d.value" :value="d.value">
                {{ d.label }}
              </option>
            </select>
          </label>
          <label class="field-row">
            <span class="field-label">備註</span>
            <textarea v-model="editForm.customer_notes" rows="3" class="textarea"></textarea>
          </label>
          <p v-if="editError" class="error">{{ editError }}</p>
          <div class="edit-actions">
            <button type="button" class="btn-ghost" @click="cancelEdit">取消</button>
            <button type="submit" class="btn-primary-sm" :disabled="editSaving">
              <Loader2 v-if="editSaving" :size="14" class="spin" />
              儲存修改
            </button>
          </div>
        </form>
      </section>

      <!-- 訊息對話 -->
      <section class="thread">
        <h2>對話紀錄</h2>
        <ul ref="messagesEl" class="msgs">
          <li v-if="!detail.messages?.length" class="msgs-empty">目前沒有訊息。</li>
          <li
            v-for="m in detail.messages"
            :key="m.id"
            class="msg"
            :class="m.sender_type === 'customer' ? 'msg-mine' : 'msg-them'"
          >
            <div class="msg-bubble">
              <p class="msg-text">{{ m.message }}</p>
              <a v-if="m.image_url" :href="m.image_url" target="_blank" class="msg-img-link">
                <ImageIcon :size="12" /> 附件圖
              </a>
              <span class="msg-time">{{ fmtDateTime(m.created_at) }}</span>
            </div>
          </li>
        </ul>

        <form
          v-if="['quote_pending', 'negotiating', 'quote_sent', 'draft_revision'].includes(detail.status)"
          class="composer"
          @submit.prevent="sendMessage"
        >
          <textarea
            v-model="draftMessage"
            rows="2"
            placeholder="補充說明或回覆訊息…"
            @keydown.ctrl.enter="sendMessage"
            @keydown.meta.enter="sendMessage"
          ></textarea>
          <button type="submit" :disabled="!draftMessage.trim() || postMsgMut.isPending.value">
            <Loader2 v-if="postMsgMut.isPending.value" :size="14" class="spin" />
            <Send v-else :size="14" :stroke-width="1.5" />
            傳送
          </button>
        </form>
        <p v-if="sendError" class="error">{{ sendError }}</p>
        <p v-else-if="!['quote_pending', 'negotiating', 'quote_sent', 'draft_revision'].includes(detail.status)" class="closed-hint">
          此申請已關閉，無法繼續發訊息。
        </p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.page { max-width: 880px; margin: 0 auto; padding: 32px 24px 96px; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); text-decoration: none; margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.state {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.error { flex-direction: column; }
.state.error button {
  margin-top: 12px; padding: 8px 16px; cursor: pointer;
  border: 1px solid var(--color-line); background: transparent;
  border-radius: var(--radius-xs); color: var(--color-ink-default);
}

.hd { margin-bottom: 24px; }
.hd-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.hd-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); }
.hd-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.hd-date { font-family: var(--font-mono); font-size: 11px; color: var(--color-ink-muted); }
.hd-live { margin-left: auto; color: #5A7A4F; font-size: 10px; animation: pulse 1.5s ease-in-out infinite; }
.hd-title { font-family: var(--font-cn-serif); font-weight: 300; font-size: 32px; letter-spacing: 0.04em; color: var(--color-ink-strong); margin: 0 0 12px; }
.status { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; letter-spacing: 0.06em; border: 1px solid transparent; }
.tone-action { background: var(--color-accent-deep); color: #FCF7E5; }
.tone-ok { background: rgba(122, 156, 110, 0.15); color: #5A7A4F; border-color: rgba(122, 156, 110, 0.3); }
.tone-danger { background: rgba(184, 91, 88, 0.1); color: #B85B58; border-color: rgba(184, 91, 88, 0.25); }
.tone-progress { background: rgba(212, 165, 116, 0.18); color: #8B6232; border-color: rgba(212, 165, 116, 0.35); }
.tone-pending, .tone-neutral { background: var(--color-paper-surface, #FCF7E5); color: var(--color-ink-muted); border-color: var(--color-line); }

.banner {
  margin: 24px 0 32px; padding: 18px 22px;
  border-radius: var(--radius-sm);
  border: 1px solid; display: flex; flex-direction: column; gap: 8px;
}
.banner p { margin: 0; font-size: 14px; line-height: 1.7; }
.banner-sub { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 11px; color: var(--color-ink-muted); }
.banner-cta {
  align-self: flex-start;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 18px; margin-top: 4px; cursor: pointer;
  border: 0; border-radius: var(--radius-xs);
  background: var(--color-accent-deep); color: #FCF7E5;
  font-family: var(--font-cn-serif); font-size: 13px; letter-spacing: 0.06em;
  text-decoration: none;
}
.banner-cta:hover { background: var(--color-accent); }
.banner-action { background: rgba(212, 165, 116, 0.12); border-color: rgba(212, 165, 116, 0.4); color: #8B6232; }
.banner-progress { background: rgba(212, 165, 116, 0.1); border-color: rgba(212, 165, 116, 0.3); }
.banner-ok { background: rgba(122, 156, 110, 0.1); border-color: rgba(122, 156, 110, 0.3); color: #5A7A4F; }
.banner-danger { background: rgba(184, 91, 88, 0.06); border-color: rgba(184, 91, 88, 0.25); color: #B85B58; }
.banner-pending { background: var(--color-paper-surface, #FCF7E5); border-color: var(--color-line); }

.photo-block, .spec, .thread {
  border-top: 1px solid var(--color-line);
  padding-top: 32px; margin-top: 32px;
}
.photo-block h2, .spec h2, .thread h2 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 19px; letter-spacing: 0.04em; margin: 0 0 16px;
  color: var(--color-ink-strong);
}
.spec-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.spec-hd h2 { margin: 0; }

.photo-frame {
  max-width: 480px; aspect-ratio: 4 / 3;
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  overflow: hidden; background: var(--color-paper-surface, #FCF7E5);
  display: flex; align-items: center; justify-content: center;
}
.photo-frame img { width: 100%; height: 100%; object-fit: cover; }
.photo-private-hint {
  font-size: 13px; color: var(--color-ink-muted); padding: 0 24px; text-align: center;
}
.photo-actions { margin-top: 12px; }

.spec dl { display: grid; grid-template-columns: 1fr 2fr; gap: 12px 24px; margin: 0; }
.spec dl > div { display: contents; }
.spec dt {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); padding-top: 2px;
}
.spec dd { font-size: 14px; color: var(--color-ink-strong); margin: 0; }
.spec dd.multiline { white-space: pre-line; }
.spec dd.muted { color: var(--color-ink-muted); font-style: italic; }
.spec dd.price { font-family: var(--font-cn-serif); font-size: 18px; color: var(--color-accent-deep); }

.edit-form { display: flex; flex-direction: column; gap: 16px; }
.field-row { display: flex; flex-direction: column; gap: 8px; }
.field-label { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; color: var(--color-ink-muted); }
.field-input-row { display: flex; align-items: center; gap: 8px; }
.field-input-row input {
  width: 80px; padding: 8px 10px;
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  font-family: var(--font-mono); font-size: 14px;
  text-align: center;
}
.cross { color: var(--color-ink-muted); }
.select, .textarea {
  padding: 8px 10px; font: inherit; font-size: 14px;
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  background: #FFF; color: var(--color-ink-default);
}
.select { max-width: 240px; }
.textarea { resize: vertical; }

.edit-actions { display: flex; gap: 12px; justify-content: flex-end; }

.msgs {
  list-style: none; padding: 16px 4px; margin: 0 0 16px;
  max-height: 400px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 12px;
  background: var(--color-paper-surface, #FCF7E5);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-line);
}
.msgs-empty { padding: 32px; text-align: center; color: var(--color-ink-muted); font-size: 13px; }
.msg { display: flex; }
.msg-mine { justify-content: flex-end; }
.msg-them { justify-content: flex-start; }
.msg-bubble { max-width: 78%; padding: 10px 14px; border-radius: var(--radius-sm); display: flex; flex-direction: column; gap: 6px; }
.msg-mine .msg-bubble { background: var(--color-accent-deep); color: #FCF7E5; }
.msg-them .msg-bubble { background: #FFF; color: var(--color-ink-strong); border: 1px solid var(--color-line); }
.msg-text { margin: 0; font-size: 14px; line-height: 1.6; white-space: pre-line; word-break: break-word; }
.msg-img-link { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: inherit; opacity: 0.85; text-decoration: underline; }
.msg-time { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.1em; opacity: 0.65; }

.composer { display: flex; gap: 8px; align-items: flex-end; }
.composer textarea {
  flex: 1; padding: 10px 12px; resize: none;
  font: inherit; font-size: 14px;
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  background: var(--color-paper-surface, #FCF7E5);
  color: var(--color-ink-default);
}
.composer textarea:focus { outline: none; border-color: var(--color-accent); background: #FFF; }
.composer button {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 10px 16px; border: 0; cursor: pointer;
  background: var(--color-accent-deep); color: #FCF7E5;
  border-radius: var(--radius-xs); font: inherit; font-size: 13px;
}
.composer button:disabled { opacity: 0.5; cursor: not-allowed; }
.composer button:hover:not(:disabled) { background: var(--color-accent); }

.btn-ghost, .btn-ghost-sm {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px; cursor: pointer;
  background: transparent; color: var(--color-ink-default);
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  font-family: inherit; font-size: 13px;
}
.btn-ghost-sm { padding: 4px 10px; font-size: 12px; }
.btn-ghost:hover, .btn-ghost-sm:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary-sm {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 18px; cursor: pointer;
  background: var(--color-accent-deep); color: #FCF7E5;
  border: 0; border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 13px; letter-spacing: 0.04em;
}
.btn-primary-sm:hover:not(:disabled) { background: var(--color-accent); }
.btn-primary-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.error { font-size: 13px; color: #B85B58; margin: 8px 0 0; }
.closed-hint { text-align: center; font-size: 13px; color: var(--color-ink-muted); margin: 0; }

.hidden { display: none; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
