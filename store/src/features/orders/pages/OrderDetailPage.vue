<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import {
  ArrowLeft, Loader2, Check, Copy, Package, AlertCircle, X, Truck, Wallet,
} from 'lucide-vue-next'
import {
  useOrderDetailQuery,
  useSubmitPaymentMutation,
  useConfirmReceivedMutation,
  useConfirmRefundMutation,
  useCancelOrderMutation,
  useUpdateShippingMutation,
  usePublicSettingsQuery,
  STATUS_LABEL,
  STATUS_TAB,
} from '../queries'
import { useOrderSse } from '../useOrderSse'
import type { ApiError, UpdateShippingPayload } from '../api'
import ShippingProfileForm from '@/features/profile/components/ShippingProfileForm.vue'
import type { ShippingProfileInput } from '@/features/profile/api'
import InfoDrawer from '@/features/info/InfoDrawer.vue'

const refundInfoOpen = ref(false)

const route = useRoute()
const orderId = computed(() => String(route.params.id || ''))

const orderQuery = useOrderDetailQuery(orderId)
const order = computed(() => orderQuery.data.value ?? null)

// SSE：訂閱訂單狀態變更（admin 標 paid / 出貨 / webhook 推 ECpay 狀態 / 退款）
// query invalidate 由 useOrderSse 內部處理
const sseToast = ref<string | null>(null)
let sseToastTimer: ReturnType<typeof setTimeout> | null = null
function showSseToast(text: string) {
  sseToast.value = text
  if (sseToastTimer) clearTimeout(sseToastTimer)
  sseToastTimer = setTimeout(() => { sseToast.value = null }, 4500)
}
useOrderSse(() => orderId.value || null, {
  onStatusChanged: (d) => {
    showSseToast(`訂單狀態更新：${STATUS_LABEL[d.status as keyof typeof STATUS_LABEL] ?? d.status}`)
  },
  onShipmentCreated: (d) => {
    showSseToast(`已出貨！追蹤號：${d.tracking_number}`)
  },
  onShipmentStatusChanged: (d) => {
    showSseToast(`物流狀態：${d.rtn_msg}`)
  },
})

// 退款確認
const confirmRefundMut = useConfirmRefundMutation(orderId)
const confirmRefundError = ref<string | null>(null)
async function doConfirmRefund() {
  confirmRefundError.value = null
  try {
    await confirmRefundMut.mutateAsync()
  } catch (e) {
    confirmRefundError.value = (e as ApiError).detail || '確認失敗'
  }
}

// 24h 倒數（pending_payment）
const now = ref(Date.now())
let tickHandle: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  tickHandle = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (tickHandle) clearInterval(tickHandle)
})

const deadline = computed(() => {
  if (!order.value?.payment_deadline) return null
  return new Date(order.value.payment_deadline).getTime()
})
const remainingMs = computed(() =>
  deadline.value === null ? 0 : Math.max(0, deadline.value - now.value),
)
const expired = computed(() => deadline.value !== null && remainingMs.value === 0)

function pad(n: number): string { return String(n).padStart(2, '0') }
const countdown = computed(() => {
  const ms = remainingMs.value
  const totalSec = Math.floor(ms / 1000)
  return {
    h: pad(Math.floor(totalSec / 3600)),
    m: pad(Math.floor((totalSec % 3600) / 60)),
    s: pad(totalSec % 60),
  }
})

// Bank info（後端 system_settings 才有；這裡先寫死 fallback）
const PAYMENT_INFO = {
  bank_name: '中華郵政',
  branch: '永康分行',
  account_name: 'YIIMUI 易木工作室',
  account_no: '700-0042312-345-678',
}
const copyMsg = ref<string | null>(null)
async function copyAccount() {
  try {
    await navigator.clipboard.writeText(PAYMENT_INFO.account_no)
    copyMsg.value = '已複製'
    setTimeout(() => (copyMsg.value = null), 1500)
  } catch {
    copyMsg.value = '複製失敗'
    setTimeout(() => (copyMsg.value = null), 1500)
  }
}

// Payment submission form
const showPaymentForm = ref(false)
const paymentForm = ref({
  transfer_amount: 0,
  transfer_date: new Date().toISOString().slice(0, 10),
  transfer_time: new Date().toTimeString().slice(0, 5),
  account_last5: '',
  notes: '',
})
const paymentError = ref<string | null>(null)

function openPaymentForm() {
  paymentError.value = null
  paymentForm.value = {
    transfer_amount: order.value?.total ?? 0,
    transfer_date: new Date().toISOString().slice(0, 10),
    transfer_time: new Date().toTimeString().slice(0, 5),
    account_last5: '',
    notes: '',
  }
  showPaymentForm.value = true
}

