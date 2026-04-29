<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import { AlertTriangle } from 'lucide-vue-next'
import type { PaymentSubmission } from '../api'

const props = defineProps<{
  submissionId: string | null
  submission: PaymentSubmission | null
  remainingHours: number | null
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [adminNote: string]
}>()

const open = computed(() => props.submissionId !== null)

const note = ref('')
const error = ref<string | null>(null)

watch(open, (v) => {
  if (v) {
    note.value = ''
    error.value = null
  }
})

const isUrgent = computed(
  () => props.remainingHours !== null && props.remainingHours < 6,
)

function submit() {
  const trimmed = note.value.trim()
  if (trimmed.length < 2) {
    error.value = '請填寫具體原因（至少 2 字）'
    return
  }
  if (trimmed.length > 500) {
    error.value = '說明請在 500 字內'
    return
  }
  emit('confirm', trimmed)
}
</script>

<template>
  <Dialog :open="open" title="標記付款資訊有誤" size="md" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <div v-if="submission" class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <div class="font-mono text-ink-strong">
          NT$ {{ submission.transfer_amount.toLocaleString() }}
        </div>
        <div class="text-ink-muted text-[12px]">
          {{ submission.transfer_date }} {{ submission.transfer_time }} · 末五碼 {{ submission.account_last5 }}
        </div>
      </div>

      <div
        v-if="isUrgent"
        class="px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[12px] rounded-[var(--radius-xs)] flex items-start gap-2"
      >
        <AlertTriangle :size="14" :stroke-width="1.75" class="mt-0.5" />
        <span>付款期限剩餘不到 6 小時，flag 後通知客戶的 email 標題會變成「<b>緊急：還剩 X 小時重新填寫</b>」。</span>
      </div>

      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">說明哪裡有誤（會放進 email 給客戶）</label>
        <Textarea
          v-model="note"
          :rows="4"
          :maxlength="500"
          placeholder="例：金額不符、帳號末五碼錯誤..."
        />
        <p v-if="error" class="mt-1 text-[12px] text-state-danger">{{ error }}</p>
        <p v-else class="mt-1 text-[11px] text-ink-muted text-right">{{ note.length }} / 500</p>
      </div>

      <p class="text-[12px] text-ink-muted">
        flag 後系統會將付款期限重設為 <b>min(now+24h, created+48h)</b>，並寄信請客戶重新填寫。
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">送出 flag</Button>
    </template>
  </Dialog>
</template>
