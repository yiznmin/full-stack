<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Label from '@/shared/ui/Label.vue'
import Select from '@/shared/ui/Select.vue'
import { Loader2, AlertTriangle } from 'lucide-vue-next'

import type { PaletteColor } from '../api'

type OperationType = 'merge_color' | 'eliminate_border' | 'smooth_contour'

const props = defineProps<{
  open: boolean
  type: OperationType | null
  palette: PaletteColor[]
  pending: boolean
}>()

const emit = defineEmits<{
  close: []
  confirmMerge: [payload: { source_template_id: number; target_template_id: number }]
  confirmEliminate: [payload: { absorbed_template_id: number; surviving_template_id: number }]
  confirmSmooth: [payload: { border_between: [number, number]; smoothness: number }]
}>()

const param1 = ref<string>('')  // first template_id
const param2 = ref<string>('')  // second template_id
const smoothness = ref<string>('3')
const errors = ref<Record<string, string>>({})

watch(
  [() => props.open, () => props.type],
  () => {
    if (props.open) {
      param1.value = ''
      param2.value = ''
      smoothness.value = '3'
      errors.value = {}
    }
  },
)

const titles: Record<OperationType, string> = {
  merge_color: '合併色塊',
  eliminate_border: '消除邊界線',
  smooth_contour: '輪廓平滑',
}
const labels: Record<OperationType, { p1: string; p2: string; hint: string; warn: string }> = {
  merge_color: {
    p1: '來源色塊（會被併掉）',
    p2: '目標色塊（保留）',
    hint: '把來源色塊的所有像素改成目標色塊的顏色，重新跑 SVG。',
    warn: '會把 approved 退回 false（需重新審核）。',
  },
  eliminate_border: {
    p1: '被吸收的色塊（消失）',
    p2: '存活的色塊（吃掉對方）',
    hint: '把兩色塊間的邊界消去，被吸收側的像素改成存活側的顏色。',
    warn: '會把 approved 退回 false。',
  },
  smooth_contour: {
    p1: '邊界一側',
    p2: '邊界另一側',
    hint: '對指定兩色塊間的邊界輪廓做 Chaikin 平滑。',
    warn: '只改 SVG，不改 snapped_rgb；approved 不會退回。',
  },
}

const paletteOptions = computed(() => [
  { value: '', label: '— 請選 —' },
  ...props.palette.map((c) => ({
    value: String(c.template_id),
    label: `#${c.template_id} ${c.hex}`,
  })),
])

function validate(): boolean {
  const errs: Record<string, string> = {}
  const id1 = Number(param1.value)
  const id2 = Number(param2.value)
  if (!id1) errs.p1 = '必選'
  if (!id2) errs.p2 = '必選'
  if (id1 && id2 && id1 === id2) errs.p2 = '不可選同一個色塊'
  if (props.type === 'smooth_contour') {
    const s = Number(smoothness.value)
    if (!Number.isInteger(s) || s < 1 || s > 5) errs.smoothness = '請選 1~5'
  }
  errors.value = errs
  return Object.keys(errs).length === 0
}

function submit() {
  if (!validate() || !props.type) return
  const id1 = Number(param1.value)
  const id2 = Number(param2.value)
  if (props.type === 'merge_color') {
    emit('confirmMerge', { source_template_id: id1, target_template_id: id2 })
  } else if (props.type === 'eliminate_border') {
    emit('confirmEliminate', { absorbed_template_id: id1, surviving_template_id: id2 })
  } else if (props.type === 'smooth_contour') {
    emit('confirmSmooth', {
      border_between: [id1, id2],
      smoothness: Number(smoothness.value),
    })
  }
}

const smoothnessOptions = [
  { value: '1', label: '1（最弱）' },
  { value: '2', label: '2' },
  { value: '3', label: '3（標準）' },
  { value: '4', label: '4' },
  { value: '5', label: '5（最強）' },
]
</script>

<template>
  <Dialog
    :open="open"
    :title="type ? titles[type] : ''"
    size="md"
    @close="emit('close')"
  >
    <div v-if="type" class="space-y-4 text-[13px]">
      <p class="text-ink-default">{{ labels[type].hint }}</p>
      <p class="text-[12px] text-state-warning flex items-start gap-1">
        <AlertTriangle :size="12" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span>{{ labels[type].warn }}</span>
      </p>

      <div>
        <Label>{{ labels[type].p1 }}</Label>
        <Select v-model="param1" :options="paletteOptions" />
        <p v-if="errors.p1" class="mt-1 text-[12px] text-state-danger">{{ errors.p1 }}</p>
      </div>
      <div>
        <Label>{{ labels[type].p2 }}</Label>
        <Select v-model="param2" :options="paletteOptions" />
        <p v-if="errors.p2" class="mt-1 text-[12px] text-state-danger">{{ errors.p2 }}</p>
      </div>

      <div v-if="type === 'smooth_contour'">
        <Label>平滑強度</Label>
        <Select v-model="smoothness" :options="smoothnessOptions" />
        <p v-if="errors.smoothness" class="mt-1 text-[12px] text-state-danger">{{ errors.smoothness }}</p>
      </div>

      <p class="text-[11px] text-ink-muted">
        色塊編號可從上方「調色盤」卡看到（每色 #N 標記）。
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="pending" @click="emit('close')">取消</Button>
      <Button variant="primary" :disabled="pending" @click="submit">
        <Loader2 v-if="pending" :size="14" :stroke-width="1.5" class="animate-spin" />
        執行
      </Button>
    </template>
  </Dialog>
</template>