const submitPayMut = useSubmitPaymentMutation(orderId)
async function submitPayment() {
  paymentError.value = null
  if (!/^\d{5}$/.test(paymentForm.value.account_last5)) {
    paymentError.value = '帳號末 5 碼需為 5 個數字'
    return
  }
  try {
    await submitPayMut.mutateAsync({
      transfer_amount: paymentForm.value.transfer_amount,
      transfer_date: paymentForm.value.transfer_date,
      transfer_time: paymentForm.value.transfer_time + ':00',
      account_last5: paymentForm.value.account_last5,
      notes: paymentForm.value.notes || null,
    })
    showPaymentForm.value = false
  } catch (e) {
    const err = e as ApiError
    paymentError.value = err.detail || '送出失敗，請稍後再試'
  }
}

// 確認收貨
const confirmMut = useConfirmReceivedMutation(orderId)
async function confirmReceived() {
  if (!confirm('確認已收到貨？確認後訂單將標記完成。')) return
  try {
    await confirmMut.mutateAsync()
  } catch (e) {
    alert((e as ApiError).detail || '確認失敗')
  }
}

// 修改地址
const showModifyShipping = ref(false)
const modifyShippingErr = ref<string | null>(null)
const updateShippingMut = useUpdateShippingMutation(orderId)
const publicSettingsQuery = usePublicSettingsQuery()
const adminContactEmail = computed(
  () => publicSettingsQuery.data.value?.items?.admin_contact_email ?? '',
)

// 把現有 shipping_snapshot 轉成 ShippingProfileForm 需要的 ShippingProfile 形狀
const shippingProfileFromOrder = computed(() => {
  const o = order.value
  if (!o) return null
  const s = o.shipping_snapshot
  return {
    id: 'order-shipping',
    shipping_type: o.shipping_type,
    recipient_name: s.recipient_name ?? '',
    phone: s.phone ?? '',
    email: s.notify_email ?? null,
    city: s.city ?? null,
    district: s.district ?? null,
    address_detail: s.address_detail ?? null,
    store_id: s.store_id ?? null,
    store_name: s.store_name ?? null,
    is_default: false,
  }
})

async function submitModifyShipping(data: ShippingProfileInput) {
  modifyShippingErr.value = null
  // 不允許改 shipping_type — backend 也禁；過濾掉
  const payload: UpdateShippingPayload = {
    recipient_name: data.recipient_name,
    phone: data.phone,
    email: data.email,
    city: data.city,
    district: data.district,
    address_detail: data.address_detail,
    store_id: data.store_id,
    store_name: data.store_name,
  }
  try {
    await updateShippingMut.mutateAsync(payload)
    showModifyShipping.value = false
  } catch (e) {
    modifyShippingErr.value = (e as ApiError).detail || '修改失敗'
  }
}

// 取消訂單
const showCancelDialog = ref(false)
const cancelReason = ref('')
const cancelMut = useCancelOrderMutation(orderId)
async function submitCancel() {
  if (!cancelReason.value.trim()) {
    alert('請填寫取消原因')
    return
  }
  try {
    await cancelMut.mutateAsync(cancelReason.value.trim())
    showCancelDialog.value = false
  } catch (e) {
    alert((e as ApiError).detail || '取消失敗')
  }
}

// 進度 stepper（依 status 點亮）
// 使用者可見的進度時間軸（4 個主階段）。
// 對應 backend OrderStatusEnum；多種 status 可能映射到同一個 step。
const PROGRESS_STEPS = [
  { idx: 0, label: '待付款' },
  { idx: 1, label: '已付款' },
  { idx: 2, label: '製作中' },
  { idx: 3, label: '已出貨' },
  { idx: 4, label: '已完成' },
]

// status → step idx（無對應的特殊狀態：cancelled / refunded 等不顯示 stepper）
const STATUS_TO_STEP_IDX: Record<string, number> = {
  pending_payment: 0,
  payment_expired: 0,
  paid: 1,
  processing: 2,
  shipped: 3,
  completed: 4,
  // refund_processing / refunded / partially_refunded / cancelled 不在 stepper 範圍
}

const currentStepIdx = computed(() => {
  if (!order.value) return 0
  const idx = STATUS_TO_STEP_IDX[order.value.status]
  return idx === undefined ? 0 : idx
})

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 物流官網查詢連結 — 依 shipping_type 對應
import type { Shipment as ShipmentType } from '../api'
function trackingUrl(s: ShipmentType): string | null {
  const tn = s.tracking_number
  if (!tn) return null
  if (!order.value) return null
  const t = order.value.shipping_type
  if (t === 'home') {
    // HOME 黑貓：t-cat.com.tw / 中華郵政：post.gov.tw
    // 預設黑貓查詢；郵政可由 admin 改 SubType 對應後自動換
    return `https://www.t-cat.com.tw/Inquire/Trace.aspx?BillID=${encodeURIComponent(tn)}`
  }
  // 超商目前 ECpay 沒對外查詢頁；客戶取貨即取，不需要
  return null
}

function shippingSummary(): string {
  if (!order.value) return ''
  const s = order.value.shipping_snapshot
  if (order.value.shipping_type === 'home') {
    return `${s.recipient_name ?? ''} · ${[s.city, s.district, s.address_detail].filter(Boolean).join('')}`
  }
  return `${s.recipient_name ?? ''} · ${s.store_name ?? ''}`
}

