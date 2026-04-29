<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import type { OrderDetail, ShipmentType } from '../api'

const props = defineProps<{
  open: boolean
  order: OrderDetail
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [type: ShipmentType]
}>()

// 計算可建立哪幾種 shipment
const totals = computed(() => {
  let fulfilled = 0
  let preorder = 0
  for (const i of props.order.items) {
    fulfilled += i.fulfilled_qty
    preorder += i.preorder_qty
  }
  return { fulfilled, preorder }
})

const existingTypes = computed(() => new Set(props.order.shipments.map((s) => s.shipment_type)))

const canFulfilled = computed(
  () => totals.value.fulfilled > 0 && !existingTypes.value.has('fulfilled'),
)
const canPreorder = computed(
  () => totals.value.preorder > 0 && !existingTypes.value.has('preorder'),
)

const selected = ref<ShipmentType>('fulfilled')

watch(
  () => props.open,
  (v) => {
    if (v) {
      selected.value = canFulfilled.value ? 'fulfilled' : 'preorder'
    }
  },
)

const notifyEmail = computed(
  () => props.order.shipping_snapshot.notify_email || `${props.order.user_email}（fallback）`,
)
</script>

<template>
  <Dialog :open="open" title="建立出貨" size="md" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <div>
        <p class="text-ink-strong font-medium mb-1">收件人</p>
        <p class="text-ink-default">
          {{ order.shipping_snapshot.recipient_name }} · {{ order.shipping_snapshot.phone }}
        </p>
      </div>

      <div>
        <p class="text-ink-strong font-medium mb-1">送達地址</p>
        <p v-if="order.shipping_snapshot.address_detail" class="text-ink-default">
          {{ order.shipping_snapshot.city }}{{ order.shipping_snapshot.district }}
          {{ order.shipping_snapshot.address_detail }}
        </p>
        <p v-else-if="order.shipping_snapshot.store_name" class="text-ink-default">
          {{ order.shipping_snapshot.store_name }}（門市 {{ order.shipping_snapshot.store_id }}）
        </p>
      </div>

      <div>
        <p class="text-ink-strong font-medium mb-1">物流通知 Email</p>
        <p class="text-ink-default">{{ notifyEmail }}</p>
      </div>

      <hr class="border-line-hairline" />

      <div>
        <p class="text-ink-strong font-medium mb-2">出貨類型</p>
        <div class="space-y-2">
          <label
            v-if="canFulfilled"
            class="flex items-center gap-2 p-3 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle"
            :class="selected === 'fulfilled' ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
          >
            <input v-model="selected" type="radio" value="fulfilled" name="shipment-type" />
            <span class="flex-1">現貨出貨（{{ totals.fulfilled }} 件）</span>
          </label>
          <label
            v-if="canPreorder"
            class="flex items-center gap-2 p-3 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle"
            :class="selected === 'preorder' ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
          >
            <input v-model="selected" type="radio" value="preorder" name="shipment-type" />
            <span class="flex-1">預購出貨（{{ totals.preorder }} 件）</span>
          </label>
          <p v-if="!canFulfilled && !canPreorder" class="text-ink-muted">
            此訂單已建立所有可能的出貨批次。
          </p>
        </div>
      </div>

      <p class="text-[12px] text-ink-muted">
        確認後系統會呼叫 ECpay API 建立物流訂單並取得追蹤號碼。若 ECpay 暫時無法連線，訂單狀態不變，可重試。
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button
        variant="primary"
        :disabled="pending || (!canFulfilled && !canPreorder)"
        @click="emit('confirm', selected)"
      >
        建立出貨
      </Button>
    </template>
  </Dialog>
</template>
