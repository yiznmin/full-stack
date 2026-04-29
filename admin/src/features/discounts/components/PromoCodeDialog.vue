<script setup lang="ts">
import { ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'

import type { DiscountType, PromoCode } from '../api'

const props = defineProps<{
  open: boolean
  /** null = 新增 / 否則編輯 */
  promo: PromoCode | null
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [
    payload: {
      code: string
      discount_type: DiscountType
      discount_value: number
      min_purchase: number | null
      start_at: string | null
      end_at: string | null
      max_total_uses: number | null
      max_per_user: number
      is_active?: boolean
    },
  ]
}>()

const code = ref('')
const discountType = ref<DiscountType>('fixed')
const discountValue = ref('')
const minPurchase = ref('')
const startAt = ref('')
const endAt = ref('')
const maxTotalUses = ref('')
const maxPerUser = ref('1')
const isActive = ref(true)

const errors = ref<Record<string, string>>({})

watch(
  () => [props.open, props.promo],
  () => {
    const p = props.promo
    if (p) {
      code.value = p.code
      discountType.value = p.discount_type
      discountValue.value = String(p.discount_value)
      minPurchase.value = p.min_purchase != null ? String(p.min_purchase) : ''
      startAt.value = p.start_at ? p.start_at.slice(0, 10) : ''
      endAt.value = p.end_at ? p.end_at.slice(0, 10) : ''
      maxTotalUses.value = p.max_total_uses != null ? String(p.max_total_uses) : ''
      maxPerUser.value = String(p.max_per_user)
      isActive.value = p.is_active
    } else {
      code.value = ''
      discountType.value = 'fixed'
      discountValue.value = ''
      minPurchase.value = ''
      startAt.value = ''
      endAt.value = ''
      maxTotalUses.value = ''
      maxPerUser.value = '1'
      isActive.value = true
    }
    errors.value = {}
  },
  { immediate: true },
)

function onCodeInput(e: Event) {
  // 自動 toUpperCase（避免大小寫混淆）
  const v = (e.target as HTMLInputElement).value.toUpperCase()
  code.value = v
  ;(e.target as HTMLInputElement).value = v
}

function validate(): boolean {
  const errs: Record<string, string> = {}
  if (!/^[A-Z0-9_-]{3,40}$/.test(code.value)) {
    errs.code = '代碼僅可含大寫字母、數字、底線、連字號（3-40 字）'
  }
  const dv = Number(discountValue.value)
  if (!Number.isFinite(dv) || dv <= 0) errs.discount_value = '折扣值必須 > 0'
  if (discountType.value === 'percentage' && dv > 100) errs.discount_value = '百分比不可超過 100'
  if (minPurchase.value && Number(minPurchase.value) < 0) errs.min_purchase = '門檻必須 ≥ 0'
  if (maxTotalUses.value && Number(maxTotalUses.value) < 1) errs.max_total_uses = '上限必須 ≥ 1'
  const mpu = Number(maxPerUser.value)
  if (!Number.isInteger(mpu) || mpu < 1) errs.max_per_user = '每人上限必須是正整數'
  if (startAt.value && endAt.value && new Date(startAt.value) > new Date(endAt.value)) {
    errs.date_range = '結束日不可早於開始日'
  }
  errors.value = errs
  return Object.keys(errs).length === 0
}

function submit() {
  if (!validate()) return
  emit('confirm', {
    code: code.value,
    discount_type: discountType.value,
    discount_value: Number(discountValue.value),
    min_purchase: minPurchase.value ? Number(minPurchase.value) : null,
    start_at: startAt.value ? new Date(startAt.value).toISOString() : null,
    end_at: endAt.value ? new Date(endAt.value + 'T23:59:59').toISOString() : null,
    max_total_uses: maxTotalUses.value ? Number(maxTotalUses.value) : null,
    max_per_user: Number(maxPerUser.value),
    ...(props.promo ? { is_active: isActive.value } : {}),
  })
}

const discountTypeOptions = [
  { value: 'percentage', label: '百分比 %' },
  { value: 'fixed', label: '固定金額 NT$' },
]
</script>

<template>
  <Dialog
    :open="open"
    :title="promo ? '編輯促銷碼' : '新增促銷碼'"
    size="md"
    @close="emit('close')"
  >
    <div class="space-y-4 text-[13px]">
      <div>
        <Label>促銷碼（自動轉大寫）</Label>
        <Input :value="code" placeholder="例：SALE2026" @input="onCodeInput" />
        <p v-if="errors.code" class="mt-1 text-[12px] text-state-danger">{{ errors.code }}</p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <Label>折扣方式</Label>
          <Select v-model="discountType" :options="discountTypeOptions" />
        </div>
        <div>
          <Label>折扣值</Label>
          <Input v-model="discountValue" type="number" />
          <p v-if="errors.discount_value" class="mt-1 text-[12px] text-state-danger">{{ errors.discount_value }}</p>
        </div>
      </div>

      <div>
        <Label>最低消費門檻（NT$，可空）</Label>
        <Input v-model="minPurchase" type="number" min="0" placeholder="留空表示無門檻" />
        <p v-if="errors.min_purchase" class="mt-1 text-[12px] text-state-danger">{{ errors.min_purchase }}</p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <Label>活動開始日</Label>
          <Input v-model="startAt" type="date" />
        </div>
        <div>
          <Label>活動結束日</Label>
          <Input v-model="endAt" type="date" />
        </div>
        <p v-if="errors.date_range" class="col-span-2 text-[12px] text-state-danger">{{ errors.date_range }}</p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <Label>總使用上限（可空 = 無限）</Label>
          <Input v-model="maxTotalUses" type="number" min="1" placeholder="留空無限" />
          <p v-if="errors.max_total_uses" class="mt-1 text-[12px] text-state-danger">{{ errors.max_total_uses }}</p>
        </div>
        <div>
          <Label>每人上限</Label>
          <Input v-model="maxPerUser" type="number" min="1" />
          <p v-if="errors.max_per_user" class="mt-1 text-[12px] text-state-danger">{{ errors.max_per_user }}</p>
        </div>
      </div>

      <div v-if="promo">
        <label class="flex items-center gap-2">
          <input v-model="isActive" type="checkbox" />
          <span class="text-ink-strong">啟用此促銷碼</span>
        </label>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">{{ promo ? '儲存' : '建立' }}</Button>
    </template>
  </Dialog>
</template>