function specSummary(spec: Record<string, unknown>): string {
  const parts: string[] = []
  const w = spec.canvas_w_cm
  const h = spec.canvas_h_cm
  if (typeof w === 'number' && typeof h === 'number') {
    parts.push(`${w}×${h}cm`)
  }
  const diff = spec.difficulty
  const DIFF: Record<string, string> = {
    beginner: '入門', elementary: '初級', intermediate: '中級', advanced: '進階',
  }
  if (typeof diff === 'string' && DIFF[diff]) parts.push(DIFF[diff])
  if (typeof spec.color_count === 'number') parts.push(`${spec.color_count} 色`)
  return parts.join(' · ')
}
</script>

<template>
  <main class="page">
    <RouterLink to="/orders" class="back-link">
      <ArrowLeft :size="14" />
      我的訂單
    </RouterLink>

    <div v-if="orderQuery.isPending.value" class="loading">
      <Loader2 :size="22" />
    </div>

    <section v-else-if="orderQuery.isError.value || !order" class="errored">
      <AlertCircle class="errored-icon" />
      <h1 class="errored-title">找不到訂單</h1>
      <RouterLink to="/orders" class="errored-cta">回我的訂單 →</RouterLink>
    </section>

    <template v-else>
      <header class="head">
        <div class="head-left">
          <span class="eyebrow">— Order #{{ order.order_number }} —</span>
          <h1 class="title">
            訂單<em class="em-status">{{ STATUS_LABEL[order.status] }}</em>
          </h1>
          <p class="meta">建立於 {{ fmtDateTime(order.created_at) }}</p>
        </div>
        <div class="head-right">
          <span class="head-total-label">應付總額</span>
          <span class="head-total">NT$ {{ order.total.toLocaleString() }}</span>
        </div>
      </header>

      <!-- 倒數（待付款）-->
      <section v-if="order.status === 'pending_payment' && deadline" class="band">
        <div class="band-row">
          <div>
            <div class="band-cap">— Payment Window —</div>
            <h2 class="band-title">24 小時付款期限</h2>
          </div>
          <div class="cd" :class="{ 'cd-expired': expired }">
            <span class="cd-num">{{ countdown.h }}</span>
            <span class="cd-sep">:</span>
            <span class="cd-num">{{ countdown.m }}</span>
            <span class="cd-sep">:</span>
            <span class="cd-num">{{ countdown.s }}</span>
          </div>
        </div>
        <p v-if="!expired" class="band-hint">逾期未付款訂單將自動取消。</p>
        <p v-else class="band-hint band-hint-expired">付款期限已過。</p>
      </section>

      <!-- 退款 / 取消狀態 banner（取代 stepper）-->
      <section
        v-if="order.status === 'refund_processing'"
        class="refund-banner refund-processing"
      >
        <Wallet :size="20" :stroke-width="1.5" class="refund-icon" />
        <div class="refund-text">
          <h3 class="refund-title">退款處理中</h3>
          <p class="refund-body">
            您的退款申請已受理，預計 5 個工作天內會匯回您的銀行帳戶。
            收到款項後請點下方按鈕確認。
          </p>
          <button
            type="button"
            class="refund-policy-link"
            @click="refundInfoOpen = true"
          >了解退款政策 →</button>
        </div>
      </section>

      <section
        v-else-if="order.status === 'refunded' || order.status === 'partially_refunded'"
        class="refund-banner refund-done"
      >
        <Wallet :size="20" :stroke-width="1.5" class="refund-icon" />
        <div class="refund-text">
          <h3 class="refund-title">
            {{ order.status === 'partially_refunded' ? '部分退款' : '退款完成' }}
          </h3>
          <p class="refund-body">
            退款金額：<strong>NT$ {{ (order.refund_amount ?? 0).toLocaleString() }}</strong>
            <span v-if="order.refunded_at"> · 處理時間：{{ fmtDateTime(order.refunded_at) }}</span>
          </p>
          <p v-if="order.refund_confirmed_at" class="refund-confirmed">
            <Check :size="12" :stroke-width="2" /> 您已確認收到退款（{{ fmtDateTime(order.refund_confirmed_at) }}）
          </p>
          <button
            type="button"
            class="refund-policy-link"
            @click="refundInfoOpen = true"
          >了解退款政策 →</button>
        </div>
        <button
          v-if="!order.refund_confirmed_at"
          type="button"
          class="refund-cta"
          :disabled="confirmRefundMut.isPending.value"
          @click="doConfirmRefund"
        >
          <Loader2 v-if="confirmRefundMut.isPending.value" :size="14" class="spin" />
          <Check v-else :size="14" :stroke-width="1.5" />
          我已收到退款
        </button>
      </section>
      <p v-if="confirmRefundError" class="refund-error">{{ confirmRefundError }}</p>

      <!-- 進度 stepper（只在主流程狀態顯示；取消/退款相關不顯示） -->
      <section
        v-if="!['cancelled', 'refunded', 'partially_refunded', 'refund_processing', 'payment_expired'].includes(order.status)"
        class="stepper"
      >
        <div class="stepper-cap">
          <span class="stepper-no">No. 01</span>
          <span class="stepper-dot"></span>
          <span class="stepper-italic">Progress</span>
        </div>
        <div class="steps">
          <div
            v-for="(step, idx) in PROGRESS_STEPS"
            :key="step.key"
            class="step"
            :class="{
              'step-done': idx < currentStepIdx,
              'step-current': idx === currentStepIdx,
            }"
          >
            <span class="step-no">{{ String(idx + 1).padStart(2, '0') }}</span>
            <span class="step-label">{{ step.label }}</span>
          </div>
        </div>
      </section>

      <div class="grid">
        <!-- 左：商品列表 + 收件 -->
        <div class="col-main">
          <section class="block">
            <h2 class="block-title">
              <span class="block-no">02</span>
              <span class="block-cap">Items</span>
              <span class="block-name">商品</span>
            </h2>
            <ul class="items">
              <li v-for="i in order.items" :key="i.id" class="item">
                <div class="item-info">
                  <div class="item-name">{{ i.product_title_snapshot }}</div>
                  <div class="item-spec">{{ specSummary(i.variant_spec_snapshot) }}</div>
                  <div v-if="i.preorder_qty > 0" class="item-preorder">
                    現貨 {{ i.fulfilled_qty }} 件 · 預購 {{ i.preorder_qty }} 件
                  </div>
                </div>
                <div class="item-qty">× {{ i.quantity }}</div>
                <div class="item-total">
                  NT$ {{ (i.unit_price * i.quantity).toLocaleString() }}
                </div>
              </li>
            </ul>
          </section>

          <section class="block">
            <div class="block-title-row">
              <h2 class="block-title">
                <span class="block-no">03</span>
                <span class="block-cap">Shipping</span>
                <span class="block-name">配送</span>
              </h2>
              <button
                v-if="order.can_modify_shipping"
                type="button"
                class="modify-btn"
                @click="showModifyShipping = true"
              >
                修改
              </button>
            </div>

            <dl class="kv">
              <div class="kv-row">
                <dt>方式</dt>
                <dd>{{ order.shipping_type === 'home' ? '宅配到府' : '超商取貨' }}</dd>
              </div>
              <div class="kv-row">
                <dt>收件</dt>
                <dd>{{ shippingSummary() }}</dd>
              </div>
              <div v-if="order.shipping_snapshot.phone" class="kv-row">
                <dt>電話</dt>
                <dd>{{ order.shipping_snapshot.phone }}</dd>
              </div>
              <div v-if="order.shipments.length > 0" class="kv-row">
                <dt>物流單號</dt>
                <dd>
                  <div
                    v-for="s in order.shipments"
                    :key="s.id"
                    class="shipment-line"
                  >
                    <span class="track-no">{{ s.tracking_number ?? '尚未產生' }}</span>
                    <a
                      v-if="trackingUrl(s) && s.tracking_number"
                      :href="trackingUrl(s)!"
                      target="_blank"
                      rel="noopener"
                      class="track-link"
                    >物流查詢 →</a>
                    <span v-if="s.last_rtn_msg" class="track-status">{{ s.last_rtn_msg }}</span>
                  </div>
                </dd>
              </div>
            </dl>

            <p
              v-if="!order.can_modify_shipping && ['paid', 'processing'].includes(order.status) && adminContactEmail"
              class="modify-hint"
            >
              如需修改地址，請寄信至
              <a :href="`mailto:${adminContactEmail}?subject=修改訂單${order.order_number}的出貨資訊`">
                {{ adminContactEmail }}
              </a>
            </p>
          </section>

          <section v-if="order.customer_notes" class="block">
            <h2 class="block-title">
              <span class="block-no">04</span>
              <span class="block-cap">Notes</span>
              <span class="block-name">備註</span>
            </h2>
            <p class="notes-body">{{ order.customer_notes }}</p>
          </section>
        </div>

        <!-- 右：摘要 + Actions -->
        <aside class="col-side">
          <div class="summary-card">
            <h2 class="summary-title">金額明細</h2>
            <dl class="summary-rows">
              <div class="srow">
                <dt>小計</dt>
                <dd>NT$ {{ order.subtotal.toLocaleString() }}</dd>
              </div>
              <div v-if="order.discount_amount > 0" class="srow srow-discount">
                <dt>折扣</dt>
                <dd>− NT$ {{ order.discount_amount.toLocaleString() }}</dd>
              </div>
              <div class="srow">
                <dt>運費</dt>
                <dd>NT$ {{ order.shipping_fee.toLocaleString() }}</dd>
              </div>
            </dl>
            <div class="summary-total">
              <span class="t-label">應付</span>
              <span class="t-value">NT$ {{ order.total.toLocaleString() }}</span>
            </div>
          </div>

          <!-- Bank info（待付款狀態）-->
          <div v-if="order.status === 'pending_payment'" class="summary-card">
            <h2 class="summary-title">匯款資訊</h2>
            <dl class="bank">
              <div class="bank-row">
                <dt>銀行</dt>
                <dd>{{ PAYMENT_INFO.bank_name }} · {{ PAYMENT_INFO.branch }}</dd>
              </div>
              <div class="bank-row">
                <dt>戶名</dt>
                <dd>{{ PAYMENT_INFO.account_name }}</dd>
              </div>
              <div class="bank-row bank-row-acc">
                <dt>帳號</dt>
                <dd>
                  <span class="acc">{{ PAYMENT_INFO.account_no }}</span>
                  <button type="button" class="copy-btn" @click="copyAccount">
                    <Copy :size="12" />
                    {{ copyMsg ?? '複製' }}
                  </button>
                </dd>
              </div>
            </dl>
          </div>

          <!-- Actions -->
          <div class="actions">
            <button
              v-if="order.status === 'pending_payment' && !showPaymentForm"
              type="button"
              class="btn-primary"
              @click="openPaymentForm"
            >
              <span>{{ order.payment_submissions.length > 0 ? '再次上傳付款核對' : '上傳付款核對表單' }}</span>
            </button>
            <button
              v-if="order.can_confirm_received"
              type="button"
              class="btn-primary"
              :disabled="confirmMut.isPending.value"
              @click="confirmReceived"
            >
              <Loader2 v-if="confirmMut.isPending.value" class="spin" />
              <Check v-else :size="14" />
              <span>確認已收貨</span>
            </button>
            <button
              v-if="order.can_cancel"
              type="button"
              class="btn-ghost btn-danger"
              @click="showCancelDialog = true"
            >
              <X :size="14" />
              <span>取消訂單</span>
            </button>
          </div>

          <!-- 已上傳的付款核對表單 -->
          <div v-if="order.payment_submissions.length > 0" class="submissions">
            <h3 class="submissions-title">已上傳的付款核對</h3>
            <ul class="sub-list">
              <li v-for="s in order.payment_submissions" :key="s.id" class="sub">
                <div class="sub-row">
                  <span class="sub-label">轉帳金額</span>
                  <span class="sub-value">NT$ {{ s.transfer_amount.toLocaleString() }}</span>
                </div>
                <div class="sub-row">
                  <span class="sub-label">時間</span>
                  <span class="sub-value">{{ s.transfer_date }} {{ s.transfer_time.slice(0, 5) }}</span>
                </div>
                <div class="sub-row">
                  <span class="sub-label">末 5 碼</span>
                  <span class="sub-value">{{ s.account_last5 }}</span>
                </div>
                <div v-if="s.is_flagged" class="sub-flag">⚠ 客服已標記，等待人工核對</div>
              </li>
            </ul>
          </div>
        </aside>
      </div>

      <!-- Payment Form Modal-ish inline -->
      <Teleport to="body">
        <Transition name="modal">
          <div v-if="showPaymentForm" class="modal-overlay" @click.self="showPaymentForm = false">
            <div class="modal">
              <header class="modal-head">
                <h3 class="modal-title">上傳付款核對表單</h3>
                <button type="button" class="modal-close" @click="showPaymentForm = false">
                  <X :size="16" />
                </button>
              </header>
              <form class="modal-form" @submit.prevent="submitPayment" novalidate>
                <div class="field">
                  <label class="label" for="pf-amt">轉帳金額</label>
                  <input
                    id="pf-amt"
                    v-model.number="paymentForm.transfer_amount"
                    type="number"
                    class="input"
                    required
                    min="1"
                  />
                </div>
                <div class="field-row">
                  <div class="field">
                    <label class="label" for="pf-date">轉帳日期</label>
                    <input
                      id="pf-date"
                      v-model="paymentForm.transfer_date"
                      type="date"
                      class="input"
                      required
                    />
                  </div>
                  <div class="field">
                    <label class="label" for="pf-time">轉帳時間</label>
                    <input
                      id="pf-time"
                      v-model="paymentForm.transfer_time"
                      type="time"
                      class="input"
                      required
                    />
                  </div>
                </div>
                <div class="field">
                  <label class="label" for="pf-acc">轉帳帳號末 5 碼</label>
                  <input
                    id="pf-acc"
                    v-model="paymentForm.account_last5"
                    type="text"
                    class="input"
                    required
                    pattern="\d{5}"
                    maxlength="5"
                    placeholder="僅 5 個數字"
                  />
                </div>
                <div class="field">
                  <label class="label" for="pf-notes">備註（可選）</label>
                  <textarea
                    id="pf-notes"
                    v-model="paymentForm.notes"
                    class="input"
                    rows="2"
                    maxlength="200"
                    placeholder="例：已加 LINE 通知"
                  />
                </div>
                <p v-if="paymentError" class="api-err">{{ paymentError }}</p>
                <div class="modal-foot">
                  <button type="button" class="btn-ghost" @click="showPaymentForm = false">取消</button>
                  <button type="submit" class="btn-primary" :disabled="submitPayMut.isPending.value">
                    <Loader2 v-if="submitPayMut.isPending.value" class="spin" />
                    <span>{{ submitPayMut.isPending.value ? '送出中...' : '送出' }}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </Transition>

        <!-- 取消訂單 dialog -->
        <Transition name="modal">
          <div v-if="showCancelDialog" class="modal-overlay" @click.self="showCancelDialog = false">
            <div class="modal modal-narrow">
              <header class="modal-head">
                <h3 class="modal-title">取消訂單</h3>
                <button type="button" class="modal-close" @click="showCancelDialog = false">
                  <X :size="16" />
                </button>
              </header>
              <div class="modal-body">
                <p class="cancel-warn">取消後此訂單無法復原。</p>
                <label class="label" for="cancel-reason">取消原因</label>
                <textarea
                  id="cancel-reason"
                  v-model="cancelReason"
                  class="input"
                  rows="3"
                  maxlength="200"
                  placeholder="請告訴我們原因，幫助我們改進"
                />
                <div class="modal-foot">
                  <button type="button" class="btn-ghost" @click="showCancelDialog = false">不取消</button>
                  <button
                    type="button"
                    class="btn-primary btn-danger"
                    :disabled="cancelMut.isPending.value"
                    @click="submitCancel"
                  >
                    <Loader2 v-if="cancelMut.isPending.value" class="spin" />
                    <span>{{ cancelMut.isPending.value ? '取消中...' : '確認取消' }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- 修改地址 Modal -->
      <Teleport to="body">
        <Transition name="fade">
          <div
            v-if="showModifyShipping && shippingProfileFromOrder"
            class="modal-overlay"
            @click.self="showModifyShipping = false"
          >
            <div class="modal modify-modal">
              <div class="modal-head">
                <h3>修改出貨資訊</h3>
                <button type="button" class="modal-close" @click="showModifyShipping = false">
                  <X :size="16" />
                </button>
              </div>
              <p class="modal-hint">付款被管理員確認後將無法自行修改。配送方式不可更動。</p>
              <ShippingProfileForm
                :initial="shippingProfileFromOrder"
                :submitting="updateShippingMut.isPending.value"
                :error-text="modifyShippingErr"
                :compact="true"
                :lock-shipping-type="true"
                @submit="submitModifyShipping"
                @cancel="showModifyShipping = false"
              />
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- SSE toast：訂單狀態 / 物流狀態即時通知 -->
      <Teleport to="body">
        <Transition name="sse-toast">
          <div v-if="sseToast" class="sse-toast" @click="sseToast = null">
            <Truck :size="14" :stroke-width="1.5" />
            <span>{{ sseToast }}</span>
          </div>
        </Transition>
      </Teleport>
    </template>

    <InfoDrawer
      :open="refundInfoOpen"
      slug="refund_policy"
      title="退款政策"
      full-page-path="/refund-policy"
      @close="refundInfoOpen = false"
    />
  </main>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 56px 56px 96px;
}

