<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Loader2, Eye, EyeOff } from 'lucide-vue-next'

import Button from '@/shared/ui/Button.vue'
import type { PaletteMapping } from '../api_mapping'

const props = defineProps<{
  /** filled_template 公開 URL（後端產出，無需 signed URL）*/
  imageUrl: string | null
  mappings: PaletteMapping[]
}>()

const emit = defineEmits<{
  /** 使用者點選 canvas 上的某個像素，吐回 template_id（用最近 algorithm RGB 反查）*/
  pickTemplate: [templateId: number]
}>()

// 兩種顯示模式：演算法原色 / 實體色預覽（替換 algo→physical）
const mode = ref<'algorithm' | 'physical'>('algorithm')
const loading = ref(false)
const rendering = ref(false)  // 切到 physical 模式時的計算中（首次 1~2 秒）
const error = ref<string | null>(null)

const canvasRef = ref<HTMLCanvasElement | null>(null)
let originalImageData: ImageData | null = null
let physicalImageData: ImageData | null = null  // 預算好的實體色版本，切換 O(1)

// mappings 的 LUT（key = `r,g,b`）— 直接命中時極快
const colorMap = computed(() => {
  const m = new Map<string, [number, number, number]>()
  for (const map of props.mappings) {
    if (!map.physical_color) continue
    const [r, g, b] = map.algorithm_rgb
    m.set(`${r},${g},${b}`, map.physical_color.rgb)
  }
  return m
})

/** 給定 (r,g,b) 找最接近的 algorithm_rgb 對應的實體色；找不到 mapping 回 null。
 * 用平方歐氏距離比較（夠用、不需 LAB 因為色塊本身已經是 quantized 後的近似色）。
 */
function _findNearestPhysical(
  r: number, g: number, b: number,
): [number, number, number] | null {
  let best: { rgb: [number, number, number]; dist: number } | null = null
  for (const map of props.mappings) {
    if (!map.physical_color) continue
    const [ar, ag, ab] = map.algorithm_rgb
    const dist = (r - ar) ** 2 + (g - ag) ** 2 + (b - ab) ** 2
    if (!best || dist < best.dist) {
      best = { rgb: map.physical_color.rgb, dist }
    }
  }
  return best?.rgb ?? null
}

async function loadImage() {
  if (!props.imageUrl || !canvasRef.value) return
  loading.value = true
  error.value = null
  try {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('圖片載入失敗（可能是 CORS）'))
      img.src = props.imageUrl!
    })
    const c = canvasRef.value
    // 限制最大 800px 寬避免太慢
    const maxW = 800
    const ratio = img.width > maxW ? maxW / img.width : 1
    c.width = Math.round(img.width * ratio)
    c.height = Math.round(img.height * ratio)
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.drawImage(img, 0, 0, c.width, c.height)
    originalImageData = ctx.getImageData(0, 0, c.width, c.height)
    _invalidatePhysicalCache()
    if (mode.value === 'physical') applyPhysical()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

/** 計算 physical-mode 的 ImageData 並快取。第一次切換時跑（800×1067 圖約 1~2 秒），
 *  後續切換 O(1) 直接用快取結果。mappings 改動時呼叫 _invalidatePhysicalCache 重算。 */
function _buildPhysicalImageData(): ImageData | null {
  if (!originalImageData) return null
  const data = new Uint8ClampedArray(originalImageData.data)
  const lut = colorMap.value
  const WHITE_KEY = '255,255,255'
  const memo = new Map<string, [number, number, number] | null>()
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    const key = `${r},${g},${b}`
    if (key === WHITE_KEY) continue
    let target = lut.get(key)
    if (!target) {
      let cached = memo.get(key)
      if (cached === undefined) {
        cached = _findNearestPhysical(r, g, b)
        memo.set(key, cached)
      }
      target = cached ?? undefined
    }
    if (target) {
      data[i] = target[0]
      data[i + 1] = target[1]
      data[i + 2] = target[2]
    }
  }
  return new ImageData(data, originalImageData.width, originalImageData.height)
}

function _invalidatePhysicalCache() {
  physicalImageData = null
}

