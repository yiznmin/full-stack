<script setup lang="ts">
import { ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Textarea from '@/shared/ui/Textarea.vue'

const props = defineProps<{
  open: boolean
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [reason: string]
}>()

const reason = ref('')
const error = ref<string | null>(null)

watch(
  () => props.open,
  (v) => {
    if (v) {
      reason.value = ''
      error.value = null
    }
  },
)

function submit() {
  const t = reason.value.trim()
  if (t.length < 2) {
    error.value = '請填寫退款原因（至少 2 字）'
    return
  }
  if (t.length > 500) {
    error.value = '說明請在 500 字內'
    return
  }
  emit('confirm', t)
}
</script>

<template>
  <Dialog :open="open" title="標記退款處理中" size="md" @close="emit('close')">
    <div class="space-y-3 text-[13px]">
      <p class="text-ink-default">
        標記後訂單狀態變為「退款處理中」，並寄信給客戶「您的退款申請已受理」。
        <b>此時尚未實際退款</b>，庫存與優惠券不會回補。完成銀行轉帳後，再進入「完成退款」步驟。
      </p>

      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">退款原因（會記錄到訂單備註）</label>
        <Textarea
          v-model="reason"
          :rows="3"
          :maxlength="500"
          placeholder="例：客戶不滿意品質 / 商品瑕疵..."
        />
        <p v-if="error" class="mt-1 text-[12px] text-state-danger">{{ error }}</p>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">標記退款處理中</Button>
    </template>
  </Dialog>
</template>
