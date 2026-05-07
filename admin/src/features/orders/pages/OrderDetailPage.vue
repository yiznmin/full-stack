<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  Package,
  Truck,
  CreditCard,
  Flag,
  RotateCcw,
  XCircle,
  AlertTriangle,
  Check,
  Pencil,
  X,
} from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Dialog from '@/shared/ui/Dialog.vue'

import {
  useOrderQuery,
  useUpdateStatusMutation,
  useCreateShipmentMutation,
  useUpdateProductionProgressMutation,
  useFlagPaymentSubmissionMutation,
  useRefundOrderMutation,
  useUpdateAdminNotesMutation,
  useUpdateShippingMutation,
  useLockShippingMutation,
} from '../queries'
import type {
  OrderDetail,
  OrderItem,
  OrderStatus,
  PaymentSubmission,
  ProductionProgressStatus,
  Shipment,
} from '../api'

import OrderStatusBadge from '../components/OrderStatusBadge.vue'
import ConfirmStatusDialog from '../components/ConfirmStatusDialog.vue'
import ShipmentDialog from '../components/ShipmentDialog.vue'
import PaymentFlagDialog from '../components/PaymentFlagDialog.vue'
import RefundProcessingDialog from '../components/RefundProcessingDialog.vue'
import RefundFinalizeDialog from '../components/RefundFinalizeDialog.vue'
import ProductionProgressRow from '../components/ProductionProgressRow.vue'

const route = useRoute()
const router = useRouter()

const orderId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))

const { data: order, isLoading, isError, error } = useOrderQuery(orderId)

// ── Mutations ─────────────────────────────────────────────────────────
const updateStatus = useUpdateStatusMutation(orderId.value)
const createShipment = useCreateShipmentMutation(orderId.value)
const updateProgress = useUpdateProductionProgressMutation(orderId.value)
const flagSub = useFlagPaymentSubmissionMutation(orderId.value)
const refund = useRefundOrderMutation(orderId.value)
const updateNotes = useUpdateAdminNotesMutation(orderId.value)

const apiError = ref<string | null>(null)

function handleApiError(e: unknown, fallback = '操作失敗') {
  const err = e as { status?: number; message?: string }
  if (err.message?.includes('狀態')) {
    apiError.value = '訂單狀態已被其他人變更，已重新載入。'
  } else if (err.status === 502 || err.status === 503) {
    apiError.value = '物流系統暫時無法連線，請稍後再試。'
  } else {
    apiError.value = err.message || fallback
  }
}

// ── Dialog state ──────────────────────────────────────────────────────
type StatusTarget = 'paid' | 'processing' | 'completed' | 'cancelled'
const confirmStatusTarget = ref<StatusTarget | null>(null)
const shipmentDialogOpen = ref(false)
const flagSubmissionId = ref<string | null>(null)
const refundProcessingOpen = ref(false)
const refundFinalizeOpen = ref(false)

// ── Inline admin notes ────────────────────────────────────────────────
const localNotes = ref('')
const notesEditing = ref(false)
watch(
  order,
  (o) => {
    if (o && !notesEditing.value) localNotes.value = o.admin_notes ?? ''
  },
  { immediate: true },
)

async function saveNotes() {
  if (!order.value) return
  try {
    await updateNotes.mutateAsync({ admin_notes: localNotes.value })
    notesEditing.value = false
  } catch (e) {
    handleApiError(e, '備註儲存失敗')
  }
}

// ── Header action handlers ────────────────────────────────────────────
function openConfirmStatus(target: StatusTarget) {
  apiError.value = null
  confirmStatusTarget.value = target
}

async function doConfirmStatus(target: StatusTarget) {
  try {
    await updateStatus.mutateAsync({ status: target })
    confirmStatusTarget.value = null
  } catch (e) {
    handleApiError(e)
    confirmStatusTarget.value = null
  }
}

async function doFlagSubmission(submissionId: string, adminNote: string) {
  try {
    await flagSub.mutateAsync({
      submissionId,
      payload: { is_flagged: true, admin_note: adminNote },
    })
    flagSubmissionId.value = null
  } catch (e) {
    handleApiError(e, 'Flag 失敗')
    flagSubmissionId.value = null
  }
}

