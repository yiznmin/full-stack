<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'
import { Loader2, AlertTriangle, Crosshair, Plus, X } from 'lucide-vue-next'

import type { BatchOperation, PaletteColor } from '../api'

type OperationType = 'merge_color' | 'eliminate_border'

const props = defineProps<{
  open: boolean
  type: OperationType | null
  palette: PaletteColor[]
  /** template.svg 的 signed URL；點選格子用 */
  svgUrl?: string | null
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  /** 全部 ops 一起送出（batch 端點） */
  confirmBatch: [payload: BatchOperation[]]
}>()

// ── 狀態 ────────────────────────────────────────────────────────────────────
// A: 點 1 格 → 從調色盤選 target_template_id
// B: 點 2 格 → 對話框問存活
const polygon1 = ref<string>('')  // 第一格 polygon_id
const polygon2 = ref<string>('')  // 第二格（B only）
const targetTemplateId = ref<string>('')  // 目標色（A only）
const survivor = ref<'p1' | 'p2' | ''>('')  // B 的存活側選擇
const errors = ref<Record<string, string>>({})
const queue = ref<BatchOperation[]>([])  // 累積的批次動作

const svgContainerRef = ref<HTMLDivElement | null>(null)
const svgLoading = ref(false)
const svgError = ref<string | null>(null)
const zoom = ref(1) // 1 = 容器寬度；> 1 = 放大；範圍 0.5 ~ 5
let cleanupClickHandler: (() => void) | null = null

watch(
  [() => props.open, () => props.type],
  () => {
    if (props.open) {
      polygon1.value = ''
      polygon2.value = ''
      targetTemplateId.value = ''
      survivor.value = ''
      errors.value = {}
      svgError.value = null
      zoom.value = 1
      queue.value = []
    }
  },
)

// ── 載入 SVG 並 inline 到 DOM；attach click handler 到所有 polygon ────────────

watch(
  [() => props.open, () => props.svgUrl],
  async () => {
    if (!props.open || !props.svgUrl) return
    svgLoading.value = true
    svgError.value = null
    try {
      // 等下個 tick 確保 dialog 容器已渲染
      await new Promise((r) => setTimeout(r, 50))
      const container = svgContainerRef.value
      if (!container) return
      const res = await fetch(props.svgUrl)
      if (!res.ok) throw new Error(`SVG 載入失敗：HTTP ${res.status}`)
      const svgText = await res.text()
      container.innerHTML = svgText

      // 強制 SVG 自適應容器寬度（zoom 透過 width % 放大）
      const svgEl = container.querySelector('svg')
      if (svgEl) {
        svgEl.setAttribute('width', `${zoom.value * 100}%`)
        svgEl.removeAttribute('height')
      }

      // 移除舊 click handler（若有）
      if (cleanupClickHandler) cleanupClickHandler()

      // 對所有 polygon attach click：把 id="rN" 的 polygon 點擊事件 bubble 到容器
      const polygons = container.querySelectorAll('polygon[id]')
      polygons.forEach((poly) => {
        const el = poly as SVGPolygonElement
        el.style.cursor = 'pointer'
        el.style.transition = 'opacity 0.15s'
      })

      const handler = (ev: Event) => {
        const target = ev.target as Element
        if (target.tagName.toLowerCase() === 'polygon' && target.id.startsWith('r')) {
          onPolygonClick(target.id)
        }
      }
      container.addEventListener('click', handler)
      cleanupClickHandler = () => container.removeEventListener('click', handler)
    } catch (e) {
      svgError.value = (e as Error).message
    } finally {
      svgLoading.value = false
    }
  },
)

// 監聽 zoom 變化 → 直接改 SVG 的 width 百分比；overflow:auto 容器自動處理捲軸
watch(zoom, (z) => {
  const container = svgContainerRef.value
  if (!container) return
  const svgEl = container.querySelector('svg')
  if (svgEl) svgEl.setAttribute('width', `${z * 100}%`)
})

