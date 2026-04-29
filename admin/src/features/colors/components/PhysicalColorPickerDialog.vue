<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from '@/shared/ui/Dialog.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Select from '@/shared/ui/Select.vue'
import { Search, Sparkles, Palette } from 'lucide-vue-next'

import { useColorsQuery } from '../queries'
import { rgbToHex, type PhysicalColor } from '../api'
import { labDistance } from '../api_mapping'

const props = defineProps<{
  open: boolean
  /** 演算法 RGB（用來算 LAB 距離找推薦）*/
  algorithmRgb: [number, number, number]
  /** 目前選中的 physical_color id（避免重複選同一個）*/
  currentId: string | null
}>()

const emit = defineEmits<{
  close: []
  pick: [physicalColorId: string]
}>()

const { data: colorsData } = useColorsQuery(() => ({}))
const allColors = computed(() => colorsData.value?.items ?? [])

const tab = ref<'recommend' | 'family' | 'search'>('recommend')
const searchKeyword = ref('')
const familyFilter = ref<string>('')

watch(
  () => props.open,
  (v) => {
    if (v) {
      tab.value = 'recommend'
      searchKeyword.value = ''
      familyFilter.value = ''
    }
  },
)

// 自動推薦：依 LAB 距離排序，過濾 is_active + stock_ml > 0 優先
const recommendations = computed(() => {
  const list = allColors.value
    .filter((c) => c.is_active)
    .map((c) => ({
      color: c,
      distance: labDistance(props.algorithmRgb, c.rgb),
    }))
    .sort((a, b) => {
      // 有庫存優先；同有/同無庫存內按距離
      const aStocked = a.color.stock_ml > 0
      const bStocked = b.color.stock_ml > 0
      if (aStocked !== bStocked) return aStocked ? -1 : 1
      return a.distance - b.distance
    })
  return list.slice(0, 10)
})

const families = computed(() => {
  const fams = new Set<string>()
  for (const c of allColors.value) {
    if (c.color_family) fams.add(c.color_family)
  }
  return Array.from(fams).sort()
})

const familyOptions = computed(() => [
  { value: '', label: '— 請選色系 —' },
  ...families.value.map((f) => ({ value: f, label: f })),
])

const familyResults = computed(() => {
  if (!familyFilter.value) return []
  return allColors.value.filter(
    (c) => c.is_active && c.color_family === familyFilter.value,
  )
})

const searchResults = computed(() => {
  const k = searchKeyword.value.trim().toLowerCase()
  if (!k) return []
  return allColors.value
    .filter(
      (c) =>
        c.is_active &&
        (c.code.toLowerCase().includes(k) || c.name.toLowerCase().includes(k)),
    )
    .slice(0, 30)
})

function pick(c: PhysicalColor) {
  emit('pick', c.id)
}

const algoHex = computed(() => rgbToHex(props.algorithmRgb))
</script>

