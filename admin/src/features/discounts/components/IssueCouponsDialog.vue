<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'

import type { CouponConfig } from '../api'
import { COUPON_TYPE_LABEL, formatDiscount } from '../api'

const props = defineProps<{
  open: boolean
  configs: CouponConfig[]
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [payload: { user_ids: string[]; coupon_config_id: string }]
}>()

const selectedConfigId = ref<string>('')
const userIdsRaw = ref('')
const errors = ref<Record<string, string>>({})

watch(
  () => props.open,
  (v) => {
    if (v) {
      selectedConfigId.value = ''
      userIdsRaw.value = ''
      errors.value = {}
    }
  },
)

// 只列 manual config（其他類型由系統自動發放）
const manualConfigs = computed(() => props.configs.filter((c) => c.coupon_type === 'manual'))

const configOptions = computed(() => {
  if (manualConfigs.value.length === 0) {
    return [{ value: '', label: '— 沒有 manual 設定 —' }]
  }
  return [
    { value: '', label: '— 請選 —' },
    ...manualConfigs.value.map((c) => ({
      value: c.id,
      label: `${COUPON_TYPE_LABEL[c.coupon_type]} · ${formatDiscount(c.discount_type, c.discount_value)}`,
    })),
  ]
})

const parsedUserIds = computed(() => {
  return userIdsRaw.value
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
})

const allValid = computed(() =>
  parsedUserIds.value.every((id) =>
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id),
  ),
)

function validate(): boolean {
  const errs: Record<string, string> = {}
  if (!selectedConfigId.value) errs.config = '請選擇 manual 券類型'
  if (parsedUserIds.value.length === 0) errs.users = '至少貼一筆 user UUID'
  else if (!allValid.value) errs.users = '部分 UUID 格式不正確'
  errors.value = errs
  return Object.keys(errs).length === 0
}

function submit() {
  if (!validate()) return
  emit('confirm', {
    user_ids: parsedUserIds.value,
    coupon_config_id: selectedConfigId.value,
  })
}
</script>

<template>
  <Dialog :open="open" title="批次發放優惠券（manual）" size="md" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <p class="text-ink-muted">
        ⚠️ 第一版用 UUID 多行貼；F13 用戶管理上線後會升級成「從用戶列表勾選」。
      </p>

      <div>
        <Label>券類型</Label>
        <Select v-model="selectedConfigId" :options="configOptions" />
        <p v-if="errors.config" class="mt-1 text-[12px] text-state-danger">{{ errors.config }}</p>
        <p v-if="manualConfigs.length === 0" class="mt-1 text-[12px] text-state-warning">
          目前無 manual 類型 config（請先建立）
        </p>
      </div>

      <div>
        <Label>User UUIDs（一行一個或用逗號分隔）</Label>
        <Textarea
          v-model="userIdsRaw"
          :rows="6"
          placeholder="9b3a8b2c-1234-..."
        />
        <p v-if="errors.users" class="mt-1 text-[12px] text-state-danger">{{ errors.users }}</p>
        <p v-else class="mt-1 text-[11px] text-ink-muted">解析到 {{ parsedUserIds.length }} 個 UUID</p>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">送出發放</Button>
    </template>
  </Dialog>
</template>
