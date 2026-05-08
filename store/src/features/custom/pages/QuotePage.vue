<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  ArrowLeft, CheckCircle2, Clock, Loader2, MapPin, RefreshCcw, Store as StoreIcon, X,
} from 'lucide-vue-next'
import {
  useQuoteSummaryQuery,
  useConfirmQuoteMutation,
  useRejectQuoteMutation,
  useExtendQuoteMutation,
  useRequestRevisionMutation,
} from '../queries'
import * as profileApi from '@/features/profile/api'
import { quotePreviewUrl, type ApiError } from '../api'

const route = useRoute()
const router = useRouter()
const token = computed(() => route.params.token as string)

const summaryQuery = useQuoteSummaryQuery(token)
const summary = computed(() => summaryQuery.data.value)

// Shipping profiles
const profilesQuery = useQuery({
  queryKey: ['shipping-profiles'] as const,
  queryFn: profileApi.listShippingProfiles,
})

const confirmMut = useConfirmQuoteMutation()
const rejectMut = useRejectQuoteMutation()
const extendMut = useExtendQuoteMutation()
const reviseMut = useRequestRevisionMutation()

// Modal states
const showConfirm = ref(false)
const showReject = ref(false)
const showRevise = ref(false)
const selectedProfileId = ref<string | null>(null)
const rejectReason = ref('')
const reviseReason = ref('')
const actionError = ref<string | null>(null)

// 倒數計時（reactive 每秒更新）
const now = ref(Date.now())
setInterval(() => { now.value = Date.now() }, 1000)
const expiresIn = computed(() => {
  if (!summary.value?.quote_expires_at) return null
  const ms = new Date(summary.value.quote_expires_at).getTime() - now.value
  if (ms <= 0) return null
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  const s = Math.floor((ms % 60_000) / 1000)
  return { h, m, s }
})

const isExpired = computed(() => {
  if (!summary.value) return false
  if (summary.value.view_count >= summary.value.max_views) return true
  return !expiresIn.value
})

// 預設選第一個地址（is_default 優先）
const defaultProfile = computed(() => {
  const profiles = profilesQuery.data.value ?? []
  return profiles.find((p) => p.is_default) ?? profiles[0] ?? null
})
function openConfirm() {
  selectedProfileId.value = defaultProfile.value?.id ?? null
  actionError.value = null
  showConfirm.value = true
}

async function doConfirm() {
  if (!selectedProfileId.value) {
    actionError.value = '請選擇配送資料'
    return
  }
  actionError.value = null
  try {
    const order = await confirmMut.mutateAsync({
      token: token.value,
      shipping_profile_id: selectedProfileId.value,
    })
    showConfirm.value = false
    router.replace({ name: 'order-detail', params: { id: order.order_id } })
  } catch (e) {
    actionError.value = (e as Error).message || '送出失敗'
  }
}

async function doReject() {
  actionError.value = null
  try {
    await rejectMut.mutateAsync({
      token: token.value,
      reason: rejectReason.value.trim() || null,
    })
    showReject.value = false
    rejectReason.value = ''
  } catch (e) {
    actionError.value = (e as Error).message || '送出失敗'
  }
}

async function doExtend() {
  actionError.value = null
  try {
    await extendMut.mutateAsync(token.value)
  } catch (e) {
    actionError.value = (e as Error).message || '延長失敗'
  }
}

