<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  MousePointer2,
  Pentagon,
  Undo2,
  Trash2,
  Check,
  ZoomIn,
  ZoomOut,
  Maximize,
  Eye,
  EyeOff,
} from 'lucide-vue-next'

import Button from '@/shared/ui/Button.vue'

export type MaskTool = 'sam' | 'polygon'

const props = defineProps<{
  tool: MaskTool
  canUndo: boolean
  canConfirm: boolean
  isLocked: boolean
  hideMask: boolean
  hasMask: boolean
}>()

const emit = defineEmits<{
  'update:tool': [tool: MaskTool]
  'update:hideMask': [v: boolean]
  undo: []
  clear: []
  confirm: []
  'zoom-in': []
  'zoom-out': []
  'reset-view': []
}>()

// 2-click 確認清除：第一次點 → armed；第二次點 → 真的清；3 秒沒點 → 復原。
const clearArmed = ref(false)
let armTimer: ReturnType<typeof setTimeout> | null = null

function onClearClick() {
  if (props.isLocked) return
  if (!clearArmed.value) {
    clearArmed.value = true
    if (armTimer) clearTimeout(armTimer)
    armTimer = setTimeout(() => { clearArmed.value = false }, 3000)
    return
  }
  if (armTimer) clearTimeout(armTimer)
  clearArmed.value = false
  emit('clear')
}

// 鎖定狀態切換時直接 disarm（避免之前 arm 過卻被忽略後又生效）
watch(() => props.isLocked, (locked) => {
  if (locked) {
    clearArmed.value = false
    if (armTimer) clearTimeout(armTimer)
  }
})
</script>

<template>
  <div class="sticky top-0 z-20 -mx-5 -mt-5 mb-4 px-5 py-3 bg-paper-surface/95 backdrop-blur-sm border-b border-line-hairline">
    <div class="flex flex-wrap gap-2 items-center">
      <!-- 工具切換 -->
      <div class="inline-flex border border-line-strong rounded-[var(--radius-xs)] overflow-hidden">
        <button
          type="button"
          class="px-3 h-9 inline-flex items-center gap-1.5 text-[13px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          :class="tool === 'sam' ? 'bg-accent text-paper-surface' : 'bg-paper-surface text-ink-default hover:bg-paper-subtle'"
          :disabled="isLocked"
          title="切到 SAM 點選（V）"
          @click="emit('update:tool', 'sam')"
        >
          <MousePointer2 :size="14" :stroke-width="1.5" />
          SAM 點選
        </button>
        <button
          type="button"
          class="px-3 h-9 inline-flex items-center gap-1.5 text-[13px] border-l border-line-strong transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          :class="tool === 'polygon' ? 'bg-accent text-paper-surface' : 'bg-paper-surface text-ink-default hover:bg-paper-subtle'"
          :disabled="isLocked"
          title="切到多邊形（P）"
          @click="emit('update:tool', 'polygon')"
        >
          <Pentagon :size="14" :stroke-width="1.5" />
          多邊形
        </button>
      </div>

      <div class="h-6 w-px bg-line-hairline" />

      <Button variant="secondary" :disabled="isLocked || !canUndo" title="撤銷（Ctrl+Z）" @click="emit('undo')">
        <Undo2 :size="14" :stroke-width="1.5" />
        撤銷
      </Button>

      <Button
        :variant="clearArmed ? 'danger' : 'secondary'"
        :disabled="isLocked"
        :title="clearArmed ? '再點一次確認，3 秒內無動作會取消' : '清除全部標記'"
        @click="onClearClick"
      >
        <Trash2 :size="14" :stroke-width="1.5" />
        {{ clearArmed ? '再點一次確認' : '清除' }}
      </Button>

      <div class="h-6 w-px bg-line-hairline" />

      <!-- Zoom controls -->
      <Button variant="secondary" title="縮小" @click="emit('zoom-out')">
        <ZoomOut :size="14" :stroke-width="1.5" />
      </Button>
      <Button variant="secondary" title="放大" @click="emit('zoom-in')">
        <ZoomIn :size="14" :stroke-width="1.5" />
      </Button>
      <Button variant="secondary" title="重置 zoom + pan" @click="emit('reset-view')">
        <Maximize :size="14" :stroke-width="1.5" />
      </Button>

      <div class="h-6 w-px bg-line-hairline" />

      <!-- Hide mask toggle -->
      <Button
        variant="secondary"
        :disabled="!hasMask"
        :title="hasMask ? '切換遮罩顯示（按住 H 暫時隱藏）' : '尚無遮罩可隱藏'"
        @click="emit('update:hideMask', !hideMask)"
      >
        <component :is="hideMask ? EyeOff : Eye" :size="14" :stroke-width="1.5" />
        {{ hideMask ? '顯示遮罩' : '隱藏遮罩' }}
      </Button>

      <div class="flex-1" />

      <Button
        variant="primary"
        :disabled="isLocked || !canConfirm"
        @click="emit('confirm')"
      >
        <Check :size="14" :stroke-width="1.5" />
        儲存並啟動批次
      </Button>
    </div>

    <!-- 提示文字（隨工具切換）-->
    <p class="mt-2 text-[12px] text-ink-muted leading-snug">
      <template v-if="tool === 'sam'">
        左鍵 = 前景點（綠 / 主體）· 右鍵空白 = 背景點（紅）· 右鍵 marker = 刪除
      </template>
      <template v-else>
        左鍵加頂點 · 右鍵空白（≥3 點）= 閉合並開新多邊形 · 右鍵多邊形 = 刪除 · Esc = 取消當前
      </template>
      <span class="mx-2 text-line-strong">|</span>
      滾輪縮放 · 空白+拖移 · Ctrl+Z 撤銷 · V/P 切工具 · 按住 H 暫時隱藏遮罩
    </p>
  </div>
</template>