<template>
  <Dialog :open="open" title="選擇實體色" size="lg" @close="emit('close')">
    <div class="space-y-4 text-[13px]">
      <!-- 演算法色預覽 -->
      <div class="p-3 border border-line-hairline rounded-[var(--radius-xs)] bg-paper-subtle">
        <p class="text-[12px] text-ink-muted mb-2">演算法產出的色（要為它找對應的實體色）</p>
        <div class="flex items-center gap-3">
          <div
            class="w-12 h-12 rounded-[var(--radius-xs)] border border-line-hairline"
            :style="{ backgroundColor: algoHex }"
          />
          <div>
            <p class="font-mono text-ink-strong">{{ algoHex }}</p>
            <p class="text-[11px] text-ink-muted">rgb({{ algorithmRgb.join(', ') }})</p>
          </div>
        </div>
      </div>

      <!-- 三 mode tabs -->
      <nav class="flex items-center gap-1 border-b border-line-hairline">
        <button
          v-for="t in [
            { id: 'recommend', label: '推薦', icon: Sparkles },
            { id: 'family', label: '色系', icon: Palette },
            { id: 'search', label: '搜尋', icon: Search },
          ]"
          :key="t.id"
          type="button"
          class="inline-flex items-center gap-1.5 h-9 px-3 text-[12px] border-b-2 -mb-px transition-colors"
          :class="
            tab === t.id
              ? 'border-accent text-ink-strong font-medium'
              : 'border-transparent text-ink-muted hover:text-ink-strong'
          "
          @click="tab = t.id as 'recommend' | 'family' | 'search'"
        >
          <component :is="t.icon" :size="12" :stroke-width="1.5" />
          {{ t.label }}
        </button>
      </nav>

      <!-- Recommend -->
      <div v-if="tab === 'recommend'" class="space-y-2 max-h-[400px] overflow-y-auto">
        <p class="text-[11px] text-ink-muted">依 LAB 色彩空間距離排序；有庫存者優先</p>
        <div
          v-for="(r, idx) in recommendations"
          :key="r.color.id"
          class="flex items-center gap-3 p-2 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle transition-colors"
          :class="r.color.id === currentId ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
          @click="pick(r.color)"
        >
          <span class="w-5 text-[11px] text-ink-muted font-mono">#{{ idx + 1 }}</span>
          <div
            class="w-8 h-8 rounded-[var(--radius-xs)] border border-line-hairline shrink-0"
            :style="{ backgroundColor: rgbToHex(r.color.rgb) }"
          />
          <div class="flex-1 min-w-0">
            <p class="text-ink-strong">
              <span class="font-mono text-[12px]">{{ r.color.code }}</span>
              <span class="ml-1">{{ r.color.name }}</span>
            </p>
            <p class="text-[11px] text-ink-muted">
              {{ rgbToHex(r.color.rgb) }} · 距離 {{ r.distance.toFixed(1) }} ·
              <span :class="r.color.stock_ml === 0 ? 'text-state-danger' : ''">
                庫存 {{ r.color.stock_ml }} ml
              </span>
            </p>
          </div>
        </div>
      </div>

      <!-- Family -->
      <div v-else-if="tab === 'family'" class="space-y-3">
        <Select v-model="familyFilter" :options="familyOptions" />
        <div
          v-if="familyResults.length === 0"
          class="text-ink-muted text-[12px] text-center py-6"
        >
          {{ familyFilter ? `「${familyFilter}」色系下無啟用中的實體色` : '請先選擇色系' }}
        </div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[360px] overflow-y-auto">
          <div
            v-for="c in familyResults"
            :key="c.id"
            class="flex items-center gap-2 p-2 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle transition-colors"
            :class="c.id === currentId ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
            @click="pick(c)"
          >
            <div
              class="w-7 h-7 rounded-[var(--radius-xs)] border border-line-hairline shrink-0"
              :style="{ backgroundColor: rgbToHex(c.rgb) }"
            />
            <div class="flex-1 min-w-0">
              <p class="text-[12px] font-mono text-ink-strong">{{ c.code }}</p>
              <p class="text-[11px] text-ink-default truncate">{{ c.name }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Search -->
      <div v-else-if="tab === 'search'" class="space-y-3">
        <Input v-model="searchKeyword" placeholder="輸入色號或名稱關鍵字..." />
        <div
          v-if="searchResults.length === 0 && searchKeyword"
          class="text-ink-muted text-[12px] text-center py-6"
        >
          無符合的實體色
        </div>
        <div v-else-if="searchResults.length > 0" class="space-y-1 max-h-[360px] overflow-y-auto">
          <div
            v-for="c in searchResults"
            :key="c.id"
            class="flex items-center gap-3 p-2 border border-line-hairline rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle transition-colors"
            :class="c.id === currentId ? 'border-accent bg-[var(--color-accent)]/[0.04]' : ''"
            @click="pick(c)"
          >
            <div
              class="w-7 h-7 rounded-[var(--radius-xs)] border border-line-hairline shrink-0"
              :style="{ backgroundColor: rgbToHex(c.rgb) }"
            />
            <div class="flex-1 min-w-0">
              <p class="text-ink-strong">
                <span class="font-mono text-[12px]">{{ c.code }}</span>
                <span class="ml-1">{{ c.name }}</span>
              </p>
              <p class="text-[11px] text-ink-muted">
                {{ c.color_family || '—' }} · 庫存 {{ c.stock_ml }} ml
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" @click="emit('close')">取消</Button>
    </template>
  </Dialog>
</template>
