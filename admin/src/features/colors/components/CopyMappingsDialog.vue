<script setup lang="ts">
import { computed, ref } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import { Loader2, AlertTriangle } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [sourceJobId: string]
}>()

const sourceId = ref('')
const error = ref<string | null>(null)

function submit() {
  const id = sourceId.value.trim()
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
    error.value = 'Job ID 格式不正確（UUID）'
    return
  }
  error.value = null
  emit('confirm', id)
}
</script>

<template>
  <Dialog :open="open" title="從其他 job 複製對應" size="md" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <p class="text-ink-default">
        貼上來源 production_job 的完整 UUID，系統會把它的 palette mappings 按 template_id 複製過來。
      </p>
      <p class="text-[12px] text-ink-muted flex items-start gap-1">
        <AlertTriangle :size="12" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span>來源必須已完成顏色對應；複製後仍需點「完成對應」才會觸發 required_ml 計算。</span>
      </p>

      <div>
        <Input v-model="sourceId" placeholder="例：3a4b5c6d-1234-..." class="font-mono" />
        <p v-if="error" class="mt-1 text-[12px] text-state-danger">{{ error }}</p>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">
        <Loader2 v-if="pending" :size="14" :stroke-width="1.5" class="animate-spin" />
        確認複製
      </Button>
    </template>
  </Dialog>
</template>
