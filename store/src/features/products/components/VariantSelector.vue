<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ProductVariant, Difficulty, Detail } from '../api'

const props = defineProps<{
  variants: ProductVariant[]
}>()

const emit = defineEmits<{
  'select': [variant: ProductVariant | null]
}>()

const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  beginner: '入門',
  elementary: '初級',
  intermediate: '中級',
  advanced: '進階',
}

const activeVariants = computed(() => props.variants.filter((v) => v.is_active))

function sizeKey(v: ProductVariant) {
  return `${v.canvas_w_cm}x${v.canvas_h_cm}`
}
function sizeLabel(key: string) {
  const [w, h] = key.split('x')
  return `${w}×${h} cm`
}

const allSizes = computed(() => {
  const set = new Set<string>()
  for (const v of activeVariants.value) set.add(sizeKey(v))
  return [...set]
})

const selectedSize = ref<string | null>(null)
const selectedDifficulty = ref<Difficulty | null>(null)

const allDifficulties: Difficulty[] = ['beginner', 'elementary', 'intermediate', 'advanced']
const availableDifficulties = computed(() => {
  if (!selectedSize.value) return new Set<Difficulty>()
  const set = new Set<Difficulty>()
  for (const v of activeVariants.value) {
    if (sizeKey(v) === selectedSize.value) set.add(v.difficulty)
  }
  return set
})

function selectSize(s: string) {
  if (selectedSize.value === s) return
  selectedSize.value = s
  selectedDifficulty.value = null
}
function selectDifficulty(d: Difficulty) {
  if (!availableDifficulties.value.has(d)) return
  selectedDifficulty.value = d
}

// 細緻度 fallback 偏好順序：standard 最常見 → detailed → rough → premium
const DETAIL_PREFERENCE: Detail[] = ['standard', 'detailed', 'rough', 'premium']

const matchedVariant = computed(() => {
  if (!selectedSize.value || !selectedDifficulty.value) return null
  const candidates = activeVariants.value.filter(
    (v) => sizeKey(v) === selectedSize.value && v.difficulty === selectedDifficulty.value,
  )
  if (candidates.length === 0) return null
  // 取偏好順序的第一個；若都無對應就拿第一個 candidate
  for (const d of DETAIL_PREFERENCE) {
    const found = candidates.find((v) => v.detail === d)
    if (found) return found
  }
  return candidates[0]
})

watch(matchedVariant, (val) => emit('select', val), { immediate: true })
</script>

<template>
  <div class="selector">
    <!-- 尺寸 -->
    <div class="step">
      <h4 class="step-label">
        <span class="step-num">01</span>
        畫布尺寸
      </h4>
      <div class="chips">
        <button
          v-for="s in allSizes"
          :key="s"
          type="button"
          class="chip"
          :class="{ 'chip-active': selectedSize === s }"
          @click="selectSize(s)"
        >{{ sizeLabel(s) }}</button>
      </div>
      <p v-if="allSizes.length === 0" class="empty">尚無可選尺寸</p>
    </div>

    <!-- 難易度 -->
    <div class="step" :class="{ 'step-disabled': !selectedSize }">
      <h4 class="step-label">
        <span class="step-num">02</span>
        難易度
      </h4>
      <div class="chips">
        <button
          v-for="d in allDifficulties"
          :key="d"
          type="button"
          class="chip"
          :class="{
            'chip-active': selectedDifficulty === d,
            'chip-disabled': selectedSize && !availableDifficulties.has(d),
          }"
          :disabled="!selectedSize || !availableDifficulties.has(d)"
          @click="selectDifficulty(d)"
        >{{ DIFFICULTY_LABEL[d] }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.selector {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: opacity 200ms;
}
.step-disabled {
  opacity: 0.4;
}

.step-label {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  font-weight: 400;
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 1px solid var(--color-line);
  border-radius: 50%;
  font-size: 10px;
  letter-spacing: 0;
  color: var(--color-ink-muted);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line);
  padding: 8px 16px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 150ms;
}
.chip:hover:not(:disabled):not(.chip-disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.chip-active {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}
.chip-active:hover {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}
.chip-disabled,
.chip:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  text-decoration: line-through;
}

.empty {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}
</style>
