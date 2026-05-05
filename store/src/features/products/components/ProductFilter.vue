<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, X } from 'lucide-vue-next'
import { useThemesQuery, useSeriesQuery, useTagsQuery } from '@/features/browse/queries'
import type { SeriesListItem } from '@/features/browse/api'
import type { Difficulty } from '../api'

interface FilterState {
  theme_id?: string
  series_id?: string
  difficulty?: Difficulty
  canvas_size?: string
  tag_id?: string
}

const props = defineProps<{
  modelValue: FilterState
}>()
const emit = defineEmits<{
  'update:modelValue': [value: FilterState]
  'close': []
}>()

const themesQuery = useThemesQuery()
const seriesQuery = useSeriesQuery()
const tagsQuery = useTagsQuery()

const DIFFICULTIES: { code: Difficulty; label: string }[] = [
  { code: 'beginner', label: '入門' },
  { code: 'elementary', label: '初級' },
  { code: 'intermediate', label: '中級' },
  { code: 'advanced', label: '進階' },
]

const CANVAS_SIZES = [
  { code: '20x20', label: '20×20' }, { code: '30x30', label: '30×30' },
  { code: '40x40', label: '40×40' }, { code: '50x50', label: '50×50' },
  { code: '60x60', label: '60×60' }, { code: '30x40', label: '30×40' },
  { code: '30x50', label: '30×50' }, { code: '30x60', label: '30×60' },
  { code: '40x50', label: '40×50' }, { code: '40x60', label: '40×60' },
  { code: '50x60', label: '50×60' }, { code: '40x30', label: '40×30' },
  { code: '50x30', label: '50×30' }, { code: '60x30', label: '60×30' },
  { code: '50x40', label: '50×40' }, { code: '60x40', label: '60×40' },
  { code: '60x50', label: '60×50' },
]

const collapsed = ref<Record<string, boolean>>({
  theme: false,
  difficulty: false,
  canvas: true,
  tag: false,
})

function toggle(key: string) {
  collapsed.value[key] = !collapsed.value[key]
}

function set<K extends keyof FilterState>(key: K, value: FilterState[K] | undefined) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

// Group series by theme_id
const seriesByTheme = computed<Record<string, SeriesListItem[]>>(() => {
  const map: Record<string, SeriesListItem[]> = {}
  for (const s of seriesQuery.data.value?.items ?? []) {
    const key = s.theme_id ?? '__none__'
    if (!map[key]) map[key] = []
    map[key].push(s)
  }
  return map
})

const orphanSeries = computed(() => seriesByTheme.value['__none__'] ?? [])

// Theme expansion state
const themeExpanded = ref<Record<string, boolean>>({})

// 自動：當 theme_id 在 modelValue 中、自動展開該 theme
function isThemeExpanded(themeId: string) {
  return themeExpanded.value[themeId] ?? props.modelValue.theme_id === themeId
}

function clickTheme(themeId: string) {
  // 點主題名：toggle 該主題（已選 → clear；未選 → 設）+ 展開
  if (props.modelValue.theme_id === themeId) {
    emit('update:modelValue', {
      ...props.modelValue,
      theme_id: undefined,
      series_id: undefined,
    })
    themeExpanded.value[themeId] = false
  } else {
    emit('update:modelValue', {
      ...props.modelValue,
      theme_id: themeId,
      series_id: undefined,
    })
    themeExpanded.value[themeId] = true
  }
}

function toggleThemeExpand(themeId: string, e: MouseEvent) {
  e.stopPropagation()
  themeExpanded.value[themeId] = !isThemeExpanded(themeId)
}

function clickSeries(s: SeriesListItem) {
  emit('update:modelValue', {
    ...props.modelValue,
    theme_id: s.theme_id ?? undefined,
    series_id: s.id,
  })
}

function clearAllInTheme() {
  emit('update:modelValue', {
    ...props.modelValue,
    theme_id: undefined,
    series_id: undefined,
  })
}

const hasAnyFilter = computed(() =>
  !!(
    props.modelValue.theme_id ||
    props.modelValue.series_id ||
    props.modelValue.difficulty ||
    props.modelValue.canvas_size ||
    props.modelValue.tag_id
  ),
)

function clearAll() {
  emit('update:modelValue', {})
}
</script>

