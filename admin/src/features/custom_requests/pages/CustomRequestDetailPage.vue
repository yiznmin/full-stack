<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  MessageSquare,
  Send,
  Quote,
  CheckCircle2,
  ImageIcon,
  ExternalLink,
  Link as LinkIcon,
} from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'
import Textarea from '@/shared/ui/Textarea.vue'

import CustomStatusBadge from '../components/CustomStatusBadge.vue'
import QuoteDialog from '../components/QuoteDialog.vue'
import {
  fetchPhotoSignedUrl,
  useCustomRequestQuery,
  useMarkNegotiatingMutation,
  usePostMessageMutation,
  usePostQuoteMutation,
} from '../queries'
import type { CustomStatus, QuotePayload } from '../api'

const route = useRoute()
const router = useRouter()

const requestId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))

const { data: req, isLoading, isError, error } = useCustomRequestQuery(requestId)

const markNeg = useMarkNegotiatingMutation(requestId.value)
const postMsg = usePostMessageMutation(requestId.value)
const postQuote = usePostQuoteMutation(requestId.value)

const apiError = ref<string | null>(null)

function handleApiError(e: unknown, fallback = '操作失敗') {
  const err = e as { status?: number; message?: string }
  if (err.message?.includes('狀態') || err.status === 409) {
    apiError.value = '申請狀態已被其他人變更，已重新載入。'
  } else {
    apiError.value = err.message || fallback
  }
}

// ── Header actions ────────────────────────────────────────────────────
const canMarkNegotiating = computed(() => req.value?.status === 'quote_pending')
const canQuote = computed(
  () =>
    !!req.value &&
    ['quote_pending', 'negotiating', 'draft_revision'].includes(req.value.status),
)

const quoteOpen = ref(false)

async function doMarkNegotiating() {
  apiError.value = null
  try {
    await markNeg.mutateAsync()
  } catch (e) {
    handleApiError(e, '標記失敗')
  }
}

async function doQuote(payload: QuotePayload) {
  apiError.value = null
  try {
    await postQuote.mutateAsync(payload)
    quoteOpen.value = false
  } catch (e) {
    handleApiError(e, '送出報價失敗')
    quoteOpen.value = false
  }
}

// ── Messages ──────────────────────────────────────────────────────────
const messageInput = ref('')
const messageError = ref<string | null>(null)

async function sendMessage() {
  const m = messageInput.value.trim()
  if (!m) {
    messageError.value = '訊息不可為空'
    return
  }
  messageError.value = null
  try {
    await postMsg.mutateAsync({ message: m })
    messageInput.value = ''
  } catch (e) {
    handleApiError(e, '訊息傳送失敗')
  }
}

// ── Photo download ────────────────────────────────────────────────────
const photoLoading = ref(false)
async function downloadPhoto() {
  if (!req.value) return
  photoLoading.value = true
  try {
    const r = await fetchPhotoSignedUrl(req.value.id)
    window.open(r.url, '_blank', 'noopener')
  } catch (e) {
    handleApiError(e, '取得圖片連結失敗')
  } finally {
    photoLoading.value = false
  }
}

