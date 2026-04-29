<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'
import { AlertTriangle } from 'lucide-vue-next'

import {
  COUPON_TYPE_LABEL,
  type CouponConfig,
  type CouponType,
  type DiscountType,
} from '../api'

const props = defineProps<{
  open: boolean
  config: CouponConfig | null
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [
    payload: {
      is_active: boolean
      discount_type: DiscountType
      discount_value: number
      min_purchase: number | null
      params: Record<string, unknown>
    },
  ]
}>()

const isActive = ref(true)
const discountType = ref<DiscountType>('fixed')
const discountValue = ref('')
const minPurchase = ref('')
// type-specific params
const validDays = ref('')
const triggerThreshold = ref('')
const startAt = ref('')
const endAt = ref('')

const errors = ref<Record<string, string>>({})

watch(
  () => props.config,
  (c) => {
    if (!c) return
    isActive.value = c.is_active
    discountType.value = c.discount_type
    discountValue.value = String(c.discount_value)
    minPurchase.value = c.min_purchase != null ? String(c.min_purchase) : ''
    validDays.value =
      typeof c.params?.valid_days === 'number' ? String(c.params.valid_days) : ''
    triggerThreshold.value =
      typeof c.params?.trigger_threshold === 'number'
        ? String(c.params.trigger_threshold)
        : ''
    startAt.value =
      typeof c.params?.start_at === 'string' ? (c.params.start_at as string).slice(0, 10) : ''
    endAt.value =
      typeof c.params?.end_at === 'string' ? (c.params.end_at as string).slice(0, 10) : ''
    errors.value = {}
  },
  { immediate: true },
)

const couponType = computed<CouponType | undefined>(() => props.config?.coupon_type)

const showValidDays = computed(
  () =>
    couponType.value === 'new_user' ||
    couponType.value === 'spend_reward' ||
    couponType.value === 'returning_loyal',
)
const showTriggerThreshold = computed(
  () =>
    couponType.value === 'spend_reward' ||
    couponType.value === 'returning_loyal' ||
    couponType.value === 'auto_checkout',
)
const showDateRange = computed(() => couponType.value === 'auto_checkout')

const discountTypeOptions = [
  { value: 'percentage', label: '百分比 %' },
  { value: 'fixed', label: '固定金額 NT$' },
]

function validate(): boolean {
  const errs: Record<string, string> = {}
  const dv = Number(discountValue.value)
  if (!Number.isFinite(dv) || dv <= 0) errs.discount_value = '折扣值必須 > 0'
  if (discountType.value === 'percentage' && dv > 100) {
    errs.discount_value = '百分比不可超過 100'
  }
  const mp = minPurchase.value ? Number(minPurchase.value) : null
  if (mp != null && (!Number.isFinite(mp) || mp < 0)) errs.min_purchase = '門檻必須 ≥ 0'

  if (showValidDays.value && validDays.value) {
    const v = Number(validDays.value)
    if (!Number.isFinite(v) || v <= 0 || !Number.isInteger(v)) errs.valid_days = '有效天數必須是正整數'
  }
  if (showTriggerThreshold.value && triggerThreshold.value) {
    const v = Number(triggerThreshold.value)
    if (!Number.isFinite(v) || v < 0) errs.trigger_threshold = '門檻必須 ≥ 0'
  }
  if (showDateRange.value && startAt.value && endAt.value) {
    if (new Date(startAt.value) > new Date(endAt.value)) errs.date_range = '結束日不可早於開始日'
  }

  errors.value = errs
  return Object.keys(errs).length === 0
}

function buildParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { ...(props.config?.params ?? {}) }
  if (showValidDays.value) {
    params.valid_days = validDays.value ? Number(validDays.value) : null
  }
  if (showTriggerThreshold.value) {
    params.trigger_threshold = triggerThreshold.value ? Number(triggerThreshold.value) : null
  }
  if (showDateRange.value) {
    params.start_at = startAt.value ? new Date(startAt.value).toISOString() : null
    params.end_at = endAt.value ? new Date(endAt.value + 'T23:59:59').toISOString() : null
  }
  return params
}

function submit() {
  if (!validate()) return
  emit('confirm', {
    is_active: isActive.value,
    discount_type: discountType.value,
    discount_value: Number(discountValue.value),
    min_purchase: minPurchase.value ? Number(minPurchase.value) : null,
    params: buildParams(),
  })
}
</script>

<template>
  <Dialog
    :open="open"
    :title="config ? `編輯：${COUPON_TYPE_LABEL[config.coupon_type]}` : ''"
    size="md"
    @close="emit('close')"
  >
    <div v-if="config" class="space-y-4 text-[13px]">
      <!-- 啟用 -->
      <div>
        <label class="flex items-center gap-2">
          <input v-model="isActive" type="checkbox" />
          <span class="text-ink-strong font-medium">啟用此券類型</span>
        </label>
        <div
          v-if="!isActive"
          class="mt-2 px-3 py-2 border border-state-warning/40 bg-[var(--color-state-warning)]/[0.06] text-state-warning text-[12px] rounded-[var(--radius-xs)] flex items-start gap-2"
        >
          <AlertTriangle :size="12" :stroke-width="1.75" class="mt-0.5 shrink-0" />
          <span>停用後不再自動發放，但已發放的券仍依當時快照生效。</span>
        </div>
      </div>

      <!-- 折扣方式 -->
      <div>
        <Label>折扣方式</Label>
        <Select v-model="discountType" :options="discountTypeOptions" />
      </div>

      <!-- 折扣值 -->
      <div>
        <Label>折扣值（{{ discountType === 'percentage' ? '百分比' : 'NT$' }}）</Label>
        <Input v-model="discountValue" type="number" :min="1" :max="discountType === 'percentage' ? 100 : undefined" />
        <p v-if="errors.discount_value" class="mt-1 text-[12px] text-state-danger">{{ errors.discount_value }}</p>
      </div>

      <!-- 最低消費 -->
      <div>
        <Label>使用時的最低消費門檻（NT$，可空）</Label>
        <Input v-model="minPurchase" type="number" min="0" placeholder="留空表示無門檻" />
        <p v-if="errors.min_purchase" class="mt-1 text-[12px] text-state-danger">{{ errors.min_purchase }}</p>
      </div>

      <!-- valid_days（new_user / spend_reward / returning_loyal）-->
      <div v-if="showValidDays">
        <Label>發放後有效天數</Label>
        <Input v-model="validDays" type="number" min="1" />
        <p v-if="errors.valid_days" class="mt-1 text-[12px] text-state-danger">{{ errors.valid_days }}</p>
      </div>

      <!-- trigger_threshold（spend_reward / returning_loyal / auto_checkout）-->
      <div v-if="showTriggerThreshold">
        <Label>觸發門檻（訂單金額達 NT$ 才{{ couponType === 'auto_checkout' ? '套用' : '發放' }}）</Label>
        <Input v-model="triggerThreshold" type="number" min="0" />
        <p v-if="errors.trigger_threshold" class="mt-1 text-[12px] text-state-danger">{{ errors.trigger_threshold }}</p>
      </div>

      <!-- start_at / end_at（auto_checkout 限定）-->
      <div v-if="showDateRange" class="grid grid-cols-2 gap-2">
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
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">儲存</Button>
    </template>
  </Dialog>
</template>