function zoomIn() {
  zoom.value = Math.min(5, +(zoom.value + 0.5).toFixed(2))
}
function zoomOut() {
  zoom.value = Math.max(0.5, +(zoom.value - 0.5).toFixed(2))
}
function zoomReset() {
  zoom.value = 1
}

// Ctrl+滾輪放大縮小（在 SVG 容器內）
function onWheel(e: WheelEvent) {
  if (!e.ctrlKey) return
  e.preventDefault()
  if (e.deltaY < 0) zoomIn()
  else zoomOut()
}

function onPolygonClick(polygonId: string) {
  if (!props.type) return
  if (props.type === 'merge_color') {
    polygon1.value = polygonId
    highlightPolygons([polygonId])
  } else {
    // eliminate_border：依序填 p1/p2，第三次 click 重置
    if (!polygon1.value) {
      polygon1.value = polygonId
    } else if (!polygon2.value && polygonId !== polygon1.value) {
      polygon2.value = polygonId
    } else {
      // 兩格已滿，或重點同一格 → 重置成新的第一格
      polygon1.value = polygonId
      polygon2.value = ''
      survivor.value = ''
    }
    highlightPolygons([polygon1.value, polygon2.value].filter(Boolean))
  }
  errors.value = {}
}

function highlightPolygons(ids: string[]) {
  const container = svgContainerRef.value
  if (!container) return
  const polys = container.querySelectorAll('polygon[id]')
  polys.forEach((p) => {
    const el = p as SVGPolygonElement
    if (ids.includes(el.id)) {
      el.style.stroke = '#FF6600'
      el.style.strokeWidth = '4'
      el.style.opacity = '1'
    } else {
      el.style.stroke = '#AAAAAA'
      el.style.strokeWidth = '1'
      el.style.opacity = ids.length ? '0.6' : '1'
    }
  })
}

// ── 顯示文字 ─────────────────────────────────────────────────────────────────

const titles: Record<OperationType, string> = {
  merge_color: '合併色塊',
  eliminate_border: '消除邊界線',
}
const hint = computed(() => {
  if (props.type === 'merge_color') {
    return '點選 template 上的某一格 → 從下方下拉選目標色 → 該格的像素會改成目標色。'
  }
  if (props.type === 'eliminate_border') {
    return '依序點選兩個相鄰格子 → 對話框選哪個顏色保留 → 兩格融合成一格。'
  }
  return ''
})
const warn = '會把 approved 退回 false（需重新審核）。'

const paletteOptions = computed(() => [
  { value: '', label: '— 請選 —' },
  ...props.palette.map((c) => ({
    value: String(c.template_id),
    label: `#${c.template_id} ${c.hex}`,
  })),
])

const survivorOptions = computed(() => {
  if (!polygon1.value || !polygon2.value) return []
  return [
    { value: 'p1', label: `保留 ${polygon1.value}` },
    { value: 'p2', label: `保留 ${polygon2.value}` },
  ]
})

// ── 驗證 + 送出 ──────────────────────────────────────────────────────────────

function validate(): boolean {
  const errs: Record<string, string> = {}
  if (props.type === 'merge_color') {
    if (!polygon1.value) errs.polygon = '請點選一個格子'
    if (!targetTemplateId.value) errs.target = '請選目標色'
  } else if (props.type === 'eliminate_border') {
    if (!polygon1.value) errs.polygon = '請點選兩個格子（先點第一個）'
    else if (!polygon2.value) errs.polygon = '請再點選一個相鄰的格子'
    if (polygon1.value && polygon2.value && !survivor.value) {
      errs.survivor = '請選保留哪個顏色'
    }
  }
  errors.value = errs
  return Object.keys(errs).length === 0
}