async function doShipment(shipmentType: 'fulfilled' | 'preorder') {
  try {
    await createShipment.mutateAsync({ shipment_type: shipmentType })
    shipmentDialogOpen.value = false
  } catch (e) {
    handleApiError(e)
    shipmentDialogOpen.value = false
  }
}

async function doRefundProcessing(reason: string) {
  try {
    await updateStatus.mutateAsync({
      status: 'refund_processing',
      admin_notes: appendAdminNote(`[退款原因] ${reason}`),
    })
    refundProcessingOpen.value = false
  } catch (e) {
    handleApiError(e)
    refundProcessingOpen.value = false
  }
}

async function doRefund(payload: {
  refund_amount: number
  returned_item_ids: string[]
  cancel_reason: string
}) {
  try {
    await refund.mutateAsync(payload)
    refundFinalizeOpen.value = false
  } catch (e) {
    handleApiError(e)
    refundFinalizeOpen.value = false
  }
}

async function doUpdateProgress(progressId: string, status: 'manufacturing' | 'packaging' | 'ready_to_ship') {
  try {
    await updateProgress.mutateAsync({ progressId, payload: { status } })
  } catch (e) {
    handleApiError(e, '生產進度更新失敗')
  }
}

// ── Shipping edit / lock ────────────────────────────────────────────────
const shippingEditOpen = ref(false)
const shippingEditErr = ref<string | null>(null)
const updateShippingMut = useUpdateShippingMutation(orderId.value)
const lockShippingMut = useLockShippingMutation(orderId.value)
const shippingForm = ref({
  recipient_name: '',
  phone: '',
  email: '',
  city: '',
  district: '',
  address_detail: '',
  store_id: '',
  store_name: '',
})
function openShippingEdit() {
  if (!order.value) return
  const s = order.value.shipping_snapshot
  shippingForm.value = {
    recipient_name: s.recipient_name ?? '',
    phone: s.phone ?? '',
    email: s.notify_email ?? '',
    city: s.city ?? '',
    district: s.district ?? '',
    address_detail: s.address_detail ?? '',
    store_id: s.store_id ?? '',
    store_name: s.store_name ?? '',
  }
  shippingEditErr.value = null
  shippingEditOpen.value = true
}
watch(shippingEditOpen, (open) => { if (open) openShippingEdit() })
async function submitShippingEdit() {
  shippingEditErr.value = null
  try {
    await updateShippingMut.mutateAsync({
      recipient_name: shippingForm.value.recipient_name || undefined,
      phone: shippingForm.value.phone || undefined,
      email: shippingForm.value.email || null,
      city: shippingForm.value.city || null,
      district: shippingForm.value.district || null,
      address_detail: shippingForm.value.address_detail || null,
      store_id: shippingForm.value.store_id || null,
      store_name: shippingForm.value.store_name || null,
    })
    shippingEditOpen.value = false
  } catch (e) {
    shippingEditErr.value = (e as { message?: string }).message || '修改失敗'
  }
}

function appendAdminNote(line: string): string {
  const existing = order.value?.admin_notes ?? ''
  const stamp = `[${new Date().toISOString().slice(0, 10)}] ${line}`
  return existing ? `${stamp}\n${existing}` : stamp
}

// ── Derived ───────────────────────────────────────────────────────────
const canConfirmPayment = computed(() => order.value?.status === 'pending_payment')
const canCancel = computed(() => order.value?.status === 'pending_payment')
const canStartProcessing = computed(() => order.value?.status === 'paid')
const canCreateShipment = computed(
  () => !!order.value && ['paid', 'processing', 'shipped'].includes(order.value.status),
)
// 修改出貨資訊：未鎖定 + 狀態允許
const canEditShipping = computed(
  () =>
    !!order.value &&
    !order.value.shipping_locked &&
    ['pending_payment', 'paid', 'processing'].includes(order.value.status),
)
// 確認出貨資訊：未鎖定 + paid/processing 狀態
const canLockShipping = computed(
  () =>
    !!order.value &&
    !order.value.shipping_locked &&
    ['paid', 'processing'].includes(order.value.status),
)
const canStartRefundProcessing = computed(
  () =>
    !!order.value &&
    ['paid', 'processing', 'shipped', 'completed'].includes(order.value.status),
)
const canFinalizeRefund = computed(() => order.value?.status === 'refund_processing')
const isRefunded = computed(
  () => !!order.value && ['refunded', 'partially_refunded'].includes(order.value.status),
)

