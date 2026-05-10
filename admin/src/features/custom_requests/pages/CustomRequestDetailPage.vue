<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  MessageSquare,
  Send,
  Quote,
  ImageOff,
  ExternalLink,
  Link as LinkIcon,
  Wrench,
  Paperclip,
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
// 「前往製作」：在「未確認報價」前的狀態都可以再跑 production_job 預覽
const canGoToProduction = computed(
  () =>
    !!req.value &&
    req.value.request_type === 'custom_photo' &&
    ['quote_pending', 'negotiating', 'draft_revision'].includes(req.value.status),
)

function goToProduction() {
  if (!req.value) return
  router.push({
    path: '/admin/production/new',
    query: { customRequestId: req.value.id },
  })
}

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
const messageImageUrl = ref<string | null>(null)
const messageImageUploading = ref(false)
const messageError = ref<string | null>(null)
const messageFileInput = ref<HTMLInputElement | null>(null)

async function onPickMessageImage(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    messageError.value = '圖片超過 10MB'
    return
  }
  if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
    messageError.value = '只接受 JPEG / PNG'
    return
  }
  messageError.value = null
  messageImageUploading.value = true
  try {
    // 沿用 product features 的通用上傳（走 Firebase signed URL）
    const { uploadFile } = await import('@/features/products/api')
    const url = await uploadFile(file)
    messageImageUrl.value = url
  } catch (err) {
    messageError.value = (err as { message?: string }).message || '圖片上傳失敗'
  } finally {
    messageImageUploading.value = false
    if (messageFileInput.value) messageFileInput.value.value = ''
  }
}

function clearMessageImage() {
  messageImageUrl.value = null
}

async function sendMessage() {
  const m = messageInput.value.trim()
  // 純文字 OR 純圖片 OR 兩者都有 都允許；兩者皆空才拒絕
  if (!m && !messageImageUrl.value) {
    messageError.value = '請輸入文字或附上圖片'
    return
  }
  messageError.value = null
  try {
    await postMsg.mutateAsync({ message: m, image_url: messageImageUrl.value })
    messageInput.value = ''
    messageImageUrl.value = null
  } catch (e) {
    handleApiError(e, '訊息傳送失敗')
  }
}

// ── Photo signed URL（inline 顯示 + 開新分頁）─────────────────────────
// 後端會把 photo_url 設為 null 強迫走 signed URL endpoint（安全）。
// 我們對 custom_photo 申請直接打一次拿 signed URL；404 = 真的沒上傳照片。
const photoUrl = ref<string | null>(null)
const photoLoading = ref(false)
const photoLoadFailed = ref(false)
const photoMissing = ref(false)

watch(
  () => req.value?.id,
  async (id) => {
    photoUrl.value = null
    photoLoadFailed.value = false
    photoMissing.value = false
    if (!id || req.value?.request_type !== 'custom_photo') return
    photoLoading.value = true
    try {
      const r = await fetchPhotoSignedUrl(id)
      photoUrl.value = r.url
    } catch (e) {
      const err = e as { status?: number }
      if (err.status === 404) photoMissing.value = true
      else handleApiError(e, '取得圖片連結失敗')
    } finally {
      photoLoading.value = false
    }
  },
  { immediate: true },
)

