<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import type { OrderDetail } from '../api'

const props = defineProps<{
  open: boolean
  order: OrderDetail
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [
    payload: { refund_amount: number; returned_item_ids: string[]; cancel_reason: string },
  ]
}>()

const checkedIds = ref<Set<string>>(new Set())
const amountStr = ref('')
const reason = ref('')
const errors = ref<Record<string, string>>({})

watch(
  () => props.open,
  (v) => {
    if (v) {
      checkedIds.value = new Set(props.order.items.map((i) => i.id))
      amountStr.value = String(props.order.total)
      reason.value = ''
      errors.value = {}
    }
  },
)

const isAllChecked = computed(() => checkedIds.value.size === props.order.items.length)
const isSomeChecked = computed(() => checkedIds.value.size > 0 && !isAllChecked.value)

function toggle(id: string) {
  const next = new Set(checkedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  checkedIds.value = next
}

function validate(): boolean {
  const errs: Record<string, string> = {}
  const amount = Number(amountStr.value)
  if (!Number.isFinite(amount) || amount <= 0) errs.amount = '退款金額必須 > 0'
  else if (amount > Number(props.order.total)) errs.amount = `不可超過訂單金額 NT$ ${props.order.total}`

  if (checkedIds.value.size === 0) errs.items = '至少勾選一項退回'

  const r = reason.value.trim()
  if (r.length < 2) errs.reason = '請填寫退款原因'
  else if (r.length > 500) errs.reason = '說明請在 500 字內'

  errors.value = errs
  return Object.keys(errs).length === 0
}

function submit() {
  if (!validate()) return
  emit('confirm', {
    refund_amount: Math.round(Number(amountStr.value)),
    returned_item_ids: Array.from(checkedIds.value),
    cancel_reason: reason.value.trim(),
  })
}

function fmtMoney(n: number) {
  return `NT$ ${n.toLocaleString('zh-TW')}`
}

function specSummary(spec: Record<string, unknown>): string {
  const parts: string[] = []
  if (spec.canvas_w_cm && spec.canvas_h_cm) parts.push(`${spec.canvas_w_cm}×${spec.canvas_h_cm}cm`)
  if (spec.detail) parts.push(String(spec.detail))
  if (spec.difficulty) parts.push(String(spec.difficulty))
  return parts.join(' · ')
}
</script>

<template>
  <Dialog :open="open" title="完成退款" size="lg" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <div class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <p class="text-ink-strong font-medium">訂單 {{ order.order_number }}</p>
        <p class="text-ink-muted text-[12px]">總額 {{ fmtMoney(Number(order.total)) }}</p>
      </div>

      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">退款金額（NT$）</label>
        <Input v-model="amountStr" type="number" min="1" :max="String(order.total)" />
        <p v-if="errors.amount" class="mt-1 text-[12px] text-state-danger">{{ errors.amount }}</p>
      </div>

      <div>
        <p class="block text-[13px] text-ink-strong mb-2">
          退回項目（勾選會回補對應庫存；勾滿全部 → 全額退款；僅勾部分 → 部分退款）
        </p>
        <div class="space-y-2">
          <label
            v-for="item in order.items"
            :key="item.id"
            class="flex items-start gap-3 p-3 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle"
            :class="checkedIds.has(item.id) ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
          >
            <input
              type="checkbox"
              :checked="checkedIds.has(item.id)"
              class="mt-0.5"
              @change="toggle(item.id)"
            />
            <div class="flex-1">
              <p class="text-ink-strong">{{ item.product_title_snapshot }}</p>
              <p class="text-[12px] text-ink-muted">{{ specSummary(item.variant_spec_snapshot) }} · 數量 {{ item.quantity }}</p>
            </div>
            <div class="font-mono text-ink-strong">{{ fmtMoney(Number(item.unit_price) * item.quantity) }}</div>
          </label>
        </div>
        <p v-if="errors.items" class="mt-1 text-[12px] text-state-danger">{{ errors.items }}</p>
        <p class="mt-2 text-[12px] text-ink-muted">
          目前選擇：
          <span v-if="isAllChecked" class="text-state-success">全額退款（refunded）</span>
          <span v-else-if="isSomeChecked" class="text-state-warning">部分退款（partially_refunded）</span>
          <span v-else class="text-ink-muted">尚未勾選</span>
        </p>
      </div>

      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">退款原因</label>
        <Textarea v-model="reason" :rows="3" :maxlength="500" placeholder="例：商品瑕疵、客戶不滿意..." />
        <p v-if="errors.reason" class="mt-1 text-[12px] text-state-danger">{{ errors.reason }}</p>
      </div>

      <p class="text-[12px] text-ink-muted">
        確認後系統會立即執行：庫存回補（勾選項）、優惠券處理、寄客戶確認 email。
        <b>請務必先實際完成銀行轉帳再按確認。</b>
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">確認退款</Button>
    </template>
  </Dialog>
</template>
