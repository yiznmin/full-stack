<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Textarea from '@/shared/ui/Textarea.vue'
import Select from '@/shared/ui/Select.vue'
import { Loader2, Eye, ChevronLeft, ImageOff, AlertTriangle } from 'lucide-vue-next'

import {
  useCustomPhotoPricesQuery,
  useCustomPhotoSurchargesQuery,
} from '../queries'
import type { CustomRequestDetail, Detail, Difficulty, QuotePayload } from '../api'

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
// 試算用 — 客戶若選「讓管理員建議」(canvas/difficulty=null)，admin 在這裡敲定試算規格。
// 不會寫回 custom_request；只供 basePrice 對 prices 表 lookup。
const priceCanvasW = ref<number | null>(null)
const priceCanvasH = ref<number | null>(null)
const priceDifficulty = ref<Difficulty>('intermediate')
const surchargeIds = ref<Set<string>>(new Set())
const overrideStr = ref('')
const note = ref('')
const errors = ref<Record<string, string>>({})

// 兩步驟：1=填寫報價、2=預覽客戶會看到的內容（確認後才真的送出）
const step = ref<1 | 2>(1)
const previewImageError = ref(false)
const previewImageLoading = ref(false)

const { data: prices, isLoading: pricesLoading } = useCustomPhotoPricesQuery()
const { data: surcharges, isLoading: surLoading } = useCustomPhotoSurchargesQuery()