.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted); text-decoration: none;
  margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

/* ── 退款 banner ──────────────────────────────────────────────── */
.refund-banner {
  display: flex; align-items: flex-start; gap: 16px;
  padding: 18px 22px;
  border: 1px solid;
  border-radius: var(--radius-sm);
  margin-bottom: 36px;
  flex-wrap: wrap;
}
.refund-icon { flex-shrink: 0; margin-top: 2px; }
.refund-text { flex: 1; min-width: 240px; }
.refund-title {
  margin: 0 0 6px;
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.04em;
}
.refund-body {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
}
.refund-body strong { color: var(--color-ink-strong); font-weight: 500; }
.refund-confirmed {
  margin: 8px 0 0;
  display: inline-flex; align-items: center; gap: 4px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--color-fresh);
}
.refund-cta {
  flex-shrink: 0;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 11px 22px;
  border: 0;
  border-radius: var(--radius-xs);
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  font-family: var(--font-cn-serif);
  font-size: 13px; letter-spacing: 0.04em;
  cursor: pointer;
}
.refund-cta:hover { background: var(--color-accent-deep); }
.refund-cta:disabled { opacity: 0.5; cursor: not-allowed; }
.refund-error {
  font-size: 12px; color: var(--color-state-danger);
  margin: 0 0 24px;
}