function openInNewTab() {
  if (photoUrl.value) window.open(photoUrl.value, '_blank', 'noopener')
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
        <Button v-if="canGoToProduction" variant="secondary" @click="goToProduction">
          <Wrench :size="14" :stroke-width="1.5" />
          前往製作
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
          <div class="mt-4 pt-4 border-t border-line-hairline">
            <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-1">展示授權</p>
            <div
              :class="[
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-[12px] tracking-[0.04em]',
                req.display_consent
                  ? 'bg-fresh-tint border-fresh text-fresh font-medium'
                  : 'bg-paper-deep border-line-subtle text-ink-muted',
              ]"
            >
              <span class="text-[14px]">{{ req.display_consent ? '✓' : '○' }}</span>
              <span>{{ req.display_consent ? '已同意作品於 IG / 網站案例展示' : '未同意展示（不可公開使用）' }}</span>
            </div>
          </div>
        </Card>

        <Card v-if="req.request_type === 'custom_photo'">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">客戶照片</h2>
            <Button
              variant="secondary"
              :disabled="!photoUrl"
              @click="openInNewTab"
            >
              <ExternalLink :size="14" :stroke-width="1.5" />
              開新分頁
            </Button>
          </div>
          <div
            class="aspect-[4/3] rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center"
          >
            <Loader2
              v-if="photoLoading"
              :size="32"
              :stroke-width="1.5"
              class="animate-spin text-ink-muted"
            />
            <img
              v-else-if="photoUrl && !photoLoadFailed"
              :src="photoUrl"
              alt="客戶上傳照片"
              class="w-full h-full object-contain bg-paper-surface"
              @error="photoLoadFailed = true"
            />
            <div v-else-if="photoMissing" class="text-center px-4 text-ink-muted">
              <ImageOff :size="32" :stroke-width="1.25" class="mx-auto mb-2" />
              <p class="text-[12px]">客戶尚未上傳照片</p>
            </div>
            <div v-else class="text-center px-4 text-ink-muted">
              <ImageOff :size="32" :stroke-width="1.25" class="mx-auto mb-2" />
              <p class="text-[12px]">圖片無法顯示（簽章 URL 已過期或檔案不存在）</p>
            </div>
          </div>
          <p class="mt-2 text-[11px] text-ink-muted">
            簽章 URL 有效期 15 分鐘，重新整理頁面即可取得新連結
          </p>
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
                <a
                  v-if="m.image_url"
                  :href="m.image_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="block mb-1.5"
                >
                  <img
                    :src="m.image_url"
                    alt="附件圖片"
                    class="max-w-[260px] max-h-[200px] rounded-[var(--radius-xs)] object-contain bg-paper-surface"
                  />
                </a>
                <p v-if="m.message" class="whitespace-pre-line">{{ m.message }}</p>
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
            <input
              ref="messageFileInput"
              type="file"
              accept="image/jpeg,image/png"
              class="hidden"
              @change="onPickMessageImage"
            />
            <!-- 已選圖片預覽 -->
            <div
              v-if="messageImageUrl"
              class="inline-flex items-center gap-2 px-2 py-1.5 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle"
            >
              <img :src="messageImageUrl" alt="附件" class="w-12 h-12 object-cover rounded" />
              <span class="text-[11px] text-ink-muted">已附圖片</span>
              <button
                type="button"
                class="text-[11px] text-state-danger hover:underline"
                @click="clearMessageImage"
              >移除</button>
            </div>
            <Textarea
              v-model="messageInput"
              :rows="3"
              :maxlength="2000"
              placeholder="輸入訊息給客戶...（Shift+Enter 換行，Enter 送出）"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <div class="flex items-center justify-between gap-2">
              <p v-if="messageError" class="text-[12px] text-state-danger flex-1">{{ messageError }}</p>
              <p v-else class="text-[11px] text-ink-muted flex-1">{{ messageInput.length }} / 2000</p>
              <button
                type="button"
                class="h-9 px-3 inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] border border-line-strong text-[13px] text-ink-default hover:bg-paper-subtle disabled:opacity-50"
                :disabled="messageImageUploading"
                @click="messageFileInput?.click()"
              >
                <Loader2 v-if="messageImageUploading" :size="14" :stroke-width="1.5" class="animate-spin" />
                <Paperclip v-else :size="14" :stroke-width="1.5" />
                附圖
              </button>
              <Button variant="primary" :disabled="postMsg.isPending.value || (!messageInput.trim() && !messageImageUrl)" @click="sendMessage">
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

        <Card v-if="req.status === 'quote_sent'">
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">客戶查看追蹤</h2>
          <dl class="text-[13px] space-y-1.5">
            <div class="flex justify-between">
              <dt class="text-ink-muted">已查看</dt>
              <dd class="font-mono">
                <span :class="req.view_count >= 8 ? 'text-state-warning' : 'text-ink-strong'">
                  {{ req.view_count }}
                </span>
                / 10 次
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-ink-muted">最後查看</dt>
              <dd class="font-mono text-[12px]">{{ fmtDateTime(req.last_viewed_at) }}</dd>
            </div>
          </dl>
          <p class="mt-3 pt-3 border-t border-line-hairline text-[11px] text-ink-muted leading-relaxed">
            客戶看到的是浮水印降解析度版（800px）+ 客戶 email 縮寫追溯標記，
            連結附帶 token；過期、超過 10 次查看後自動失效。
          </p>
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