// ── Format helpers ────────────────────────────────────────────────────
function fmtMoney(n: number | null): string {
  if (n == null) return '—'
  return `NT$ ${Number(n).toLocaleString('zh-TW')}`
}
function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const requestTypeLabel = computed(() => {
  const t = req.value?.request_type
  return t === 'custom_photo' ? '客製照片' : t === 'custom_spec' ? '客製規格' : '—'
})
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/custom-requests')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回客製訂單列表
    </button>
  </div>

  <div v-if="isLoading" class="flex items-center justify-center py-20 text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    <span class="ml-2 text-[13px]">載入中...</span>
  </div>

  <div
    v-else-if="isError"
    class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗：{{ (error as { message?: string })?.message ?? '申請不存在' }}
  </div>

  <template v-else-if="req">
    <header class="mb-7 pb-5 border-b border-line-hairline flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2 flex-wrap">
          <h1 class="font-display text-ink-strong text-[24px] leading-[32px] tracking-[-0.005em]">
            客製申請
            <span class="font-mono text-[20px] ml-1">#{{ req.id.slice(0, 8) }}</span>
          </h1>
          <CustomStatusBadge :status="req.status as CustomStatus" />
          <span
            class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-paper-subtle text-ink-default"
            title="修改次數"
          >
            修改 {{ req.revision_count }} / 3
          </span>
          <span
            class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-paper-subtle text-ink-default"
          >
            {{ requestTypeLabel }}
          </span>
        </div>
        <p class="mt-1 text-[13px] text-ink-muted">建立於 {{ fmtDateTime(req.created_at) }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <Button v-if="canMarkNegotiating" variant="secondary" :disabled="markNeg.isPending.value" @click="doMarkNegotiating">
          <Loader2 v-if="markNeg.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
          標記洽談中
        </Button>
        <Button v-if="canQuote" variant="primary" @click="quoteOpen = true">
          <Quote :size="14" :stroke-width="1.5" />
          {{ req.status === 'draft_revision' ? '重新送報價' : '送出報價' }}
        </Button>
      </div>
    </header>

    <div
      v-if="apiError"
      class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
    >
      <span class="flex-1">{{ apiError }}</span>
      <button class="text-[12px] underline" @click="apiError = null">關閉</button>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- Main column -->
      <div class="lg:col-span-2 space-y-5">
        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">申請內容</h2>
          <dl class="grid grid-cols-2 gap-3 text-[13px]">
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">畫布</dt>
              <dd class="text-ink-default mt-0.5">
                {{ req.canvas_w_cm || '—' }} × {{ req.canvas_h_cm || '—' }} cm
              </dd>
            </div>
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">難易度</dt>
              <dd class="text-ink-default mt-0.5">{{ req.difficulty || '—' }}</dd>
            </div>
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">細緻度</dt>
              <dd class="text-ink-default mt-0.5">{{ req.detail || '—' }}</dd>
            </div>
            <div v-if="req.parent_request_id">
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">原申請</dt>
              <dd class="mt-0.5">
                <button
                  type="button"
                  class="text-accent hover:text-accent-hover inline-flex items-center gap-1 font-mono text-[12px]"
                  @click="router.push(`/admin/custom-requests/${req.parent_request_id}`)"
                >
                  <LinkIcon :size="12" :stroke-width="1.5" />
                  #{{ req.parent_request_id.slice(0, 8) }}
                </button>
              </dd>
            </div>
            <div v-if="req.order_id">
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">建立的訂單</dt>
              <dd class="mt-0.5">
                <button
                  type="button"
                  class="text-accent hover:text-accent-hover inline-flex items-center gap-1 font-mono text-[12px]"
                  @click="router.push(`/admin/orders/${req.order_id}`)"
                >
                  <LinkIcon :size="12" :stroke-width="1.5" />
                  訂單詳情
                </button>
              </dd>
            </div>
          </dl>
          <div v-if="req.customer_notes" class="mt-4 pt-4 border-t border-line-hairline">
            <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-1">客戶備註</p>
            <p class="text-[13px] text-ink-default whitespace-pre-line">{{ req.customer_notes }}</p>
          </div>
        </Card>

        <Card v-if="req.photo_url">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">客戶照片</h2>
            <Button variant="secondary" :disabled="photoLoading" @click="downloadPhoto">
              <Loader2 v-if="photoLoading" :size="14" :stroke-width="1.5" class="animate-spin" />
              <ExternalLink v-else :size="14" :stroke-width="1.5" />
              開新分頁查看原圖
            </Button>
          </div>
          <div
            class="aspect-[4/3] rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center"
          >
            <ImageIcon :size="40" :stroke-width="1.25" class="text-ink-muted" />
          </div>
          <p class="mt-2 text-[11px] text-ink-muted">點按上方按鈕透過 15 分鐘簽章 URL 取得原圖</p>
        </Card>

        <!-- Messages -->
        <Card>
          <div class="flex items-center justify-between mb-4">
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">訊息對話</h2>
            <span class="inline-flex items-center gap-1 text-[12px] text-ink-muted">
              <MessageSquare :size="12" :stroke-width="1.5" />
              {{ req.messages.length }} 則
            </span>
          </div>

          <div
            v-if="req.messages.length === 0"
            class="text-[13px] text-ink-muted text-center py-8"
          >
            尚無訊息
          </div>
          <ul v-else class="space-y-3 mb-4 max-h-[460px] overflow-y-auto">
            <li
              v-for="m in req.messages"
              :key="m.id"
              class="flex"
              :class="m.sender_type === 'admin' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] px-3 py-2 rounded-[var(--radius-sm)] text-[13px]"
                :class="
                  m.sender_type === 'admin'
                    ? 'bg-accent text-paper-surface'
                    : 'bg-paper-subtle text-ink-default border border-line-hairline'
                "
              >
                <p class="whitespace-pre-line">{{ m.message }}</p>
                <p
                  class="mt-1 text-[10px] tracking-[0.04em]"
                  :class="m.sender_type === 'admin' ? 'text-paper-surface/70' : 'text-ink-muted'"
                >
                  {{ m.sender_type === 'admin' ? '管理員' : '客戶' }} · {{ fmtDateTime(m.created_at) }}
                </p>
              </div>
            </li>
          </ul>

          <div class="space-y-2">
            <Textarea
              v-model="messageInput"
              :rows="3"
              :maxlength="2000"
              placeholder="輸入訊息給客戶...（Shift+Enter 換行，Enter 送出）"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <div class="flex items-center justify-between">
              <p v-if="messageError" class="text-[12px] text-state-danger">{{ messageError }}</p>
              <p v-else class="text-[11px] text-ink-muted">{{ messageInput.length }} / 2000</p>
              <Button variant="primary" :disabled="postMsg.isPending.value || !messageInput.trim()" @click="sendMessage">
                <Loader2 v-if="postMsg.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
                <Send v-else :size="14" :stroke-width="1.5" />
                送出
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <!-- Side column -->
      <div class="space-y-5">
        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">客戶</h2>
          <p class="text-[13px] text-ink-strong">{{ req.user_name }}</p>
          <p class="text-[12px] text-ink-muted">{{ req.user_email }}</p>
        </Card>

        <Card v-if="req.quoted_price">
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">已送報價</h2>
          <dl class="text-[13px] space-y-1.5">
            <div class="flex justify-between">
              <dt class="text-ink-muted">金額</dt>
              <dd class="font-mono text-ink-strong">{{ fmtMoney(req.quoted_price) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-ink-muted">送出時間</dt>
              <dd class="font-mono text-[12px]">{{ fmtDateTime(req.quoted_at) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-ink-muted">有效期至</dt>
              <dd class="font-mono text-[12px]">{{ fmtDateTime(req.quote_expires_at) }}</dd>
            </div>
            <div v-if="req.is_extended" class="flex justify-between">
              <dt class="text-ink-muted">客戶延長</dt>
              <dd class="text-state-info">已延長</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">時間軸</h2>
          <ul class="text-[12px] space-y-1.5">
            <li class="flex justify-between"><span class="text-ink-muted">建立</span><span class="font-mono">{{ fmtDateTime(req.created_at) }}</span></li>
            <li v-if="req.quoted_at" class="flex justify-between"><span class="text-ink-muted">報價送出</span><span class="font-mono">{{ fmtDateTime(req.quoted_at) }}</span></li>
            <li v-if="req.rejected_at" class="flex justify-between"><span class="text-ink-muted">已拒絕</span><span class="font-mono">{{ fmtDateTime(req.rejected_at) }}</span></li>
          </ul>
        </Card>

        <Card v-if="req.admin_notes">
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">內部備註</h2>
          <p class="text-[12px] text-ink-default whitespace-pre-line">{{ req.admin_notes }}</p>
        </Card>
      </div>
    </div>

    <QuoteDialog
      :open="quoteOpen"
      :request="req"
      :pending="postQuote.isPending.value"
      @close="quoteOpen = false"
      @confirm="(p) => doQuote(p)"
    />
  </template>
</template>