.refund-policy-link {
  display: inline-block;
  margin-top: 8px;
  padding: 0;
  background: transparent;
  border: none;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  cursor: pointer;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 2px;
  transition: color 150ms, border-color 150ms;
}
.refund-policy-link:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

.refund-processing {
  background: var(--color-paper-surface);
  border-color: var(--color-state-warning);
  color: var(--color-state-warning);
}
.refund-done {
  background: var(--color-fresh-tint);
  border-color: var(--color-fresh-soft);
  color: var(--color-fresh);
}

/* ── SSE toast ───────────────────────────────────────────────── */
.sse-toast {
  position: fixed; right: 32px; bottom: 32px; z-index: 1100;
  padding: 12px 18px;
  background: var(--color-ink-strong); color: var(--color-paper-canvas);
  border-radius: var(--radius-sm);
  font-family: var(--font-cn-serif); font-size: 13px; letter-spacing: 0.04em;
  display: inline-flex; align-items: center; gap: 8px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(46, 40, 35, 0.18);
  max-width: 360px;
}
.sse-toast-enter-active, .sse-toast-leave-active {
  transition: opacity 200ms, transform 200ms;
}
.sse-toast-enter-from, .sse-toast-leave-to {
  opacity: 0; transform: translateY(8px);
}

.loading {
  display: flex;
  justify-content: center;
  padding: 96px 0;
  color: var(--color-ink-muted);
}
.loading :deep(svg),
.spin {
  animation: spin 1s linear infinite;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
.spin { width: 14px; height: 14px; }
@keyframes spin { to { transform: rotate(360deg); } }

.errored {
  text-align: center;
  padding: 96px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.errored-icon {
  width: 36px; height: 36px;
  stroke: var(--color-state-danger);
  stroke-width: 1.25;
  fill: none;
  margin-bottom: 16px;
}
.errored-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  color: var(--color-ink-strong);
  margin: 0 0 18px;
}
.errored-cta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 4px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 36px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-line);
}
.head-left {}
.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
}
.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 12px 0 6px;
}
.em-status {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  margin-left: 0.2em;
}
.meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--color-ink-muted);
  margin: 0;
}

