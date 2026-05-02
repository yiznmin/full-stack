<script setup lang="ts">
/**
 * MaskCanvas — 圖片 + sam_points/polygons 標記 + mask overlay 渲染
 *
 * 規格：admin_production.md §1.3 + 04c_production_sam.md §C.2
 *
 * 互動：
 *   左鍵空白 → SAM 模式：前景點 (label=1, 綠) / 多邊形模式：currentPolygon 加頂點
 *   右鍵空白 → SAM 模式：背景點 (label=0, 紅) / 多邊形模式：≥3 點則閉合
 *   右鍵 marker → 刪除該 marker（不論模式）
 *   滾輪 → 縮放（向游標靠攏）
 *   空白鍵 + 拖移 / 中鍵拖移 → 平移
 *
 * 顯示：
 *   1. 原圖（bottom layer）
 *   2. mask overlay（半透明綠色，CSS mask-image 蓋在純色 div 上 — 可被 hideMask prop 隱藏）
 *   3. SVG marker layer（viewBox = natural pixels；marker 尺寸用 1/zoom 反向縮放保持視覺一致）
 *
 * 座標系：所有 sam_points / polygons 對外都是 image-natural 座標。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'

import type { SamPoint } from '../api'
import type { MaskTool } from './MaskToolbar.vue'

const props = defineProps<{
  imageUrl: string
  imageWidth: number                            // natural width (px)
  imageHeight: number                           // natural height (px)
  tool: MaskTool
  samPoints: SamPoint[]
  polygons: number[][][]
  currentPolygon: number[][]
  maskUrl: string | null
  isLocked: boolean
  hideMask?: boolean
  inflight?: boolean
}>()

const emit = defineEmits<{
  'add-sam-point': [point: SamPoint]
  'add-polygon-vertex': [point: [number, number]]
  'close-polygon': []
  'delete-sam-point': [index: number]
  'delete-polygon': [index: number]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const innerRef = ref<HTMLDivElement | null>(null)

// ── Zoom & Pan ─────────────────────────────────────────────────────────
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const isPanning = ref(false)
const isSpaceDown = ref(false)
let panStart: { mx: number; my: number; px: number; py: number } | null = null
let didPan = false

const transformStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

function clampZoom(z: number) {
  return Math.max(0.25, Math.min(8, z))
}

function resetView() {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
}

function zoomTowardPoint(localX: number, localY: number, factor: number) {
  const newZoom = clampZoom(zoom.value * factor)
  if (newZoom === zoom.value) return
  // 維持 (localX, localY) 對應的 world 點不動
  const worldX = (localX - panX.value) / zoom.value
  const worldY = (localY - panY.value) / zoom.value
  panX.value = localX - worldX * newZoom
  panY.value = localY - worldY * newZoom
  zoom.value = newZoom
}

function zoomAtCenter(factor: number) {
  const rect = containerRef.value?.getBoundingClientRect()
  if (!rect) return
  zoomTowardPoint(rect.width / 2, rect.height / 2, factor)
}

function zoomIn() { zoomAtCenter(1.25) }
function zoomOut() { zoomAtCenter(1 / 1.25) }

defineExpose({ resetView, zoomIn, zoomOut })

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const rect = containerRef.value?.getBoundingClientRect()
  if (!rect) return
  const localX = e.clientX - rect.left
  const localY = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
  zoomTowardPoint(localX, localY, factor)
}

// ── Pan ────────────────────────────────────────────────────────────────
function startPan(e: MouseEvent) {
  isPanning.value = true
  didPan = false
  panStart = { mx: e.clientX, my: e.clientY, px: panX.value, py: panY.value }
  e.preventDefault()
  e.stopPropagation()
}

function onMouseMoveWindow(e: MouseEvent) {
  if (!isPanning.value || !panStart) return
  const dx = e.clientX - panStart.mx
  const dy = e.clientY - panStart.my
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didPan = true
  panX.value = panStart.px + dx
  panY.value = panStart.py + dy
}

function onMouseUpWindow() {
  if (!isPanning.value) return
  isPanning.value = false
  panStart = null
}

function onMouseDown(e: MouseEvent) {
  // 中鍵 OR 空白鍵 + 左鍵 → 平移
  if (e.button === 1 || (e.button === 0 && isSpaceDown.value)) {
    startPan(e)
  }
}

// ── Keyboard：空白鍵（pan modifier；其他快捷鍵在父層處理）──────────────
function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'Space' && !isInputFocused()) {
    isSpaceDown.value = true
    e.preventDefault()
  }
}
function onKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') {
    isSpaceDown.value = false
  }
}
function isInputFocused() {
  const el = document.activeElement as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

// ── Coord conversion (post-transform via getBoundingClientRect) ───────
function eventToNatural(e: MouseEvent): [number, number] {
  // innerRef 已套 transform；rect 反映實際螢幕呈現
  const rect = innerRef.value?.getBoundingClientRect()
  if (!rect || rect.width === 0 || rect.height === 0) return [-1, -1]
  const dx = e.clientX - rect.left
  const dy = e.clientY - rect.top
  const naturalX = Math.round((dx / rect.width) * props.imageWidth)
  const naturalY = Math.round((dy / rect.height) * props.imageHeight)
  return [naturalX, naturalY]
}

function inBounds(x: number, y: number) {
  return x >= 0 && y >= 0 && x < props.imageWidth && y < props.imageHeight
}

// ── Click handlers（容器層級）─────────────────────────────────────────
function onClickArea(e: MouseEvent) {
  if (didPan) { didPan = false; return }
  if (props.isLocked) return
  const [x, y] = eventToNatural(e)
  if (!inBounds(x, y)) return
  if (props.tool === 'sam') {
    emit('add-sam-point', { x, y, label: 1 })
  } else {
    emit('add-polygon-vertex', [x, y])
  }
}

function onContextArea(e: MouseEvent) {
  e.preventDefault()
  if (props.isLocked) return
  const [x, y] = eventToNatural(e)
  if (!inBounds(x, y)) return
  if (props.tool === 'sam') {
    emit('add-sam-point', { x, y, label: 0 })
  } else {
    if (props.currentPolygon.length >= 3) emit('close-polygon')
  }
}

// 右鍵 marker → 刪除（@contextmenu.stop.prevent → 不會冒泡到 onContextArea）
function deleteSamAt(idx: number) {
  if (props.isLocked) return
  emit('delete-sam-point', idx)
}
function deletePolyAt(idx: number) {
  if (props.isLocked) return
  emit('delete-polygon', idx)
}

// ── Lifecycle ──────────────────────────────────────────────────────────
onMounted(() => {
  window.addEventListener('mousemove', onMouseMoveWindow)
  window.addEventListener('mouseup', onMouseUpWindow)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})
onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMoveWindow)
  window.removeEventListener('mouseup', onMouseUpWindow)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
})

// 換圖時 reset view
watch(() => props.imageUrl, () => resetView())

const cursorClass = computed(() => {
  if (props.isLocked) return 'cursor-not-allowed'
  if (isPanning.value) return 'cursor-grabbing'
  if (isSpaceDown.value) return 'cursor-grab'
  return props.tool === 'sam' ? 'cursor-crosshair' : 'cursor-copy'
})

// 反向縮放 — 讓 marker 在不同 zoom 下視覺尺寸一致
const inv = computed(() => 1 / zoom.value)
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full overflow-hidden bg-paper-subtle rounded-[var(--radius-xs)] select-none"
    :style="{ aspectRatio: `${imageWidth} / ${imageHeight}` }"
    :class="cursorClass"
    @wheel="onWheel"
    @mousedown="onMouseDown"
    @click="onClickArea"
    @contextmenu="onContextArea"
  >
    <!-- 縮放/平移 wrapper（裝原圖 + mask + svg）-->
    <div
      ref="innerRef"
      class="absolute inset-0"
      :style="transformStyle"
    >
      <img
        :src="imageUrl"
        class="block w-full h-full pointer-events-none"
        alt="待標記圖"
        draggable="false"
      />

      <!-- mask overlay：CSS mask-image 限制純色到 mask 白色區 -->
      <div
        v-if="maskUrl && !hideMask"
        class="absolute inset-0 pointer-events-none"
        :style="{
          backgroundColor: 'rgb(34, 197, 94)',
          opacity: 0.45,
          WebkitMaskImage: `url('${maskUrl}')`,
          maskImage: `url('${maskUrl}')`,
          WebkitMaskSize: '100% 100%',
          maskSize: '100% 100%',
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
        }"
        aria-label="mask overlay"
      />

      <!-- Marker SVG（viewBox = natural pixels；marker 尺寸用 inv 反向縮放）-->
      <svg
        class="absolute inset-0 w-full h-full pointer-events-none"
        :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
        preserveAspectRatio="none"
      >
        <!-- 已閉合多邊形（藍）— 右鍵刪除 -->
        <polygon
          v-for="(poly, i) in polygons"
          :key="`p-${i}`"
          :points="poly.map((pt) => `${pt[0]},${pt[1]}`).join(' ')"
          fill="rgba(56, 189, 248, 0.18)"
          stroke="#0284c7"
          :stroke-width="2 * inv"
          style="pointer-events: auto; cursor: context-menu"
          @click.stop
          @contextmenu.stop.prevent="deletePolyAt(i)"
        />

        <!-- 進行中多邊形（虛線）-->
        <polyline
          v-if="currentPolygon.length > 0"
          :points="currentPolygon.map((pt) => `${pt[0]},${pt[1]}`).join(' ')"
          fill="none"
          stroke="#0284c7"
          :stroke-width="2 * inv"
          :stroke-dasharray="`${6 * inv},${4 * inv}`"
        />
        <circle
          v-for="(pt, i) in currentPolygon"
          :key="`cp-${i}`"
          :cx="pt[0]"
          :cy="pt[1]"
          :r="4 * inv"
          fill="#0284c7"
        />

        <!-- SAM 點 — 右鍵刪除 -->
        <circle
          v-for="(p, i) in samPoints"
          :key="`s-${i}`"
          :cx="p.x"
          :cy="p.y"
          :r="7 * inv"
          :fill="p.label === 1 ? '#22c55e' : '#ef4444'"
          stroke="white"
          :stroke-width="2 * inv"
          style="pointer-events: auto; cursor: context-menu"
          @click.stop
          @contextmenu.stop.prevent="deleteSamAt(i)"
        />
      </svg>
    </div>

    <!-- 浮層：右上 — zoom % 與後端推論狀態 -->
    <div class="absolute top-2 right-2 flex items-center gap-2 z-10 pointer-events-none">
      <div
        v-if="inflight"
        class="px-2 py-1 rounded-[var(--radius-xs)] bg-paper-surface/95 border border-line-strong text-[11px] text-accent flex items-center gap-1.5 shadow-sm"
      >
        <Loader2 :size="11" :stroke-width="1.5" class="animate-spin" />
        後端推論中
      </div>
      <div
        class="px-2 py-1 rounded-[var(--radius-xs)] bg-paper-surface/95 border border-line-strong text-[11px] text-ink-muted shadow-sm tabular-nums"
      >
        {{ Math.round(zoom * 100) }}%
      </div>
    </div>

    <!-- 浮層：左下 — 操作提示 -->
    <div
      v-if="!isLocked"
      class="absolute bottom-2 left-2 px-2 py-1 rounded-[var(--radius-xs)] bg-paper-surface/85 border border-line-hairline text-[11px] text-ink-muted shadow-sm pointer-events-none"
    >
      滾輪縮放 · 空白鍵+拖移 · 右鍵 marker = 刪除
    </div>
  </div>
</template>