const remainingHours = computed(() => {
  if (!order.value?.payment_deadline) return null
  const ms = new Date(order.value.payment_deadline).getTime() - Date.now()
  if (ms <= 0) return 0
  return Math.floor(ms / (1000 * 60 * 60))
})
const isPaymentUrgent = computed(
  () =>
    order.value?.status === 'pending_payment' &&
    remainingHours.value !== null &&
    remainingHours.value < 6,
)

// ── Format helpers ────────────────────────────────────────────────────
function fmtMoney(n: number | null): string {
  if (n == null || !Number.isFinite(Number(n))) return '—'
  return `NT$ ${Number(n).toLocaleString('zh-TW')}`
}
function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const shippingTypeLabel: Record<OrderDetail['shipping_type'], string> = {
  home: '宅配到府',
  seven_eleven: '7-11 店到店',
  family_mart: '全家店到店',
}
const shipmentTypeLabel: Record<Shipment['shipment_type'], string> = {
  fulfilled: '現貨',
  preorder: '預購',
}
const shipmentStatusLabel: Record<Shipment['status'], string> = {
  pending: '待出貨',
  shipped: '已出貨',
  delivered: '已送達',
}

function specSummary(spec: Record<string, unknown>): string {
  const parts: string[] = []
  if (spec.canvas_w_cm && spec.canvas_h_cm) parts.push(`${spec.canvas_w_cm}×${spec.canvas_h_cm}cm`)
  if (spec.detail) parts.push(String(spec.detail))
  if (spec.difficulty) parts.push(String(spec.difficulty))
  return parts.join(' · ')
}

function copyOrderNumber() {
  if (!order.value) return
  navigator.clipboard?.writeText(order.value.order_number).catch(() => {})
}