.head-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.head-total-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.head-total {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 500;
  color: var(--color-accent-wine);
}

/* 倒數 band */
.band {
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 24px 28px;
  margin-bottom: 32px;
}
.band-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}
.band-cap {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
  margin-bottom: 4px;
}
.band-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.cd {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 30px;
  font-weight: 500;
  color: var(--color-ink-strong);
}
.cd-num {
  background: var(--color-paper-canvas);
  padding: 4px 10px;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  min-width: 50px;
  text-align: center;
}
.cd-sep { color: var(--color-ink-muted); }
.cd-expired .cd-num { border-color: var(--color-state-danger); opacity: 0.6; }

.band-hint {
  font-size: 12px;
  color: var(--color-ink-muted);
  margin: 12px 0 0;
  letter-spacing: 0.04em;
}
.band-hint-expired { color: var(--color-state-danger); }

/* Stepper */
.stepper { margin-bottom: 36px; }
.stepper-cap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}
.stepper-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.stepper-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.stepper-italic {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  color: var(--color-accent);
}

.steps {
  display: flex;
  align-items: center;
  gap: 0;
  position: relative;
  padding: 24px 0 16px;
}
.steps::before {
  content: '';
  position: absolute;
  top: 36px;
  left: 16px;
  right: 16px;
  height: 1px;
  background: var(--color-line);
  z-index: 0;
}
.step {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
}
.step-no {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-ink-muted);
}
.step-label {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
}
.step-done .step-no {
  background: var(--color-fresh-tint);
  border-color: var(--color-fresh);
  color: var(--color-fresh);
}
.step-done .step-label { color: var(--color-fresh); }
.step-current .step-no {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}
.step-current .step-label {
  color: var(--color-ink-strong);
  font-weight: 400;
}

