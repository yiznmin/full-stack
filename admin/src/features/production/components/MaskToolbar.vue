<script setup lang="ts">
import { MousePointer2, Pentagon, Undo2, Trash2, Check } from 'lucide-vue-next'
import Button from '@/shared/ui/Button.vue'

export type MaskTool = 'sam' | 'polygon'

defineProps<{
  tool: MaskTool
  canUndo: boolean
  canConfirm: boolean
  isLocked: boolean  // status != pending → 不可編輯
}>()

const emit = defineEmits<{
  'update:tool': [tool: MaskTool]
  undo: []
  clear: []
  confirm: []
}>()
</script>

<template>
  <div class="flex flex-wrap gap-2 items-center">
    <!-- 工具切換：SAM 點選 / 多邊形 -->
    <div class="inline-flex border border-line-strong rounded-[var(--radius-xs)] overflow-hidden">
      <button
        type="button"
        class="px-3 h-9 inline-flex items-center gap-1.5 text-[13px] transition-colors"
        :class="tool === 'sam' ? 'bg-accent text-paper-surface' : 'bg-paper-surface text-ink-default hover:bg-paper-subtle'"
        :disabled="isLocked"
        @click="emit('update:tool', 'sam')"
      >
        <MousePointer2 :size="14" :stroke-width="1.5" />
        SAM 點選
      </button>
      <button
        type="button"
        class="px-3 h-9 inline-flex items-center gap-1.5 text-[13px] border-l border-line-strong transition-colors"
        :class="tool === 'polygon' ? 'bg-accent text-paper-surface' : 'bg-paper-surface text-ink-default hover:bg-paper-subtle'"
        :disabled="isLocked"
        @click="emit('update:tool', 'polygon')"
      >
        <Pentagon :size="14" :stroke-width="1.5" />
        多邊形
      </button>
    </div>

    <div class="h-6 w-px bg-line-hairline" />

    <Button variant="tertiary" :disabled="isLocked || !canUndo" @click="emit('undo')">
      <Undo2 :size="14" :stroke-width="1.5" />
      撤銷
    </Button>

    <Button variant="tertiary" :disabled="isLocked" @click="emit('clear')">
      <Trash2 :size="14" :stroke-width="1.5" />
      清除
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
  <p class="mt-2 text-[12px] text-ink-muted">
    <template v-if="tool === 'sam'">
      左鍵 = 前景點（綠 / 要保留的主體）/ 右鍵 = 背景點（紅 / 排除）
    </template>
    <template v-else>
      左鍵逐點加頂點 / 右鍵閉合（≥ 3 點）並開新多邊形 / 與 SAM 點可混用
    </template>
  </p>
</template>