<template>
  <aside class="filter">
    <header class="filter-header">
      <span class="filter-title">篩選</span>
      <button
        v-if="hasAnyFilter"
        type="button"
        class="filter-clear"
        @click="clearAll"
      >
        清除全部
      </button>
      <button type="button" class="filter-close-mobile" aria-label="關閉" @click="emit('close')">
        <X />
      </button>
    </header>

    <!-- 主題 + 巢狀系列 -->
    <section class="group">
      <button class="group-toggle" type="button" @click="toggle('theme')">
        <span>主題 / 系列</span>
        <ChevronDown class="chevron" :class="{ 'is-collapsed': collapsed.theme }" />
      </button>
      <ul v-show="!collapsed.theme" class="group-list">
        <li>
          <button
            type="button"
            class="opt opt-root"
            :class="{ 'opt-active': !modelValue.theme_id && !modelValue.series_id }"
            @click="clearAllInTheme"
          >全部</button>
        </li>

        <li v-for="t in themesQuery.data.value?.items" :key="t.id" class="theme-li">
          <div class="theme-row">
            <button
              type="button"
              class="opt opt-theme"
              :class="{ 'opt-active': modelValue.theme_id === t.id }"
              @click="clickTheme(t.id)"
            >
              <span class="theme-name">{{ t.name }}</span>
              <span class="opt-count">{{ t.product_count }}</span>
            </button>
            <button
              v-if="(seriesByTheme[t.id]?.length ?? 0) > 0"
              type="button"
              class="theme-expand"
              :aria-label="isThemeExpanded(t.id) ? '收起' : '展開'"
              @click="(e) => toggleThemeExpand(t.id, e)"
            >
              <ChevronDown
                class="expand-chevron"
                :class="{ 'is-open': isThemeExpanded(t.id) }"
              />
            </button>
          </div>

          <ul
            v-show="isThemeExpanded(t.id) && (seriesByTheme[t.id]?.length ?? 0) > 0"
            class="series-sublist"
          >
            <li v-for="s in seriesByTheme[t.id]" :key="s.id">
              <button
                type="button"
                class="opt opt-series"
                :class="{ 'opt-active': modelValue.series_id === s.id }"
                @click="clickSeries(s)"
              >
                <span class="series-bullet">└</span>
                <span class="series-name">{{ s.name }}</span>
                <span class="opt-count">{{ s.product_count }}</span>
              </button>
            </li>
          </ul>
        </li>

        <!-- 未歸屬主題的系列 -->
        <li v-if="orphanSeries.length > 0" class="theme-li theme-li-orphan">
          <div class="orphan-label">未歸屬主題</div>
          <ul class="series-sublist series-sublist-orphan">
            <li v-for="s in orphanSeries" :key="s.id">
              <button
                type="button"
                class="opt opt-series"
                :class="{ 'opt-active': modelValue.series_id === s.id }"
                @click="clickSeries(s)"
              >
                <span class="series-bullet">·</span>
                <span class="series-name">{{ s.name }}</span>
                <span class="opt-count">{{ s.product_count }}</span>
              </button>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <!-- 難易度 -->
    <section class="group">
      <button class="group-toggle" type="button" @click="toggle('difficulty')">
        <span>難易度</span>
        <ChevronDown class="chevron" :class="{ 'is-collapsed': collapsed.difficulty }" />
      </button>
      <ul v-show="!collapsed.difficulty" class="group-list">
        <li>
          <button
            type="button"
            class="opt"
            :class="{ 'opt-active': !modelValue.difficulty }"
            @click="set('difficulty', undefined)"
          >全部</button>
        </li>
        <li v-for="d in DIFFICULTIES" :key="d.code">
          <button
            type="button"
            class="opt"
            :class="{ 'opt-active': modelValue.difficulty === d.code }"
            @click="set('difficulty', d.code)"
          >{{ d.label }}</button>
        </li>
      </ul>
    </section>

    <!-- 尺寸 -->
    <section class="group">
      <button class="group-toggle" type="button" @click="toggle('canvas')">
        <span>尺寸</span>
        <ChevronDown class="chevron" :class="{ 'is-collapsed': collapsed.canvas }" />
      </button>
      <div v-show="!collapsed.canvas" class="canvas-grid">
        <button
          type="button"
          class="canvas-chip"
          :class="{ 'canvas-chip-active': !modelValue.canvas_size }"
          @click="set('canvas_size', undefined)"
        >全部</button>
        <button
          v-for="c in CANVAS_SIZES"
          :key="c.code"
          type="button"
          class="canvas-chip"
          :class="{ 'canvas-chip-active': modelValue.canvas_size === c.code }"
          @click="set('canvas_size', c.code)"
        >{{ c.label }}</button>
      </div>
    </section>

    <!-- 標籤 -->
    <section class="group">
      <button class="group-toggle" type="button" @click="toggle('tag')">
        <span>標籤</span>
        <ChevronDown class="chevron" :class="{ 'is-collapsed': collapsed.tag }" />
      </button>
      <div v-show="!collapsed.tag" class="tag-chips">
        <button
          type="button"
          class="tag-chip"
          :class="{ 'tag-chip-active': !modelValue.tag_id }"
          @click="set('tag_id', undefined)"
        >全部</button>
        <button
          v-for="t in tagsQuery.data.value?.items"
          :key="t.id"
          type="button"
          class="tag-chip"
          :class="{ 'tag-chip-active': modelValue.tag_id === t.id }"
          @click="set('tag_id', t.id)"
        >{{ t.name }}</button>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.filter {
  width: 240px;
  flex-shrink: 0;
}