/* Grid */
.grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 48px;
  align-items: start;
}
.col-main { display: flex; flex-direction: column; gap: 32px; }
.col-side {
  position: sticky;
  top: 96px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Block */
.block-title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin: 0 0 20px;
}
.block-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.block-cap {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  color: var(--color-accent);
}
.block-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}

.items {
  list-style: none;
  padding: 0;
  margin: 0;
  border-top: 1px solid var(--color-line-subtle);
}
.item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 16px 24px;
  align-items: center;
  padding: 18px 0;
  border-bottom: 1px solid var(--color-line-subtle);
}
.item-info { min-width: 0; }
.item-name {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}
.item-spec {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.item-preorder {
  font-size: 11px;
  color: var(--color-state-warning);
  margin-top: 4px;
  letter-spacing: 0.04em;
}
.item-qty {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-default);
}
.item-total {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink-strong);
}

.kv {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kv-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 14px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-line-subtle);
}
.kv-row:last-child { border-bottom: none; }
.kv-row dt {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.kv-row dd {
  font-size: 13px;
  color: var(--color-ink-default);
  margin: 0;
  letter-spacing: 0.02em;
}
.track-no {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-ink-strong);
  background: var(--color-paper-deep);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  margin-right: 8px;
}
.shipment-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.track-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  transition: color 150ms;
}
.track-link:hover { color: var(--color-accent-deep); }
.track-status {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

.notes-body {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
  margin: 0;
  letter-spacing: 0.04em;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 16px 20px;
  border-radius: var(--radius-xs);
  white-space: pre-wrap;
}

/* Summary card */
.summary-card {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 24px;
}
.summary-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 16px;
}