// ── Recompute mutations 在 orderId 變動時 — 雖然此頁通常 id 不變
// 但 router.push('/admin/orders/:id') 切換時 mutation orderId 已過期；
// 簡化：頁面靠 :key="orderId" 強制重建（在 router 配置或父元件可控）。
// 此處假設 id 不會在頁內變動。
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/orders')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回訂單列表
    </button>
  </div>

  <!-- Loading -->
  <div v-if="isLoading" class="flex items-center justify-center py-20 text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    <span class="ml-2 text-[13px]">載入中...</span>
  </div>

  <!-- Error -->
  <div
    v-else-if="isError"
    class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗：{{ (error as { message?: string })?.message ?? '未知錯誤' }}
  </div>

  <!-- Loaded -->
  <template v-else-if="order">
    <header class="mb-7 pb-5 border-b border-line-hairline flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2 flex-wrap">
          <h1 class="font-display text-ink-strong text-[24px] leading-[32px] tracking-[-0.005em]">
            訂單
            <button
              type="button"
              class="font-mono text-[22px] text-ink-strong hover:underline ml-1"
              :title="'點擊複製'"
              @click="copyOrderNumber"
            >
              {{ order.order_number }}
            </button>
          </h1>
          <OrderStatusBadge :status="order.status" />
        </div>
        <p class="mt-1 text-[13px] text-ink-muted">下單於 {{ fmtDateTime(order.created_at) }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <Button v-if="canConfirmPayment" variant="primary" @click="openConfirmStatus('paid')">
          <CreditCard :size="14" :stroke-width="1.5" />
          確認付款
        </Button>
        <Button v-if="canStartProcessing" variant="primary" @click="openConfirmStatus('processing')">
          <Package :size="14" :stroke-width="1.5" />
          開始備貨
        </Button>
        <Button
          v-if="canCreateShipment"
          variant="secondary"
          :disabled="!order.shipping_locked"
          :title="order.shipping_locked ? '' : '請先確認出貨資訊'"
          @click="shipmentDialogOpen = true"
        >
          <Truck :size="14" :stroke-width="1.5" />
          出貨
        </Button>
        <Button v-if="canStartRefundProcessing" variant="secondary" @click="refundProcessingOpen = true">
          <RotateCcw :size="14" :stroke-width="1.5" />
          標記退款處理中
        </Button>
        <Button v-if="canFinalizeRefund" variant="primary" @click="refundFinalizeOpen = true">
          <RotateCcw :size="14" :stroke-width="1.5" />
          完成退款
        </Button>
        <Button v-if="canCancel" variant="secondary" @click="openConfirmStatus('cancelled')">
          <XCircle :size="14" :stroke-width="1.5" />
          取消訂單
        </Button>
      </div>
    </header>

    <!-- Urgent payment banner -->
    <div
      v-if="isPaymentUrgent"
      class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.08] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-center gap-2"
    >
      <AlertTriangle :size="14" :stroke-width="1.75" />
      付款期限剩餘不到 6 小時（{{ fmtDateTime(order.payment_deadline) }}）— 此時 flag 付款會發送「緊急」標題 email。
    </div>

    <!-- Refund pending customer confirm -->
    <div
      v-if="isRefunded && !order.refund_confirmed_at"
      class="mb-5 px-4 py-3 border border-state-warning/40 bg-[var(--color-state-warning)]/[0.08] text-state-warning text-[13px] rounded-[var(--radius-xs)]"
    >
      已退款 {{ fmtMoney(order.refund_amount) }}（{{ fmtDateTime(order.refunded_at) }}），請等待客戶確認收到退款。
    </div>
    <div
      v-if="isRefunded && order.refund_confirmed_at"
      class="mb-5 px-4 py-3 border border-line-hairline bg-paper-subtle text-ink-muted text-[13px] rounded-[var(--radius-xs)]"
    >
      退款已完成，客戶已於 {{ fmtDate(order.refund_confirmed_at) }} 確認收到。
    </div>

    <!-- API error -->
    <div
      v-if="apiError"
      class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
    >
      <span class="flex-1">{{ apiError }}</span>
      <button class="text-[12px] underline" @click="apiError = null">關閉</button>
    </div>

    <!-- Layout grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- Main column -->
      <div class="lg:col-span-2 space-y-5">
        <!-- Items -->
        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">商品明細</h2>
          <div class="divide-y divide-line-hairline">
            <div
              v-for="item in order.items"
              :key="item.id"
              class="py-4 first:pt-0 last:pb-0 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3"
            >
              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-medium text-ink-strong">{{ item.product_title_snapshot }}</span>
                  <span
                    v-if="item.is_returned"
                    class="inline-flex items-center px-2 h-[20px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-paper-subtle text-ink-muted"
                  >
                    已退回
                  </span>
                </div>
                <p class="mt-1 text-[12px] text-ink-muted">{{ specSummary(item.variant_spec_snapshot) }}</p>

                <div class="mt-2 flex items-center gap-3 text-[12px] text-ink-default">
                  <span>{{ fmtMoney(item.unit_price) }} × {{ item.quantity }}</span>
                  <span v-if="item.preorder_qty > 0" class="text-ink-muted">
                    （現貨 {{ item.fulfilled_qty }} + 預購 {{ item.preorder_qty }}）
                  </span>
                </div>

                <ProductionProgressRow
                  v-if="item.production_progress"
                  class="mt-3"
                  :progress="item.production_progress"
                  :order-status="order.status"
                  :pending="updateProgress.isPending.value"
                  @advance="(s: 'manufacturing' | 'packaging' | 'ready_to_ship') => doUpdateProgress(item.production_progress!.id, s)"
                />
              </div>
              <div class="md:text-right text-ink-strong font-mono">
                {{ fmtMoney(item.unit_price * item.quantity) }}
              </div>
            </div>
          </div>
        </Card>

        <!-- Shipments -->
        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">出貨</h2>
          <div v-if="order.shipments.length === 0" class="text-[13px] text-ink-muted">
            尚未建立任何出貨批次
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="s in order.shipments"
              :key="s.id"
              class="border border-line-hairline rounded-[var(--radius-xs)] p-3 text-[13px]"
            >
              <div class="flex items-center justify-between flex-wrap gap-2">
                <div class="flex items-center gap-2">
                  <span class="inline-flex items-center px-2 h-[20px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-paper-subtle text-ink-default">
                    {{ shipmentTypeLabel[s.shipment_type] }}
                  </span>
                  <span class="text-ink-default">{{ shipmentStatusLabel[s.status] }}</span>
                </div>
                <div class="text-ink-muted text-[12px]">
                  <span v-if="s.shipped_at">出貨 {{ fmtDateTime(s.shipped_at) }}</span>
                  <span v-if="s.delivered_at" class="ml-3">送達 {{ fmtDateTime(s.delivered_at) }}</span>
                </div>
              </div>
              <div v-if="s.tracking_number" class="mt-2 font-mono text-[12px] text-ink-strong">
                追蹤號 {{ s.tracking_number }}
              </div>
            </div>
          </div>
        </Card>

        <!-- Payment submissions -->
        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">付款核對表</h2>
          <div v-if="order.payment_submissions.length === 0" class="text-[13px] text-ink-muted">
            客戶尚未提交付款資訊
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="sub in order.payment_submissions"
              :key="sub.id"
              class="border border-line-hairline rounded-[var(--radius-xs)] p-3 text-[13px]"
              :class="sub.is_flagged ? 'bg-[var(--color-state-warning)]/[0.04]' : ''"
            >
              <div class="flex items-center justify-between flex-wrap gap-2">
                <div class="flex items-center gap-3">
                  <span class="font-mono text-ink-strong">{{ fmtMoney(sub.transfer_amount) }}</span>
                  <span class="text-ink-muted">{{ sub.transfer_date }} {{ sub.transfer_time }}</span>
                  <span class="text-ink-muted">末五碼 <span class="font-mono">{{ sub.account_last5 }}</span></span>
                </div>
                <div class="flex items-center gap-2">
                  <span
                    v-if="sub.is_flagged"
                    class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-[var(--color-state-warning)]/[0.18] text-state-warning"
                  >
                    <Flag :size="11" :stroke-width="1.5" class="mr-1" />
                    已 flag
                  </span>
                  <button
                    v-else-if="canConfirmPayment"
                    type="button"
                    class="text-[12px] text-ink-muted hover:text-ink-strong transition-colors"
                    @click="flagSubmissionId = sub.id"
                  >
                    Flag 為有誤
                  </button>
                </div>
              </div>
              <p v-if="sub.notes" class="mt-2 text-[12px] text-ink-muted whitespace-pre-line">{{ sub.notes }}</p>
            </div>
          </div>
        </Card>

        <!-- Customer notes (客戶下單時填的備註) -->
        <Card v-if="order.customer_notes">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">客戶備註</h2>
            <span class="text-[11px] text-ink-muted">下單時客戶填寫</span>
          </div>
          <p class="text-[14px] text-ink-default whitespace-pre-line leading-[1.7]">{{ order.customer_notes }}</p>
        </Card>

        <!-- Admin notes -->
        <Card>
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">內部備註</h2>
            <span class="text-[11px] text-ink-muted">客戶看不到</span>
          </div>
          <Textarea v-model="localNotes" :rows="5" :maxlength="2000" placeholder="管理員專用備註..." @focus="notesEditing = true" />
          <div v-if="notesEditing" class="mt-3 flex items-center justify-end gap-2">
            <Button
              variant="secondary"
              @click="
                () => {
                  notesEditing = false
                  localNotes = order!.admin_notes ?? ''
                }
              "
            >
              取消
            </Button>
            <Button variant="primary" :disabled="updateNotes.isPending.value" @click="saveNotes">
              <Loader2 v-if="updateNotes.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
              儲存
            </Button>
          </div>
        </Card>
      </div>

      <!-- Side column -->
      <div class="space-y-5">
        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">客戶</h2>
          <p class="text-[13px] text-ink-strong">{{ order.user_name }}</p>
          <p class="text-[12px] text-ink-muted">{{ order.user_email }}</p>
        </Card>

        <Card>
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-display text-ink-strong text-[16px] leading-[24px]">收件資訊</h2>
            <span
              v-if="order.shipping_locked"
              class="inline-flex items-center px-2 h-[20px] text-[10px] tracking-[0.18em] uppercase rounded-[var(--radius-xs)] bg-state-success/[0.18] text-state-success"
            >✓ 已確認</span>
            <span
              v-else
              class="inline-flex items-center px-2 h-[20px] text-[10px] tracking-[0.18em] uppercase rounded-[var(--radius-xs)] bg-state-warning/[0.18] text-state-warning"
            >⚠ 未確認</span>
          </div>
          <p class="text-[13px] text-ink-strong">{{ order.shipping_snapshot.recipient_name }}</p>
          <p class="text-[12px] text-ink-muted">{{ order.shipping_snapshot.phone }}</p>
          <p class="text-[12px] text-ink-default mt-2">
            <span class="text-ink-muted">取貨方式：</span>{{ shippingTypeLabel[order.shipping_type] }}
          </p>
          <p v-if="order.shipping_snapshot.address_detail" class="text-[12px] text-ink-default mt-1">
            {{ order.shipping_snapshot.city }}{{ order.shipping_snapshot.district }} {{ order.shipping_snapshot.address_detail }}
          </p>
          <p v-if="order.shipping_snapshot.store_name" class="text-[12px] text-ink-default mt-1">
            {{ order.shipping_snapshot.store_name }}（門市 {{ order.shipping_snapshot.store_id }}）
          </p>
          <p v-if="order.shipping_snapshot.notify_email" class="text-[12px] text-ink-muted mt-2">
            通知 Email：{{ order.shipping_snapshot.notify_email }}
          </p>
          <p v-else class="text-[12px] text-ink-muted mt-2 italic">通知 Email：fallback 用 {{ order.user_email }}</p>

          <!-- 修改 / 確認 actions -->
          <div v-if="canEditShipping || canLockShipping" class="mt-4 pt-3 border-t border-line-hairline flex items-center gap-2 flex-wrap">
            <Button v-if="canEditShipping" variant="secondary" @click="shippingEditOpen = true">
              <Pencil :size="14" :stroke-width="1.5" />
              修改出貨資訊
            </Button>
            <Button
              v-if="canLockShipping"
              variant="primary"
              :disabled="lockShippingMut.isPending.value"
              @click="lockShippingMut.mutate()"
            >
              <Loader2 v-if="lockShippingMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
              <Check v-else :size="14" :stroke-width="1.5" />
              確認出貨資訊
            </Button>
          </div>
          <p
            v-if="order.shipping_locked"
            class="mt-3 text-[11px] text-ink-muted"
          >已鎖定 — 出貨資訊無法再修改（包裹已建單後永久鎖死）</p>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">金額</h2>
          <dl class="text-[13px] space-y-1.5">
            <div class="flex justify-between"><dt class="text-ink-muted">小計</dt><dd class="font-mono">{{ fmtMoney(order.subtotal) }}</dd></div>
            <div v-if="order.discount_amount > 0" class="flex justify-between">
              <dt class="text-ink-muted">折扣<span v-if="order.discount_source" class="text-[11px] ml-1">({{ order.discount_source === 'coupon' ? '券' : '促銷' }})</span></dt>
              <dd class="font-mono text-state-success">-{{ fmtMoney(order.discount_amount) }}</dd>
            </div>
            <div class="flex justify-between"><dt class="text-ink-muted">運費</dt><dd class="font-mono">{{ fmtMoney(order.shipping_fee) }}</dd></div>
            <div class="flex justify-between pt-1.5 border-t border-line-hairline mt-1.5">
              <dt class="text-ink-strong font-medium">總計</dt><dd class="font-mono text-ink-strong font-medium">{{ fmtMoney(order.total) }}</dd>
            </div>
            <div v-if="order.refund_amount" class="flex justify-between text-state-warning">
              <dt>退款</dt><dd class="font-mono">-{{ fmtMoney(order.refund_amount) }}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">時間軸</h2>
          <ul class="text-[12px] space-y-1.5">
            <li class="flex justify-between"><span class="text-ink-muted">建立</span><span class="font-mono">{{ fmtDateTime(order.created_at) }}</span></li>
            <li v-if="order.payment_deadline" class="flex justify-between"><span class="text-ink-muted">付款期限</span><span class="font-mono">{{ fmtDateTime(order.payment_deadline) }}</span></li>
            <li v-if="order.paid_at" class="flex justify-between"><span class="text-ink-muted">付款確認</span><span class="font-mono">{{ fmtDateTime(order.paid_at) }}</span></li>
            <li v-if="order.completed_at" class="flex justify-between"><span class="text-ink-muted">完成</span><span class="font-mono">{{ fmtDateTime(order.completed_at) }}</span></li>
            <li v-if="order.refunded_at" class="flex justify-between"><span class="text-ink-muted">退款</span><span class="font-mono">{{ fmtDateTime(order.refunded_at) }}</span></li>
          </ul>
        </Card>
      </div>
    </div>

    <!-- Dialogs -->
    <ConfirmStatusDialog
      :target="confirmStatusTarget"
      :pending="updateStatus.isPending.value"
      @close="confirmStatusTarget = null"
      @confirm="(t) => doConfirmStatus(t)"
    />
    <ShipmentDialog
      :open="shipmentDialogOpen"
      :order="order"
      :pending="createShipment.isPending.value"
      @close="shipmentDialogOpen = false"
      @confirm="(t) => doShipment(t)"
    />
    <PaymentFlagDialog
      :submission-id="flagSubmissionId"
      :submission="(order.payment_submissions.find((s) => s.id === flagSubmissionId) ?? null) as PaymentSubmission | null"
      :remaining-hours="remainingHours"
      :pending="flagSub.isPending.value"
      @close="flagSubmissionId = null"
      @confirm="(note) => doFlagSubmission(flagSubmissionId!, note)"
    />
    <RefundProcessingDialog
      :open="refundProcessingOpen"
      :pending="updateStatus.isPending.value"
      @close="refundProcessingOpen = false"
      @confirm="(reason) => doRefundProcessing(reason)"
    />
    <RefundFinalizeDialog
      :open="refundFinalizeOpen"
      :order="order"
      :pending="refund.isPending.value"
      @close="refundFinalizeOpen = false"
      @confirm="(p) => doRefund(p)"
    />

    <!-- 修改出貨資訊 Dialog -->
    <Dialog
      :open="shippingEditOpen"
      title="修改出貨資訊"
      @close="shippingEditOpen = false"
    >
      <div class="space-y-3">
        <p class="text-[12px] text-ink-muted leading-[1.7]">
          配送方式（{{ shippingTypeLabel[order.shipping_type] }}）不可修改 — 若需要切換請取消訂單後重下。
        </p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <Label>收件人</Label>
            <Input v-model="shippingForm.recipient_name" />
          </div>
          <div>
            <Label>電話 (09xxxxxxxx)</Label>
            <Input v-model="shippingForm.phone" />
          </div>
        </div>
        <div>
          <Label>通知 Email</Label>
          <Input v-model="shippingForm.email" type="email" />
        </div>

        <template v-if="order.shipping_type === 'home'">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <Label>縣市</Label>
              <Input v-model="shippingForm.city" placeholder="台北市" />
            </div>
            <div>
              <Label>行政區</Label>
              <Input v-model="shippingForm.district" placeholder="信義區" />
            </div>
          </div>
          <div>
            <Label>地址</Label>
            <Input v-model="shippingForm.address_detail" />
          </div>
        </template>

        <template v-else>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <Label>門市代碼</Label>
              <Input v-model="shippingForm.store_id" />
            </div>
            <div>
              <Label>門市名稱</Label>
              <Input v-model="shippingForm.store_name" />
            </div>
          </div>
        </template>

        <p
          v-if="shippingEditErr"
          class="px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[12px] rounded-[var(--radius-xs)]"
        >{{ shippingEditErr }}</p>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <Button variant="secondary" @click="shippingEditOpen = false">取消</Button>
          <Button
            variant="primary"
            :disabled="updateShippingMut.isPending.value"
            @click="submitShippingEdit"
          >
            <Loader2 v-if="updateShippingMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
            儲存
          </Button>
        </div>
      </template>
    </Dialog>
  </template>
</template>