async function doRevise() {
  if (!reviseReason.value.trim()) {
    actionError.value = '請說明希望調整的方向'
    return
  }
  actionError.value = null
  try {
    await reviseMut.mutateAsync({
      token: token.value,
      reason: reviseReason.value.trim(),
    })
    showRevise.value = false
    reviseReason.value = ''
    // 修改成功 → request 切到 draft_revision，回 detail 頁
    router.replace({
      name: 'custom-request-detail',
      params: { id: summary.value!.custom_request_id },
    })
  } catch (e) {
    actionError.value = (e as Error).message || '送出失敗'
  }
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('zh-TW', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// 410 / 404 → 直接顯示「報價已失效」
const failedReason = computed<string | null>(() => {
  const err = summaryQuery.error.value as ApiError | null
  if (!err) return null
  if (err.status === 410) {
    if (err.code === 'QUOTE_VIEW_LIMIT_REACHED') return '此報價已超過查看次數上限。'
    return '此報價已失效或已逾期。'
  }
  if (err.status === 404) return '報價連結無效。'
  return err.message || '無法載入報價'
})

// reject reasons quick buttons
const REJECT_REASONS = [
  '價格超出預期',
  '不需要了',
  '改用其他方案',
  '其他',
]

const REVISE_REASONS = [
  '想調整尺寸',
  '希望提高 / 降低難度',
  '想改變線稿精細度',
  '其他細節調整',
]

function canExtend() {
  return !summary.value?.is_extended && !isExpired.value
}
</script>

<template>
  <main class="page">
    <!-- ── 載入 ──────────────────────────────────────────────── -->
    <div v-if="summaryQuery.isPending.value" class="state">
      <Loader2 :size="24" class="spin" /> 載入報價中…
    </div>

    <!-- ── 失效 / 錯誤 ───────────────────────────────────────── -->
    <div v-else-if="failedReason" class="state error">
      <X :size="32" class="error-icon" />
      <h1>{{ failedReason }}</h1>
      <p class="error-hint">如仍想下單，請從客製申請頁重新發起。</p>
      <RouterLink to="/custom" class="cta">重新申請 →</RouterLink>
    </div>

    <!-- ── 報價內容 ──────────────────────────────────────────── -->
    <template v-else-if="summary">
      <RouterLink to="/custom/requests" class="back">
        <ArrowLeft :size="14" /> 我的申請
      </RouterLink>

      <header class="hd">
        <div class="kicker">
          <span class="kicker-no">No. 08</span>
          <span class="kicker-dot"></span>
          <span class="kicker-chapter">Quote · 報價確認</span>
        </div>
        <h1>客製作品報價</h1>
        <div class="hd-meta">
          <span><Clock :size="13" /> 將於 {{ fmtDateTime(summary.quote_expires_at) }} 過期</span>
          <span class="view-count">查看 {{ summary.view_count }} / {{ summary.max_views }}</span>
        </div>
      </header>

      <!-- 倒數 -->
      <div v-if="expiresIn && !isExpired" class="countdown">
        <span class="countdown-label">距離到期</span>
        <div class="countdown-time">
          <span class="cd-cell">
            <span class="cd-num">{{ String(expiresIn.h).padStart(2, '0') }}</span>
            <span class="cd-lbl">時</span>
          </span>
          <span class="cd-sep">:</span>
          <span class="cd-cell">
            <span class="cd-num">{{ String(expiresIn.m).padStart(2, '0') }}</span>
            <span class="cd-lbl">分</span>
          </span>
          <span class="cd-sep">:</span>
          <span class="cd-cell">
            <span class="cd-num">{{ String(expiresIn.s).padStart(2, '0') }}</span>
            <span class="cd-lbl">秒</span>
          </span>
        </div>
        <button
          v-if="canExtend()"
          class="extend-btn"
          :disabled="extendMut.isPending.value"
          @click="doExtend"
        >
          <Loader2 v-if="extendMut.isPending.value" :size="12" class="spin" />
          <RefreshCcw v-else :size="12" />
          延長 24 小時（限 1 次）
        </button>
        <p v-else-if="summary.is_extended" class="extended-hint">已使用過延長</p>
      </div>

      <!-- 預覽圖 -->
      <section v-if="summary.preview_available" class="preview">
        <h2>預覽（降解析度浮水印）</h2>
        <div class="preview-frame">
          <img :src="quotePreviewUrl(token)" alt="預覽" />
        </div>
        <p class="preview-hint">
          完成付款後，您將取得高解析度、無浮水印的原檔。
        </p>
      </section>

      <!-- 規格摘要 -->
      <section class="spec">
        <h2>作品規格</h2>
        <dl>
          <div v-if="summary.spec_summary.canvas_w_cm">
            <dt>畫布尺寸</dt>
            <dd>{{ summary.spec_summary.canvas_w_cm }}×{{ summary.spec_summary.canvas_h_cm }} cm</dd>
          </div>
          <div v-if="summary.spec_summary.difficulty">
            <dt>難度</dt>
            <dd>{{ summary.spec_summary.difficulty }}</dd>
          </div>
          <div v-if="summary.spec_summary.detail">
            <dt>線稿精細度</dt>
            <dd>{{ summary.spec_summary.detail }}</dd>
          </div>
          <div v-if="summary.spec_summary.customer_notes">
            <dt>您的備註</dt>
            <dd class="multiline">{{ summary.spec_summary.customer_notes }}</dd>
          </div>
        </dl>
      </section>

      <!-- 報價金額 -->
      <section class="price">
        <div class="price-row">
          <span>報價金額</span>
          <strong>NT$ {{ summary.quoted_price.toLocaleString() }}</strong>
        </div>
        <p class="price-hint">不含運費；運費依配送方式計算（宅配 NT$ 120 / 超商 NT$ 70）。</p>
      </section>

      <!-- 對話紀錄（read-only） -->
      <section v-if="summary.messages.length > 0" class="thread">
        <h2>對話紀錄</h2>
        <ul class="msgs">
          <li
            v-for="m in summary.messages"
            :key="m.id"
            class="msg"
            :class="m.sender_type === 'customer' ? 'msg-mine' : 'msg-them'"
          >
            <div class="msg-bubble">
              <p>{{ m.message }}</p>
              <span class="msg-time">{{ fmtDateTime(m.created_at) }}</span>
            </div>
          </li>
        </ul>
      </section>

      <!-- 操作按鈕 -->
      <section class="actions" v-if="!isExpired">
        <button class="btn-primary" @click="openConfirm">
          <CheckCircle2 :size="16" :stroke-width="1.5" /> 確認報價並下單
        </button>
        <button class="btn-secondary" @click="showRevise = true">
          要求修改（剩餘 {{ 3 - summary.revision_count }} 次）
        </button>
        <button class="btn-tertiary" @click="showReject = true">
          拒絕此報價
        </button>
      </section>
    </template>

    <!-- ── 確認下單 modal ────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showConfirm" class="modal-overlay" @click.self="showConfirm = false">
        <div class="modal">
          <header class="modal-hd">
            <h3>選擇配送方式</h3>
            <button @click="showConfirm = false" aria-label="關閉"><X :size="16" /></button>
          </header>
          <div class="modal-body">
            <div v-if="profilesQuery.isPending.value" class="state">
              <Loader2 :size="18" class="spin" /> 載入中
            </div>
            <div v-else-if="(profilesQuery.data.value ?? []).length === 0" class="state empty">
              <p>您尚未建立任何配送資料。</p>
              <RouterLink to="/profile/shipping" class="cta">前往新增 →</RouterLink>
            </div>
            <ul v-else class="profiles">
              <li
                v-for="p in profilesQuery.data.value"
                :key="p.id"
                class="profile"
                :class="{ active: selectedProfileId === p.id }"
                @click="selectedProfileId = p.id"
              >
                <div class="profile-icon">
                  <component :is="p.shipping_type === 'home' ? MapPin : StoreIcon" :size="16" />
                </div>
                <div class="profile-text">
                  <div class="profile-name">
                    {{ p.recipient_name }}
                    <span v-if="p.is_default" class="default-tag">預設</span>
                  </div>
                  <div class="profile-detail">
                    <template v-if="p.shipping_type === 'home'">
                      {{ p.city }}{{ p.district }}{{ p.address_detail }}
                    </template>
                    <template v-else>
                      {{ p.store_name || p.store_id }}
                    </template>
                  </div>
                  <div class="profile-phone">{{ p.phone }}</div>
                </div>
                <div class="profile-fee">
                  +NT$ {{ p.shipping_type === 'home' ? 120 : 70 }}
                </div>
              </li>
            </ul>
          </div>
          <p v-if="actionError" class="error">{{ actionError }}</p>
          <footer class="modal-ft">
            <button class="btn-secondary" @click="showConfirm = false">取消</button>
            <button
              class="btn-primary"
              :disabled="!selectedProfileId || confirmMut.isPending.value"
              @click="doConfirm"
            >
              <Loader2 v-if="confirmMut.isPending.value" :size="14" class="spin" />
              確認下單
            </button>
          </footer>
        </div>
      </div>
    </Teleport>

    <!-- ── 拒絕 modal ────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showReject" class="modal-overlay" @click.self="showReject = false">
        <div class="modal">
          <header class="modal-hd">
            <h3>拒絕此報價</h3>
            <button @click="showReject = false" aria-label="關閉"><X :size="16" /></button>
          </header>
          <div class="modal-body">
            <p class="modal-desc">為了讓我們做得更好，方便告訴我們原因嗎？（選填）</p>
            <div class="quick-reasons">
              <button
                v-for="r in REJECT_REASONS"
                :key="r"
                class="reason-chip"
                @click="rejectReason = r"
              >
                {{ r }}
              </button>
            </div>
            <textarea v-model="rejectReason" rows="3" placeholder="補充說明…" />
          </div>
          <p v-if="actionError" class="error">{{ actionError }}</p>
          <footer class="modal-ft">
            <button class="btn-secondary" @click="showReject = false">取消</button>
            <button class="btn-tertiary" :disabled="rejectMut.isPending.value" @click="doReject">
              <Loader2 v-if="rejectMut.isPending.value" :size="14" class="spin" />
              確定拒絕
            </button>
          </footer>
        </div>
      </div>
    </Teleport>

    <!-- ── 修改 modal ────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showRevise" class="modal-overlay" @click.self="showRevise = false">
        <div class="modal">
          <header class="modal-hd">
            <h3>要求修改</h3>
            <button @click="showRevise = false" aria-label="關閉"><X :size="16" /></button>
          </header>
          <div class="modal-body">
            <p class="modal-desc">告訴我們希望調整的方向，我們將在 1–2 工作天內提供新的報價。</p>
            <div class="quick-reasons">
              <button
                v-for="r in REVISE_REASONS"
                :key="r"
                class="reason-chip"
                @click="reviseReason = r"
              >
                {{ r }}
              </button>
            </div>
            <textarea v-model="reviseReason" rows="3" required placeholder="例：希望尺寸改成 50×70 cm，並提高難度。" />
          </div>
          <p v-if="actionError" class="error">{{ actionError }}</p>
          <footer class="modal-ft">
            <button class="btn-secondary" @click="showRevise = false">取消</button>
            <button class="btn-primary" :disabled="reviseMut.isPending.value || !reviseReason.trim()" @click="doRevise">
              <Loader2 v-if="reviseMut.isPending.value" :size="14" class="spin" />
              送出修改要求
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.page {
  max-width: 720px; margin: 0 auto;
  padding: 32px 24px 96px;
}
.state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.error h1 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 22px; margin: 0;
}
.state.error .error-icon { color: #B85B58; }
.error-hint { font-size: 13px; margin: 0; }
.cta {
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.18em;
  color: var(--color-accent-deep); text-decoration: none;
  border-bottom: 1px solid currentColor;
}

.back {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.18em; color: var(--color-ink-muted);
  text-decoration: none; margin-bottom: 32px;
}
.back:hover { color: var(--color-accent-deep); }

.hd { margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--color-line); }
.kicker {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
}
.kicker-no {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em;
  color: var(--color-fresh);
}
.kicker-dot {
  width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent);
}
.kicker-chapter {
  font-family: var(--font-display); font-style: italic;
  font-size: 14px; color: var(--color-accent);
}
.hd h1 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 36px; letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 16px;
}
.hd-meta {
  display: flex; gap: 16px; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.1em; color: var(--color-ink-muted);
}
.hd-meta span { display: inline-flex; align-items: center; gap: 4px; }
.view-count {
  padding: 2px 8px; border: 1px solid var(--color-line);
  border-radius: 999px;
}

