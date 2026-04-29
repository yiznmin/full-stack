<script setup lang="ts">
import { computed } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'

type Target = 'paid' | 'processing' | 'completed' | 'cancelled'

const props = defineProps<{
  target: Target | null
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [target: Target]
}>()

const meta = computed<Record<Target, { title: string; body: string; primaryLabel: string; danger?: boolean }>>(() => ({
  paid: {
    title: '確認付款？',
    body: '確認付款後，系統會自動為每筆商品建立生產進度，並寄出付款確認 email 給客戶。此動作無法復原。',
    primaryLabel: '確認付款',
  },
  processing: {
    title: '開始備貨？',
    body: '訂單將進入備貨中。',
    primaryLabel: '開始備貨',
  },
  completed: {
    title: '標記為已完成？',
    body: '一般情況請等待 ECpay webhook 或客戶確認收貨自動完成。手動完成請確定貨已送達。',
    primaryLabel: '標記完成',
  },
  cancelled: {
    title: '取消訂單？',
    body: '取消後將回補庫存與優惠券，並寄出取消通知 email 給客戶。此動作無法復原。',
    primaryLabel: '取消訂單',
    danger: true,
  },
}))

const open = computed(() => props.target !== null)
</script>

<template>
  <Dialog :open="open" :title="target ? meta[target].title : ''" size="sm" @close="emit('close')">
    <p v-if="target" class="text-[13px] text-ink-default leading-[20px]">{{ meta[target].body }}</p>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button
        :variant="target && meta[target].danger ? 'danger' : 'primary'"
        :disabled="pending"
        @click="target && emit('confirm', target)"
      >
        {{ target ? meta[target].primaryLabel : '' }}
      </Button>
    </template>
  </Dialog>
</template>
