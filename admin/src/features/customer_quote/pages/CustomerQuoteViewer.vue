<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Loader2, ImageOff, AlertTriangle, Eye, Calendar, MessageSquare,
} from 'lucide-vue-next'

const route = useRoute()
const token = computed(() => route.params.token as string)

interface QuoteMessage {
  id: string
  sender_type: 'admin' | 'customer'
  message: string
  image_url: string | null
  created_at: string
}

interface QuoteSummary {
  custom_request_id: string
  spec_summary: {
    canvas_w_cm: number | null
    canvas_h_cm: number | null
    difficulty: string | null
    detail: string | null
    photo_url: string | null
    customer_notes: string | null
  }
  quoted_price: number
  quote_expires_at: string
  is_extended: boolean
  revision_count: number
  messages: QuoteMessage[]
  preview_available: boolean
  view_count: number
  max_views: number
}

const quote = ref<QuoteSummary | null>(null)
const loading = ref(true)
const error = ref<{ message: string; code?: string } | null>(null)
const previewSrc = computed(() =>
  quote.value?.preview_available ? `/api/v1/custom/quote/${token.value}/preview?_v=${quote.value?.view_count}` : null,
)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/v1/custom/quote/${token.value}`, { credentials: 'include' })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      error.value = {
        message: body.message || body.detail || `HTTP ${res.status}`,
        code: body.code,
      }
      return
    }
    quote.value = body
  } catch (e) {
    error.value = { message: (e as Error).message || '載入失敗' }
  } finally {
    loading.value = false
  }
}

onMounted(load)

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtMoney(n: number | null): string {
  if (n == null) return '—'
  return `NT$ ${Number(n).toLocaleString('zh-TW')}`
}

const expiresIn = computed(() => {
  if (!quote.value?.quote_expires_at) return null
  const ms = new Date(quote.value.quote_expires_at).getTime() - Date.now()
  if (ms <= 0) return '已逾期'
  const hours = Math.floor(ms / 3600000)
  const days = Math.floor(hours / 24)
  if (days >= 1) return `剩餘約 ${days} 天`
  return `剩餘約 ${hours} 小時`
})

const isAuthError = computed(() => error.value?.message?.includes('未登入') || error.value?.code === 'UNAUTHORIZED' || error.value?.message?.includes('HTTP 401'))
</script>

<template>
  <div class="min-h-screen bg-paper-canvas">
    <header class="border-b border-line-hairline bg-paper-surface">
      <div class="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
        <div>
          <p class="font-display text-ink-strong text-[20px]">易木工房 YIIMUI</p>
          <p class="text-[12px] text-ink-muted">客製作品報價確認</p>
        </div>
      </div>
    </header>

    <main class="max-w-3xl mx-auto px-6 py-8">
      <!-- Loading -->
      <div v-if="loading" class="py-20 flex flex-col items-center gap-3 text-ink-muted">
        <Loader2 :size="28" :stroke-width="1.5" class="animate-spin" />
        <p class="text-[13px]">載入報價內容…</p>
      </div>

      <!-- Auth required -->
      <div
        v-else-if="error && isAuthError"
        class="py-12 px-6 text-center border border-line-hairline rounded-[var(--radius-sm)] bg-paper-surface"
      >
        <AlertTriangle :size="32" :stroke-width="1.25" class="text-state-warning mx-auto mb-3" />
        <p class="text-[15px] text-ink-strong mb-2">請先登入您的帳號</p>
        <p class="text-[13px] text-ink-muted mb-5">為保護您的客製設計不被外流，需驗證您的身份才能查看報價內容。</p>
        <a
          :href="`/admin/login?next=${encodeURIComponent(route.fullPath)}`"
          class="inline-flex items-center justify-center px-4 py-2 rounded-[var(--radius-xs)] bg-accent text-paper-surface text-[13px] font-medium hover:opacity-90"
        >前往登入</a>
      </div>

      <!-- Expired / view-limit -->
      <div
        v-else-if="error"
        class="py-12 px-6 text-center border border-state-danger/40 rounded-[var(--radius-sm)] bg-[var(--color-state-danger)]/[0.04]"
      >
        <AlertTriangle :size="32" :stroke-width="1.25" class="text-state-danger mx-auto mb-3" />
        <p class="text-[15px] text-ink-strong mb-2">{{ error.code === 'QUOTE_VIEW_LIMIT_REACHED' ? '查看次數已達上限' : '報價已失效' }}</p>
        <p class="text-[13px] text-ink-muted">{{ error.message }}</p>
        <p class="text-[12px] text-ink-muted mt-3">請聯絡 易木工房 客服協助</p>
      </div>

      <!-- Quote -->
      <div v-else-if="quote" class="space-y-5">
        <!-- View tracking pill -->
        <div class="flex items-center justify-between text-[12px] text-ink-muted">
          <span class="inline-flex items-center gap-1">
            <Eye :size="12" :stroke-width="1.5" />
            您已查看 {{ quote.view_count }} / {{ quote.max_views }} 次
          </span>
          <span v-if="expiresIn" class="inline-flex items-center gap-1">
            <Calendar :size="12" :stroke-width="1.5" />
            {{ expiresIn }}
          </span>
        </div>

        <!-- Preview image -->
        <div
          v-if="quote.preview_available"
          class="rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-surface select-none"
          oncontextmenu="return false"
        >
          <div class="px-4 py-2.5 border-b border-line-hairline bg-paper-subtle text-[12px] text-ink-muted">
            作品預覽（為保護您的客製設計，此圖片帶有浮水印且為低解析度版本）
          </div>
          <img
            v-if="previewSrc"
            :src="previewSrc"
            alt="客製預覽"
            class="block w-full"
            draggable="false"
          />
        </div>
        <div
          v-else
          class="rounded-[var(--radius-sm)] border border-line-hairline px-6 py-10 text-center bg-paper-surface"
        >
          <ImageOff :size="32" :stroke-width="1.25" class="text-ink-muted mx-auto mb-2" />
          <p class="text-[13px] text-ink-muted">作品預覽製作中，目前僅有報價資訊</p>
        </div>

        <!-- Quote summary -->
        <div class="rounded-[var(--radius-sm)] border border-line-hairline bg-paper-surface p-5 space-y-3">
          <div class="flex items-baseline justify-between">
            <p class="text-[13px] text-ink-muted">報價金額</p>
            <p class="font-display text-ink-strong text-[28px]">{{ fmtMoney(quote.quoted_price) }}</p>
          </div>
          <dl class="grid grid-cols-2 gap-3 text-[13px] pt-3 border-t border-line-hairline">
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">畫布</dt>
              <dd class="text-ink-default mt-0.5">
                {{ quote.spec_summary.canvas_w_cm ?? '—' }} × {{ quote.spec_summary.canvas_h_cm ?? '—' }} cm
              </dd>
            </div>
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">難易度</dt>
              <dd class="text-ink-default mt-0.5">{{ quote.spec_summary.difficulty ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">細緻度</dt>
              <dd class="text-ink-default mt-0.5">{{ quote.spec_summary.detail ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-[11px] text-ink-muted tracking-[0.04em] uppercase">修改次數</dt>
              <dd class="text-ink-default mt-0.5">{{ quote.revision_count }} / 3</dd>
            </div>
          </dl>
          <div v-if="quote.spec_summary.customer_notes" class="pt-3 border-t border-line-hairline">
            <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-1">您的需求</p>
            <p class="text-[13px] whitespace-pre-line">{{ quote.spec_summary.customer_notes }}</p>
          </div>
        </div>

        <!-- Messages -->
        <div class="rounded-[var(--radius-sm)] border border-line-hairline bg-paper-surface p-5">
          <div class="flex items-center gap-2 mb-3">
            <MessageSquare :size="14" :stroke-width="1.5" class="text-ink-muted" />
            <h2 class="font-display text-ink-strong text-[16px]">與工房對話 ({{ quote.messages.length }})</h2>
          </div>
          <ul v-if="quote.messages.length > 0" class="space-y-3 max-h-[400px] overflow-y-auto">
            <li
              v-for="m in quote.messages"
              :key="m.id"
              class="flex"
              :class="m.sender_type === 'customer' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] px-3 py-2 rounded-[var(--radius-sm)] text-[13px]"
                :class="m.sender_type === 'customer'
                  ? 'bg-accent text-paper-surface'
                  : 'bg-paper-subtle text-ink-default border border-line-hairline'"
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
                    alt="附件"
                    class="max-w-[260px] max-h-[200px] rounded-[var(--radius-xs)] object-contain bg-paper-surface"
                    draggable="false"
                  />
                </a>
                <p v-if="m.message" class="whitespace-pre-line">{{ m.message }}</p>
                <p
                  class="mt-1 text-[10px] tracking-[0.04em]"
                  :class="m.sender_type === 'customer' ? 'text-paper-surface/70' : 'text-ink-muted'"
                >
                  {{ m.sender_type === 'customer' ? '您' : '工房' }} · {{ fmtDateTime(m.created_at) }}
                </p>
              </div>
            </li>
          </ul>
          <p v-else class="text-[13px] text-ink-muted text-center py-4">尚無對話</p>
        </div>

        <!-- Actions -->
        <div class="rounded-[var(--radius-sm)] border border-line-hairline bg-paper-subtle p-5 text-center">
          <p class="text-[13px] text-ink-muted mb-4">
            ※ 點選「確認接單」後將建立訂單並進入付款流程；如有疑問請聯絡客服。
          </p>
          <p class="text-[12px] text-ink-muted">
            （確認/拒絕/要求修改按鈕仍由現有 customer-side API 處理，本頁尚未串接動作 — 之後接入店家前台時補）
          </p>
        </div>

        <p class="text-[11px] text-ink-muted text-center mt-6">
          本頁面內容為您專屬，請勿轉發給第三方；圖片帶追溯浮水印，外流可由工房追蹤。
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
img { user-drag: none; -webkit-user-drag: none; }
</style>