.summary-rows .srow {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
}
.summary-rows .srow dt {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.summary-rows .srow dd {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-strong);
  margin: 0;
}
.srow-discount dd { color: var(--color-fresh); }

.summary-total {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 14px 0 0;
  margin-top: 12px;
  border-top: 1px solid var(--color-line-subtle);
}
.t-label {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 13px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}
.t-value {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 500;
  color: var(--color-accent-wine);
}

.bank {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bank-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-line-subtle);
}
.bank-row:last-child { border-bottom: none; }
.bank-row dt {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.bank-row dd {
  font-family: var(--font-cn-serif);
  font-size: 13px;
  color: var(--color-ink-strong);
  margin: 0;
  text-align: right;
}
.bank-row-acc dd { display: inline-flex; align-items: center; gap: 8px; }
.acc {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.06em;
}
.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 3px 7px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  cursor: pointer;
}
.copy-btn :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

/* Actions */
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.btn-primary {
  width: 100%;
  height: 48px;
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  background: var(--color-ink-strong);
  border: 1px solid var(--color-ink-strong);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 200ms, border-color 200ms;
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-primary :deep(svg) { stroke: currentColor; stroke-width: 1.75; fill: none; }

.btn-ghost {
  width: 100%;
  height: 44px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-ink-default);
  background: transparent;
  border: 1px solid var(--color-line);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: border-color 150ms, color 150ms;
}
.btn-ghost:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.btn-danger { color: var(--color-state-danger); border-color: var(--color-state-danger); }
.btn-danger:hover { color: var(--color-paper-canvas); background: var(--color-state-danger); border-color: var(--color-state-danger); }
.btn-primary.btn-danger { background: var(--color-state-danger); border-color: var(--color-state-danger); color: var(--color-paper-canvas); }
.btn-primary.btn-danger:hover:not(:disabled) { background: #5C2230; border-color: #5C2230; }
.btn-ghost :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

/* Submissions */
.submissions {
  background: var(--color-paper-canvas);
  border: 1px dashed var(--color-line);
  border-radius: var(--radius-xs);
  padding: 18px 20px;
}
.submissions-title {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0 0 12px;
}
.sub-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.sub {
  padding: 12px 14px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  font-size: 12px;
}
.sub-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}
.sub-label { color: var(--color-ink-muted); font-family: var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; font-size: 10px; }
.sub-value { color: var(--color-ink-strong); font-family: var(--font-mono); font-size: 12px; }
.sub-flag {
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-state-warning);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(31, 26, 21, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 24px;
  backdrop-filter: blur(2px);
}
.modal {
  width: 100%;
  max-width: 480px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  padding: 28px 32px 24px;
  box-shadow: 0 16px 48px -12px rgba(31, 26, 21, 0.18);
}
.modal-narrow { max-width: 420px; }
.modify-modal { max-width: 560px; }
.modify-modal .modal-head h3 {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.modal-hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 12px 0 18px;
  padding: 10px 12px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
}

.block-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}
.modify-btn {
  background: transparent;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 4px 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-default);
  cursor: pointer;
  transition: border-color 150ms, color 150ms;
}
.modify-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.modify-hint {
  margin: 14px 0 0;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  line-height: 1.7;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
}
.modify-hint a {
  color: var(--color-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.modal-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.modal-close {
  width: 28px; height: 28px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-ink-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.modal-close:hover { color: var(--color-ink-strong); }
.modal-close :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

.modal-form { display: flex; flex-direction: column; gap: 14px; }
.modal-body { display: flex; flex-direction: column; gap: 14px; }

.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-default);
}
.input {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-ink-strong);
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 10px 12px;
  outline: none;
  transition: border-color 150ms, box-shadow 150ms;
}
.input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-tint);
}

.api-err {
  margin: 0;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-state-danger);
  background: rgba(123, 46, 64, 0.06);
  border: 1px solid var(--color-state-danger);
  border-radius: var(--radius-xs);
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 6px;
}
.modal-foot .btn-ghost,
.modal-foot .btn-primary {
  width: auto;
  padding: 0 22px;
  height: 42px;
}

.cancel-warn {
  font-size: 13px;
  color: var(--color-state-warning);
  margin: 0 0 8px;
  letter-spacing: 0.04em;
}

.modal-enter-active, .modal-leave-active {
  transition: opacity 200ms ease;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 200ms ease;
}
.modal-enter-from .modal { transform: translateY(8px); }
.modal-leave-to .modal { transform: translateY(8px); }

@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .grid { grid-template-columns: 1fr; gap: 32px; }
  .col-side { position: static; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .head { flex-direction: column; align-items: flex-start; gap: 16px; }
  .head-right { text-align: left; flex-direction: row; align-items: baseline; gap: 12px; }
  .field-row { grid-template-columns: 1fr; }
  .item { grid-template-columns: 1fr; gap: 6px; }
  .item-qty, .item-total { justify-self: flex-end; }
}
</style>