.countdown {
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  padding: 24px; margin-bottom: 32px;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.countdown-label {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.2em;
  color: var(--color-ink-muted);
}
.countdown-time {
  display: flex; align-items: baseline; gap: 8px;
  font-family: var(--font-mono);
}
.cd-cell {
  display: flex; flex-direction: column; align-items: center;
  min-width: 56px;
}
.cd-num {
  font-size: 36px; font-weight: 300;
  color: var(--color-accent-deep); letter-spacing: 0.04em;
}
.cd-lbl {
  font-size: 10px; color: var(--color-ink-muted);
  letter-spacing: 0.16em; margin-top: 2px;
}
.cd-sep {
  font-size: 28px; color: var(--color-line-strong, #BFAD8C);
}
.extend-btn {
  margin-top: 8px; padding: 8px 14px; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.12em;
  color: var(--color-ink-default);
  transition: border-color 150ms, color 150ms;
}
.extend-btn:hover:not(:disabled) {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.extended-hint {
  font-size: 12px; color: var(--color-ink-muted); margin: 0;
}

.preview, .spec, .price, .thread {
  margin-bottom: 40px;
}
.preview h2, .spec h2, .thread h2 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 19px; letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 16px;
}
.preview-frame {
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  overflow: hidden; background: #FFF;
}
.preview-frame img { width: 100%; display: block; }
.preview-hint {
  font-size: 12px; color: var(--color-ink-muted);
  margin: 12px 0 0; font-style: italic;
}

.spec dl {
  display: grid; grid-template-columns: 140px 1fr;
  gap: 12px 24px; margin: 0;
}
.spec dl > div { display: contents; }
.spec dt {
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.18em; color: var(--color-ink-muted);
}
.spec dd {
  font-size: 14px; color: var(--color-ink-strong); margin: 0;
}
.spec dd.multiline { white-space: pre-line; }

.price {
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  padding: 24px;
}
.price-row {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 14px; color: var(--color-ink-default);
  margin-bottom: 8px;
}
.price-row strong {
  font-family: var(--font-cn-serif); font-weight: 400;
  font-size: 32px; color: var(--color-accent-deep);
}
.price-hint {
  font-size: 12px; color: var(--color-ink-muted); margin: 0;
}

.thread {
  border-top: 1px solid var(--color-line); padding-top: 32px;
}
.msgs {
  list-style: none; padding: 16px; margin: 0;
  background: var(--color-paper-surface, #FCF7E5);
  border-radius: var(--radius-sm); border: 1px solid var(--color-line);
  display: flex; flex-direction: column; gap: 10px;
  max-height: 240px; overflow-y: auto;
}
.msg { display: flex; }
.msg-mine { justify-content: flex-end; }
.msg-them { justify-content: flex-start; }
.msg-bubble {
  max-width: 78%; padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.msg-mine .msg-bubble {
  background: var(--color-accent-deep); color: #FCF7E5;
}
.msg-them .msg-bubble {
  background: #FFF; color: var(--color-ink-strong);
  border: 1px solid var(--color-line);
}
.msg-bubble p { margin: 0; line-height: 1.6; white-space: pre-line; }
.msg-time {
  display: block; font-family: var(--font-mono);
  font-size: 10px; opacity: 0.7; margin-top: 4px;
}

.actions {
  display: flex; flex-direction: column; gap: 12px;
  padding-top: 24px; border-top: 1px solid var(--color-line);
}
.btn-primary, .btn-secondary, .btn-tertiary {
  padding: 14px 24px; cursor: pointer;
  border-radius: var(--radius-xs); font-family: var(--font-cn-serif);
  font-size: 15px; letter-spacing: 0.06em;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
}
.btn-primary {
  background: var(--color-accent-deep); color: #FCF7E5; border: 0;
}
.btn-primary:hover:not(:disabled) { background: var(--color-accent); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: transparent; color: var(--color-ink-default);
  border: 1px solid var(--color-line);
}
.btn-secondary:hover:not(:disabled) {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.btn-tertiary {
  background: transparent; color: #B85B58; border: 1px solid rgba(184, 91, 88, 0.3);
}
.btn-tertiary:hover:not(:disabled) {
  border-color: #B85B58; background: rgba(184, 91, 88, 0.06);
}

/* modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: 60;
  background: rgba(43, 36, 27, 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: 20px; animation: fadein 150ms;
}
.modal {
  width: 100%; max-width: 480px;
  background: var(--color-paper-base, #F7F1E3);
  border-radius: var(--radius-md);
  display: flex; flex-direction: column;
  max-height: 90vh; overflow: hidden;
}
.modal-hd {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 24px; border-bottom: 1px solid var(--color-line);
}
.modal-hd h3 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 19px; margin: 0; letter-spacing: 0.04em;
}
.modal-hd button {
  background: transparent; border: 0; cursor: pointer;
  width: 32px; height: 32px; border-radius: 50%;
  color: var(--color-ink-muted);
}
.modal-hd button:hover {
  background: var(--color-paper-surface, #FCF7E5);
  color: var(--color-ink-strong);
}
.modal-body {
  padding: 20px 24px; overflow-y: auto; flex: 1;
}
.modal-desc {
  font-size: 13px; color: var(--color-ink-muted);
  margin: 0 0 16px; line-height: 1.7;
}
.modal-ft {
  display: flex; gap: 12px; padding: 16px 24px;
  border-top: 1px solid var(--color-line);
  background: var(--color-paper-surface, #FCF7E5);
}
.modal-ft .btn-primary, .modal-ft .btn-secondary, .modal-ft .btn-tertiary {
  flex: 1; padding: 12px;
}

.profiles { list-style: none; padding: 0; margin: 0; }
.profile {
  display: flex; gap: 12px; padding: 16px;
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  cursor: pointer; margin-bottom: 8px;
  transition: border-color 150ms, background 150ms;
}
.profile:hover { border-color: var(--color-accent); }
.profile.active {
  border-color: var(--color-accent-deep);
  background: var(--color-paper-surface, #FCF7E5);
}
.profile-icon {
  flex-shrink: 0; width: 32px; height: 32px;
  border-radius: 50%; background: var(--color-paper-surface, #FCF7E5);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--color-accent-deep);
}
.profile-text { flex: 1; min-width: 0; }
.profile-name {
  font-family: var(--font-cn-serif); font-size: 15px;
  color: var(--color-ink-strong);
  display: flex; align-items: center; gap: 6px;
}
.default-tag {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.14em;
  padding: 1px 6px; background: var(--color-accent);
  color: #FCF7E5; border-radius: 2px;
}
.profile-detail {
  font-size: 12px; color: var(--color-ink-default);
  margin-top: 4px; line-height: 1.5;
}
.profile-phone {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--color-ink-muted); margin-top: 2px;
}
.profile-fee {
  font-family: var(--font-mono); font-size: 12px;
  color: var(--color-accent-deep); align-self: center;
  flex-shrink: 0;
}

.quick-reasons {
  display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;
}
.reason-chip {
  padding: 6px 12px; cursor: pointer;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: 999px;
  font: inherit; font-size: 12px; color: var(--color-ink-default);
}
.reason-chip:hover {
  border-color: var(--color-accent); color: var(--color-accent-deep);
}
.modal-body textarea {
  width: 100%; padding: 10px 12px; resize: vertical; min-height: 72px;
  font: inherit; font-size: 14px;
  border: 1px solid var(--color-line); border-radius: var(--radius-xs);
  background: #FFF; color: var(--color-ink-default);
}
.modal-body textarea:focus { outline: none; border-color: var(--color-accent); }

.empty p { font-size: 14px; margin: 0 0 12px; }

.error {
  font-size: 13px; color: #B85B58;
  padding: 8px 16px; margin: 0;
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadein {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