/** 判斷顏色明暗 — 給色票上的數字選黑或白文字 */
function _isLightColor(hex: string): boolean {
  const m = hex.match(/^#([0-9a-f]{6})$/i)
  if (!m) return true
  const n = parseInt(m[1], 16)
  const r = (n >> 16) & 0xff
  const g = (n >> 8) & 0xff
  const b = n & 0xff
  // YIQ 亮度公式
  return (r * 299 + g * 587 + b * 114) / 1000 > 155
}

function addToQueue() {
  if (!validate() || !props.type) return
  if (props.type === 'merge_color') {
    queue.value.push({
      op: 'merge_color',
      polygon_id: polygon1.value,
      target_template_id: Number(targetTemplateId.value),
    })
  } else if (props.type === 'eliminate_border') {
    const absorbed = survivor.value === 'p1' ? polygon2.value : polygon1.value
    const surviving = survivor.value === 'p1' ? polygon1.value : polygon2.value
    queue.value.push({
      op: 'eliminate_border',
      absorbed_polygon_id: absorbed,
      surviving_polygon_id: surviving,
    })
  }
  // 清空當前選擇，方便下一個動作
  polygon1.value = ''
  polygon2.value = ''
  targetTemplateId.value = ''
  survivor.value = ''
  errors.value = {}
  highlightPolygons([])
}

function removeFromQueue(idx: number) {
  queue.value.splice(idx, 1)
}

function submitBatch() {
  if (queue.value.length === 0) return
  emit('confirmBatch', [...queue.value])
}

/** 給已加入佇列的 op 顯示一行人類可讀描述。 */
function describeOp(op: BatchOperation): string {
  if (op.op === 'merge_color') {
    const c = props.palette.find((p) => p.template_id === op.target_template_id)
    return `合併 ${op.polygon_id} → #${op.target_template_id} ${c?.hex ?? ''}`
  }
  return `消邊界 ${op.absorbed_polygon_id} → ${op.surviving_polygon_id}`
}
</script>

<template>
  <Dialog
    :open="open"
    :title="type ? titles[type] : ''"
    size="lg"
    @close="emit('close')"
  >
    <div v-if="type" class="space-y-4 text-[13px]">
      <p class="text-ink-default">{{ hint }}</p>
      <p class="text-[12px] text-state-warning flex items-start gap-1">
        <AlertTriangle :size="12" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span>{{ warn }}</span>
      </p>

      <!-- SVG 預覽（template.svg inline，可點 polygon） -->
      <div v-if="svgUrl">
        <div class="flex items-center justify-between text-[12px] text-ink-muted mb-1">
          <div class="flex items-center gap-1">
            <Crosshair :size="12" :stroke-width="1.5" />
            <span>點選 template 上的格子</span>
          </div>
          <div class="flex items-center gap-1">
            <button
              type="button"
              class="px-2 py-0.5 rounded border border-line-hairline hover:bg-surface-muted text-ink-default"
              title="縮小"
              @click="zoomOut"
            >
              −
            </button>
            <span class="px-1 font-mono tabular-nums w-12 text-center">{{ Math.round(zoom * 100) }}%</span>
            <button
              type="button"
              class="px-2 py-0.5 rounded border border-line-hairline hover:bg-surface-muted text-ink-default"
              title="放大"
              @click="zoomIn"
            >
              +
            </button>
            <button
              type="button"
              class="ml-1 px-2 py-0.5 rounded border border-line-hairline hover:bg-surface-muted text-ink-default text-[11px]"
              title="重設"
              @click="zoomReset"
            >
              重設
            </button>
          </div>
        </div>
        <div
          class="rounded-[var(--radius-sm)] border border-line-hairline bg-paper-canvas overflow-auto relative"
          style="min-height: 300px; max-height: 600px"
          @wheel="onWheel"
        >
          <div ref="svgContainerRef" class="block" />
          <div
            v-if="svgLoading"
            class="absolute inset-0 flex items-center justify-center bg-paper-canvas/80"
          >
            <Loader2 :size="20" :stroke-width="1.5" class="animate-spin text-ink-muted" />
          </div>
          <p v-if="svgError" class="p-2 text-[11px] text-state-danger">{{ svgError }}</p>
        </div>
        <p class="mt-0.5 text-[11px] text-ink-muted">提示：按 Ctrl + 滑鼠滾輪也可縮放</p>
      </div>

      <!-- 已選格子 -->
      <div class="text-[12px] space-y-1">
        <div class="flex gap-2">
          <Label>已點選：</Label>
          <span v-if="polygon1" class="font-mono px-1.5 rounded bg-accent/10 text-accent">
            {{ polygon1 }}
          </span>
          <span v-if="polygon2" class="font-mono px-1.5 rounded bg-accent/10 text-accent">
            {{ polygon2 }}
          </span>
          <span v-if="!polygon1" class="text-ink-muted">尚未點選</span>
        </div>
        <p v-if="errors.polygon" class="text-state-danger">{{ errors.polygon }}</p>
      </div>

      <!-- A: 目標色色票網格 -->
      <div v-if="type === 'merge_color'">
        <Label>目標色號</Label>
        <div class="mt-1 grid grid-cols-6 sm:grid-cols-9 gap-1.5">
          <button
            v-for="c in palette"
            :key="c.template_id"
            type="button"
            class="relative aspect-square rounded-[var(--radius-xs)] border-2 transition-all hover:scale-105 focus:outline-none focus:ring-2 focus:ring-accent"
            :class="
              Number(targetTemplateId) === c.template_id
                ? 'border-accent ring-2 ring-accent/30'
                : 'border-line-hairline'
            "
            :style="{ backgroundColor: c.hex }"
            :title="`#${c.template_id} ${c.hex}`"
            @click="targetTemplateId = String(c.template_id)"
          >
            <span
              class="absolute inset-0 flex items-center justify-center text-[11px] font-mono font-medium"
              :style="{ color: _isLightColor(c.hex) ? '#000' : '#fff' }"
            >
              {{ c.template_id }}
            </span>
          </button>
        </div>
        <p v-if="errors.target" class="mt-1 text-[12px] text-state-danger">{{ errors.target }}</p>
      </div>

      <!-- B: 存活選擇 -->
      <div v-if="type === 'eliminate_border' && polygon1 && polygon2">
        <Label>保留哪個顏色？</Label>
        <Select v-model="survivor" :options="survivorOptions" />
        <p v-if="errors.survivor" class="mt-1 text-[12px] text-state-danger">{{ errors.survivor }}</p>
      </div>

      <!-- 加入佇列 -->
      <div class="flex justify-end">
        <Button variant="secondary" :disabled="pending" @click="addToQueue">
          <Plus :size="14" :stroke-width="1.5" />
          加入佇列
        </Button>
      </div>

      <!-- 佇列 -->
      <div v-if="queue.length > 0" class="border-t border-line-hairline pt-3">
        <Label>動作佇列（{{ queue.length }} 個）</Label>
        <ul class="mt-1 space-y-1">
          <li
            v-for="(op, idx) in queue"
            :key="idx"
            class="flex items-center justify-between gap-2 px-2 py-1 rounded bg-surface-muted text-[12px]"
          >
            <span class="font-mono truncate">{{ idx + 1 }}. {{ describeOp(op) }}</span>
            <button
              type="button"
              class="text-ink-muted hover:text-state-danger"
              :disabled="pending"
              @click="removeFromQueue(idx)"
            >
              <X :size="14" :stroke-width="1.5" />
            </button>
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button
        variant="primary"
        :disabled="pending || queue.length === 0"
        @click="submitBatch"
      >
        <Loader2 v-if="pending" :size="14" :stroke-width="1.5" class="animate-spin" />
        全部執行（{{ queue.length }}）
      </Button>
    </template>
  </Dialog>
</template>