// 從 prices 表推所有可選的 canvas 尺寸（去重）
const availableCanvasSizes = computed(() => {
  if (!prices.value) return [] as Array<{ w: number; h: number; label: string }>
  const seen = new Set<string>()
  const out: Array<{ w: number; h: number; label: string }> = []
  for (const p of prices.value.items) {
    const key = `${p.canvas_w}x${p.canvas_h}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ w: p.canvas_w, h: p.canvas_h, label: `${p.canvas_w} × ${p.canvas_h} cm` })
  }
  return out.sort((a, b) => a.w * a.h - b.w * b.h)
})
const canvasSizeOptions = computed(() =>
  availableCanvasSizes.value.map((s) => ({ value: `${s.w}x${s.h}`, label: s.label })),
)
const priceCanvasKey = computed({
  get: () => (priceCanvasW.value && priceCanvasH.value
    ? `${priceCanvasW.value}x${priceCanvasH.value}` : ''),
  set: (v: string) => {
    const [w, h] = v.split('x').map(Number)
    priceCanvasW.value = w || null
    priceCanvasH.value = h || null
  },
})

const difficultyOptions: Array<{ value: Difficulty; label: string }> = [
  { value: 'beginner', label: '入門 beginner' },
  { value: 'elementary', label: '初級 elementary' },
  { value: 'intermediate', label: '中級 intermediate' },
  { value: 'advanced', label: '進階 advanced' },
]

watch(
  () => props.open,
  (v) => {
    if (v) {
      detail.value = (props.request.detail as Detail) || 'standard'
      // 預設帶客戶填的；客戶 null 則用合理 default
      priceCanvasW.value = props.request.canvas_w_cm ?? 30
      priceCanvasH.value = props.request.canvas_h_cm ?? 40
      priceDifficulty.value = (props.request.difficulty as Difficulty) ?? 'intermediate'
      surchargeIds.value = new Set()
      overrideStr.value = ''
      note.value = ''
      errors.value = {}
      step.value = 1
      previewImageError.value = false
    }
  },
)

const PRICE_MULTIPLIER = 2.0

const basePrice = computed(() => {
  if (!prices.value || !priceCanvasW.value || !priceCanvasH.value) return null
  const match = prices.value.items.find(
    (p) =>
      p.canvas_w === priceCanvasW.value &&
      p.canvas_h === priceCanvasH.value &&
      p.difficulty === priceDifficulty.value,
  )
  return match ? Number(match.price) : null
})

const customerSpecsHint = computed(() => {
  const r = props.request
  const cv = r.canvas_w_cm ? `${r.canvas_w_cm}×${r.canvas_h_cm}cm` : '讓我們建議'
  const df = r.difficulty || '讓我們建議'
  return `客戶填：畫布 ${cv}、難易度 ${df}`
})

const usingCustomerSpec = computed(() => {
  const r = props.request
  return (
    r.canvas_w_cm === priceCanvasW.value
    && r.canvas_h_cm === priceCanvasH.value
    && r.difficulty === priceDifficulty.value
  )
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

function goPreview() {
  if (!validate()) return
  step.value = 2
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

// admin preview 端點：渲染客戶會看到的浮水印圖（不消耗 view_count）
const previewImageSrc = computed(
  () => `/api/v1/admin/custom-requests/${props.request.id}/preview-watermark`,
)
</script>

<template>
  <Dialog :open="open" :title="step === 1 ? '送出報價' : '確認客戶會看到的內容'" size="lg" @close="emit('close')">
    <div v-if="pricesLoading || surLoading" class="py-12 flex justify-center text-ink-muted">
      <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    </div>

    <!-- Step 1: 報價設定 -->
    <div v-else-if="step === 1" class="space-y-5 text-[13px]">
      <!-- Spec preview -->
      <div class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <p class="text-ink-strong font-medium">客戶申請內容</p>
        <p class="text-ink-muted text-[12px] mt-1">{{ customerSpecsHint }}</p>
      </div>

      <!-- 試算規格 — admin 敲定報價基準 -->
      <div class="p-3 border border-aux-rice-mid/40 bg-aux-rice-mid/[0.06] rounded-[var(--radius-xs)] space-y-3">
        <p class="text-[12px] text-ink-default">
          報價試算規格
          <span v-if="usingCustomerSpec" class="text-ink-muted">（沿用客戶填的）</span>
          <span v-else class="text-state-warning">（你已調整 — 請確認最終要報的尺寸／難度）</span>
        </p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[12px] text-ink-muted mb-1">畫布尺寸</label>
            <Select v-model="priceCanvasKey" :options="canvasSizeOptions" />
          </div>
          <div>
            <label class="block text-[12px] text-ink-muted mb-1">難易度</label>
            <Select v-model="priceDifficulty" :options="difficultyOptions" />
          </div>
        </div>
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
          <div class="flex justify-between">
            <dt>基礎價（{{ priceCanvasW }}×{{ priceCanvasH }} · {{ priceDifficulty }}）</dt>
            <dd class="font-mono">{{ fmtMoney(basePrice) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt>加費小計</dt>
            <dd class="font-mono">{{ fmtMoney(surchargeTotal) }}</dd>
          </div>
          <div class="flex justify-between pt-1.5 border-t border-line-hairline mt-1.5">
            <dt class="text-ink-strong">建議報價</dt>
            <dd class="font-mono text-ink-strong">{{ fmtMoney(suggestedPrice) }}</dd>
          </div>
        </dl>
        <p v-if="basePrice == null" class="mt-2 text-[11px] text-state-warning">
          ⚠ 找不到對應價格表 — 請確認 prices 表已 seed 此 (尺寸 × 難度) 組合
        </p>
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
        送出後系統會：寄純文字 email + 連結（不附圖）；客戶在連結頁看浮水印降解析度預覽圖；報價有效 24 小時、最多查看 10 次。
      </p>
    </div>

    <!-- Step 2: 預覽客戶看到的內容 -->
    <div v-else class="space-y-4 text-[13px]">
      <div class="p-3 border border-aux-rice-mid/40 bg-aux-rice-mid/[0.06] rounded-[var(--radius-xs)] flex items-start gap-2">
        <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0 text-aux-rice-deep" />
        <div class="flex-1 text-[12px] leading-relaxed">
          以下是<strong class="text-ink-strong">客戶會看到的完整內容</strong>，請確認預覽圖品質、報價金額、備註無誤後再送出。
          送出後狀態變「報價已寄出」、客戶會收到 email。
        </div>
      </div>

      <!-- 客戶看到的浮水印預覽 -->
      <div>
        <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-1.5">
          客戶看到的預覽圖（800px 寬 + 浮水印追溯印）
        </p>
        <div
          class="rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-canvas"
          :class="previewImageError ? 'p-6 text-center' : ''"
        >
          <div v-if="previewImageError" class="text-ink-muted">
            <ImageOff :size="32" :stroke-width="1.25" class="mx-auto mb-2" />
            <p class="text-[12px]">尚未有可預覽的製作圖</p>
            <p class="text-[11px] mt-1">請先「前往製作」跑出 production_job 並 approve，才能用浮水印預覽。</p>
          </div>
          <img
            v-else
            :src="previewImageSrc"
            alt="客戶看到的預覽圖"
            class="w-full h-auto"
            @error="previewImageError = true"
            @load="previewImageError = false"
          />
        </div>
      </div>

      <!-- 客戶看到的 email 內容 -->
      <div>
        <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-1.5">客戶會收到的 email</p>
        <div class="p-4 border border-line-hairline rounded-[var(--radius-sm)] bg-paper-surface text-[13px] leading-relaxed">
          <p class="text-ink-muted text-[11px] mb-3 pb-3 border-b border-line-hairline">
            主旨：【YIIMUI】客製報價已送出
          </p>
          <p class="mb-2">您的客製申請 #{{ request.id.slice(0, 8) }} 已完成報價。</p>
          <p class="mb-2"><strong>報價金額：{{ fmtMoney(finalPrice) }}</strong></p>
          <p v-if="note.trim()" class="mb-2">備註：{{ note.trim() }}</p>
          <p class="mb-2">請於 24 小時內確認：<span class="text-accent underline">查看報價</span></p>
        </div>
      </div>

      <!-- 客戶看到的報價摘要 -->
      <div class="p-4 border border-line-hairline rounded-[var(--radius-sm)] bg-paper-surface">
        <p class="text-[11px] text-ink-muted tracking-[0.04em] uppercase mb-2">客戶在 viewer 頁看到</p>
        <dl class="text-[13px] space-y-1.5">
          <div class="flex justify-between">
            <dt class="text-ink-muted">報價金額</dt>
            <dd class="font-display text-ink-strong text-[18px]">{{ fmtMoney(finalPrice) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-muted">畫布尺寸</dt>
            <dd>{{ priceCanvasW }}×{{ priceCanvasH }}cm</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-muted">難易度</dt>
            <dd>{{ priceDifficulty }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-muted">細緻度</dt>
            <dd>{{ detail }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-muted">查看限制</dt>
            <dd class="text-state-warning">10 次內必須決定 / 24 小時有效</dd>
          </div>
        </dl>
      </div>

      <p class="text-[11px] text-ink-muted">
        浮水印追溯印格式：<code class="font-mono bg-paper-subtle px-1">YIIMUI PREVIEW #{客戶 email 縮寫}-{申請 id 前 8 碼}</code>
        — 流到競品時可從浮水印反推來源。
      </p>
    </div>

    <template #footer>
      <template v-if="step === 1">
        <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
        <Button variant="primary" :disabled="pending" @click="goPreview">
          <Eye :size="14" :stroke-width="1.5" />
          預覽客戶會看到的內容
        </Button>
      </template>
      <template v-else>
        <Button variant="secondary" :disabled="pending" @click="step = 1">
          <ChevronLeft :size="14" :stroke-width="1.5" />
          回上一步修改
        </Button>
        <Button variant="primary" :disabled="pending" @click="submit">
          <Loader2 v-if="pending" :size="14" :stroke-width="1.5" class="animate-spin" />
          確認無誤、送出報價
        </Button>
      </template>
    </template>
  </Dialog>
</template>
