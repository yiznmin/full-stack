<script setup lang="ts">
import { computed, watch } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { TW_COUNTIES, getDistricts, normalizeCounty } from '@/shared/data/taiwan-districts'

const props = defineProps<{
  county: string
  district: string
}>()

const emit = defineEmits<{
  'update:county': [value: string]
  'update:district': [value: string]
}>()

const normalizedCounty = computed(() => normalizeCounty(props.county))

const districts = computed(() => getDistricts(normalizedCounty.value))

// 縣市改變且當前 district 不在新清單裡 → 清空
watch(
  () => normalizedCounty.value,
  (next, prev) => {
    if (next === prev) return
    if (props.district && !getDistricts(next).includes(props.district)) {
      emit('update:district', '')
    }
  },
)

function onCountyChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  emit('update:county', v)
}
function onDistrictChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  emit('update:district', v)
}
</script>

<template>
  <div class="picker">
    <div class="select-wrap">
      <label class="label" for="addr-county">縣市</label>
      <div class="select-shell">
        <select
          id="addr-county"
          class="select"
          :value="normalizedCounty"
          required
          @change="onCountyChange"
        >
          <option value="" disabled>請選擇縣市</option>
          <option v-for="c in TW_COUNTIES" :key="c" :value="c">{{ c }}</option>
        </select>
        <ChevronDown class="chev" :size="14" />
      </div>
    </div>

    <div class="select-wrap">
      <label class="label" for="addr-district">行政區</label>
      <div class="select-shell">
        <select
          id="addr-district"
          class="select"
          :value="district"
          required
          :disabled="!normalizedCounty"
          @change="onDistrictChange"
        >
          <option value="" disabled>{{ normalizedCounty ? '請選擇行政區' : '請先選縣市' }}</option>
          <option v-for="d in districts" :key="d" :value="d">{{ d }}</option>
        </select>
        <ChevronDown class="chev" :size="14" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.picker {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.select-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-default);
}

.select-shell {
  position: relative;
}

.select {
  width: 100%;
  appearance: none;
  -webkit-appearance: none;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-ink-strong);
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 11px 36px 11px 13px;
  outline: none;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms;
}
.select:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-tint);
}
.select:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  background: var(--color-paper-deep);
}

.chev {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  stroke: var(--color-ink-muted);
  stroke-width: 1.5;
  fill: none;
}

@media (max-width: 1023px) {
  .picker { grid-template-columns: 1fr; }
}
</style>
