<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Select from '@/shared/ui/Select.vue'
import { Loader2 } from 'lucide-vue-next'

import {
  useCustomPhotoPricesQuery,
  useCustomPhotoSurchargesQuery,
} from '../queries'
import type { CustomRequestDetail, Detail, QuotePayload } from '../api'

const props = defineProps<{
  open: boolean
  request: CustomRequestDetail
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [payload: QuotePayload]
}>()

const detail = ref<Detail>('standard')
const surchargeIds = ref<Set<string>>(new Set())
const overrideStr = ref('')
const note = ref('')
const errors = ref<Record<string, string>>({})

const { data: prices, isLoading: pricesLoading } = useCustomPhotoPricesQuery()
const { data: surcharges, isLoading: surLoading } = useCustomPhotoSurchargesQuery()

watch(
  () => props.open,
  (v) => {
    if (v) {
      detail.value = (props.request.detail as Detail) || 'standard'
      surchargeIds.value = new Set()
      overrideStr.value = ''
      note.value = ''
      errors.value = {}
    }
  },
)

const PRICE_MULTIPLIER = 2.0

const basePrice = computed(() => {
  if (!prices.value || !props.request.canvas_w_cm || !props.request.canvas_h_cm) return null
  const match = prices.value.items.find(
    (p) =>
      p.canvas_w === props.request.canvas_w_cm &&
      p.canvas_h === props.request.canvas_h_cm &&
      p.difficulty === props.request.difficulty,
  )
  return match ? Number(match.price) : null
})

const activeSurcharges = computed(() => surcharges.value?.items.filter((s) => s.is_active) ?? [])

const surchargeTotal = computed(() => {
  let sum = 0
  for (const s of activeSurcharges.value) {
    if (surchargeIds.value.has(s.id)) sum += Number(s.amount)
  }
  return sum
})

const suggestedPrice = computed(() => {
  if (basePrice.value == null) return null
  return Math.round((basePrice.value + surchargeTotal.value) * PRICE_MULTIPLIER)
})

const finalPrice = computed(() => {
  const o = Number(overrideStr.value)
  if (overrideStr.value.trim() && Number.isFinite(o) && o > 0) return Math.round(o)
  return suggestedPrice.value
})

function toggleSurcharge(id: string) {
  const next = new Set(surchargeIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  surchargeIds.value = next
}

const detailOptions = [
  { value: 'rough', label: '粗 rough' },
  { value: 'standard', label: '標準 standard' },
  { value: 'detailed', label: '細緻 detailed' },
  { value: 'premium', label: '高級 premium' },
]

function fmtMoney(n: number | null): string {
  if (n == null) return '—'
  return `NT$ ${n.toLocaleString('zh-TW')}`
}

function validate(): boolean {
  const errs: Record<string, string> = {}
  if (finalPrice.value == null || finalPrice.value <= 0) {
    errs.price = '報價金額必須大於 0'
  }
  errors.value = errs
  return Object.keys(errs).length === 0
}

function submit() {
  if (!validate()) return
  emit('confirm', {
    quoted_price: finalPrice.value!,
    detail: detail.value,
    surcharge_ids: Array.from(surchargeIds.value),
    quote_note: note.value.trim() || null,
  })
}
</script>

<template>
  <Dialog :open="open" title="送出報價" size="lg" @close="emit('close')">
    <div v-if="pricesLoading || surLoading" class="py-12 flex justify-center text-ink-muted">
      <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    </div>

    <div v-else class="space-y-5 text-[13px]">
      <!-- Spec preview -->
      <div class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <p class="text-ink-strong font-medium">客戶申請內容</p>
        <p class="text-ink-muted text-[12px] mt-1">
          畫布 {{ request.canvas_w_cm }}×{{ request.canvas_h_cm }}cm ·
          難易度 {{ request.difficulty || '—' }} ·
          細緻度 {{ request.detail || '—' }}
        </p>
      </div>

      <!-- Detail picker -->
      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">細緻度（影響報價）</label>
        <Select v-model="detail" :options="detailOptions" />
      </div>

      <!-- Surcharges -->
      <div>
        <label class="block text-[13px] text-ink-strong mb-2">加費項目</label>
        <div v-if="activeSurcharges.length === 0" class="text-ink-muted text-[12px]">
          目前無啟用中加費項目
        </div>
        <div v-else class="space-y-1.5">
          <label
            v-for="s in activeSurcharges"
            :key="s.id"
            class="flex items-center gap-3 p-2.5 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle"
            :class="surchargeIds.has(s.id) ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
          >
            <input
              type="checkbox"
              :checked="surchargeIds.has(s.id)"
              @change="toggleSurcharge(s.id)"
            />
            <div class="flex-1">
              <span class="text-ink-default">{{ s.label }}</span>
              <span class="text-[11px] text-ink-muted ml-1">（{{ s.category }}）</span>
            </div>
            <span class="font-mono text-ink-strong">+{{ fmtMoney(Number(s.amount)) }}</span>
          </label>
        </div>
      </div>

      <!-- Calculation breakdown -->
      <div class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <p class="text-[12px] text-ink-muted mb-2">系統建議價格（公式 × {{ PRICE_MULTIPLIER }}）</p>
        <dl class="text-[12px] space-y-1">
          <div class="flex justify-between"><dt>基礎價（{{ request.canvas_w_cm }}×{{ request.canvas_h_cm }} · {{ request.difficulty || '—' }}）</dt><dd class="font-mono">{{ fmtMoney(basePrice) }}</dd></div>
          <div class="flex justify-between"><dt>加費小計</dt><dd class="font-mono">{{ fmtMoney(surchargeTotal) }}</dd></div>
          <div class="flex justify-between pt-1.5 border-t border-line-hairline mt-1.5">
            <dt class="text-ink-strong">建議報價</dt><dd class="font-mono text-ink-strong">{{ fmtMoney(suggestedPrice) }}</dd>
          </div>
        </dl>
      </div>

      <!-- Override -->
      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">
          管理員確認報價（NT$，留空則用建議價）
        </label>
        <Input v-model="overrideStr" type="number" :placeholder="suggestedPrice ? String(suggestedPrice) : ''" />
        <p class="mt-1 text-[12px] text-ink-default">
          將使用：<span class="font-mono text-ink-strong">{{ fmtMoney(finalPrice) }}</span>
        </p>
        <p v-if="errors.price" class="mt-1 text-[12px] text-state-danger">{{ errors.price }}</p>
      </div>

      <!-- Note -->
      <div>
        <label class="block text-[13px] text-ink-strong mb-1.5">報價備註（會放進訊息流）</label>
        <Textarea v-model="note" :rows="3" :maxlength="1000" placeholder="可選：報價說明、製作期、備註..." />
      </div>

      <p class="text-[12px] text-ink-muted">
        送出後系統會：寄報價 email（含初稿預覽圖 + 確認連結）給客戶；狀態轉為「報價已寄出」；報價有效期 24 小時。
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">送出報價</Button>
    </template>
  </Dialog>
</template>