async function applyPhysical() {
  if (!canvasRef.value || !originalImageData) return
  const ctx = canvasRef.value.getContext('2d')
  if (!ctx) return
  if (!physicalImageData) {
    rendering.value = true
    // 等下一 frame 讓 spinner 先 paint，再做重活
    await new Promise<void>((r) => requestAnimationFrame(() => r()))
    physicalImageData = _buildPhysicalImageData()
    rendering.value = false
  }
  if (physicalImageData) ctx.putImageData(physicalImageData, 0, 0)
}

function applyOriginal() {
  if (!canvasRef.value || !originalImageData) return
  const ctx = canvasRef.value.getContext('2d')
  if (!ctx) return
  ctx.putImageData(originalImageData, 0, 0)
}

watch(mode, (m) => {
  if (m === 'physical') applyPhysical()
  else applyOriginal()
})

watch(() => props.mappings, () => {
  // 對應改變 → physical cache 失效；若目前在實體色模式則重繪
  _invalidatePhysicalCache()
  if (mode.value === 'physical') applyPhysical()
}, { deep: true })

watch(() => props.imageUrl, () => {
  _invalidatePhysicalCache()
  loadImage()
}, { immediate: false })

onMounted(() => loadImage())

function onClick(e: MouseEvent) {
  if (!canvasRef.value || !originalImageData) return
  const rect = canvasRef.value.getBoundingClientRect()
  const scaleX = canvasRef.value.width / rect.width
  const scaleY = canvasRef.value.height / rect.height
  const x = Math.floor((e.clientX - rect.left) * scaleX)
  const y = Math.floor((e.clientY - rect.top) * scaleY)
  const idx = (y * originalImageData.width + x) * 4
  const r = originalImageData.data[idx]
  const g = originalImageData.data[idx + 1]
  const b = originalImageData.data[idx + 2]
  // 找最接近的 mapping（用平方距離，client-side 已夠快）
  let best: { id: number; dist: number } | null = null
  for (const m of props.mappings) {
    const [mr, mg, mb] = m.algorithm_rgb
    const dist = (r - mr) ** 2 + (g - mg) ** 2 + (b - mb) ** 2
    if (!best || dist < best.dist) best = { id: m.template_id, dist }
  }
  if (best) emit('pickTemplate', best.id)
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-[12px] text-ink-muted">點圖片可選色塊</p>
      <button
        type="button"
        class="text-[12px] inline-flex items-center gap-1 text-ink-muted hover:text-ink-strong transition-colors disabled:opacity-50 disabled:cursor-wait"
        :disabled="rendering"
        @click="mode = mode === 'algorithm' ? 'physical' : 'algorithm'"
      >
        <Loader2 v-if="rendering" :size="12" :stroke-width="1.5" class="animate-spin" />
        <Eye v-else-if="mode === 'algorithm'" :size="12" :stroke-width="1.5" />
        <EyeOff v-else :size="12" :stroke-width="1.5" />
        {{
          rendering
            ? '計算中…'
            : mode === 'algorithm' ? '切到實體色預覽' : '切回演算法原色'
        }}
      </button>
    </div>

    <div
      class="relative rounded-[var(--radius-sm)] border border-line-hairline bg-paper-canvas overflow-hidden"
      :class="loading ? 'min-h-[200px]' : ''"
    >
      <canvas
        ref="canvasRef"
        class="block max-w-full h-auto cursor-crosshair"
        @click="onClick"
      />

      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center bg-paper-canvas/80"
      >
        <Loader2 :size="20" :stroke-width="1.5" class="animate-spin text-ink-muted" />
      </div>

      <div
        v-else-if="error"
        class="p-4 text-[12px] text-state-danger text-center"
      >
        {{ error }}
        <p class="mt-1 text-[11px] text-ink-muted">
          （Firebase Storage CORS 已設定 admin localhost；若仍失敗請重新整理）
        </p>
      </div>

      <div
        v-else-if="!imageUrl"
        class="p-4 text-[12px] text-ink-muted text-center"
      >
        無 filled_template 圖片
      </div>
    </div>
  </div>
</template>