.filter-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--color-line);
}

.filter-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}

.filter-clear {
  background: transparent;
  border: none;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  cursor: pointer;
  padding: 4px 0;
}

.filter-close-mobile {
  display: none;
  background: transparent;
  border: none;
  cursor: pointer;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-default);
}
.filter-close-mobile :deep(svg) {
  width: 18px; height: 18px;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}

.group {
  border-bottom: 1px solid var(--color-line-subtle);
  padding: 0 0 16px;
  margin-bottom: 16px;
}
.group:last-child { border-bottom: none; }

.group-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  border: none;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-strong);
  padding: 8px 0;
  cursor: pointer;
  margin-bottom: 8px;
}

.chevron {
  width: 14px; height: 14px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none;
  transition: transform 200ms;
}
.chevron.is-collapsed { transform: rotate(-90deg); }

.group-list {
  list-style: none; padding: 0; margin: 0;
}
.group-list > li { margin: 0; }

.opt {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  border: none;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  text-align: left;
  padding: 6px 0;
  cursor: pointer;
  transition: color 120ms;
}
.opt:hover { color: var(--color-accent); }
.opt-active {
  color: var(--color-accent);
  font-weight: 400;
}

.opt-count {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
  flex-shrink: 0;
  margin-left: 8px;
}

.opt-root {
  font-weight: 400;
}

/* Theme row with expand button */
.theme-li { padding: 0; }

.theme-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.opt-theme {
  flex: 1;
  min-width: 0;
}

.theme-name {
  flex: 1;
  text-align: left;
}

.theme-expand {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-xs);
  flex-shrink: 0;
  transition: background 120ms;
}
.theme-expand:hover {
  background: var(--color-paper-deep);
}

.expand-chevron {
  width: 12px; height: 12px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none;
  transition: transform 200ms;
}
.expand-chevron.is-open {
  transform: rotate(180deg);
  stroke: var(--color-accent);
}

/* Series sublist (nested) */
.series-sublist {
  list-style: none;
  padding: 0;
  margin: 4px 0 8px;
  border-left: 1px solid var(--color-line-subtle);
  margin-left: 8px;
}

.series-sublist > li { margin: 0; }

.opt-series {
  font-size: 13px;
  padding: 5px 0 5px 12px;
  gap: 6px;
}

.series-bullet {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-line);
  flex-shrink: 0;
  line-height: 1;
}

.series-name {
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.opt-series.opt-active .series-bullet {
  color: var(--color-accent);
}

/* Orphan series */
.theme-li-orphan { margin-top: 12px; }

.orphan-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  padding: 6px 0 4px;
}

.series-sublist-orphan {
  margin-left: 0;
  border-left: none;
}

/* Difficulty / Detail / Tag / Canvas */
.canvas-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.canvas-chip {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--color-ink-default);
  background: transparent;
  border: 1px solid var(--color-line-subtle);
  padding: 6px 4px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 120ms;
}
.canvas-chip:hover { border-color: var(--color-accent); }
.canvas-chip-active {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}

.tag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  background: transparent;
  border: 1px solid var(--color-line-subtle);
  padding: 5px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 120ms;
}
.tag-chip:hover { border-color: var(--color-accent); }
.tag-chip-active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: var(--color-paper-canvas);
}

@media (max-width: 1023px) {
  .filter-close-mobile { display: inline-flex; }
}
</style>
