<script setup lang="ts">
// /pricing — 報價參考（自訂元件、互動式計算機）
// 對應 docs/yii_mui_static_pages_spec.md（pricing 是我們獨立頁）
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useTitle } from '@vueuse/core'
import {
  Loader2, Calculator, Users, PawPrint, Layers, Zap, ArrowRight,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('報價參考｜易木 YIIMUI')

const API_BASE = '/api/v1'

interface CanvasSize {
  id: string
  canvas_w_cm: number
  canvas_h_cm: number
  display_name: string
}

interface PhotoPriceRow {
  id: string
  canvas_w: number
  canvas_h: number
  difficulty: 'beginner' | 'elementary' | 'intermediate' | 'advanced'
  price: number
}

const canvasQuery = useQuery({
  queryKey: ['canvas-sizes'] as const,
  queryFn: async () => {
    const res = await fetch(`${API_BASE}/canvas-sizes`)
    if (!res.ok) throw new Error('canvas-sizes 載入失敗')
    return (await res.json()) as { items: CanvasSize[] }
  },
  staleTime: 30 * 60 * 1000,
})

const pricesQuery = useQuery({
  queryKey: ['custom-photo-prices'] as const,
  queryFn: async () => {
    const res = await fetch(`${API_BASE}/custom-photo-prices`)
    if (!res.ok) throw new Error('photo-prices 載入失敗')
    return (await res.json()) as { items: PhotoPriceRow[] }
  },
  staleTime: 30 * 60 * 1000,
})

const isLoading = computed(
  () => canvasQuery.isPending.value || pricesQuery.isPending.value,
)
const isError = computed(
  () => canvasQuery.isError.value || pricesQuery.isError.value,
)

// 規格化 + 排序尺寸（依面積由小到大）— 只保留 custom_photo_prices 有對應資料的尺寸
const canvasOptions = computed<CanvasSize[]>(() => {
  const items = canvasQuery.data.value?.items ?? []
  const prices = pricesQuery.data.value?.items ?? []
  const sizesWithPrices = new Set(prices.map((p) => `${p.canvas_w}x${p.canvas_h}`))
  return items
    .filter((c) => sizesWithPrices.has(`${c.canvas_w_cm}x${c.canvas_h_cm}`))
    .sort((a, b) => a.canvas_w_cm * a.canvas_h_cm - b.canvas_w_cm * b.canvas_h_cm)
})

// 已選尺寸（預設 30×40）
const selectedSizeId = ref<string | null>(null)
const selectedSize = computed<CanvasSize | null>(() => {
  if (!canvasOptions.value.length) return null
  const found = canvasOptions.value.find((c) => c.id === selectedSizeId.value)
  if (found) return found
  // default：30×40 或 list 中第一個
  return canvasOptions.value.find((c) => c.canvas_w_cm === 30 && c.canvas_h_cm === 40)
    ?? canvasOptions.value[0]
})

// 已選難度
type Difficulty = 'beginner' | 'elementary' | 'intermediate' | 'advanced'
const selectedDifficulty = ref<Difficulty>('intermediate')

const DIFFICULTIES: Array<{ value: Difficulty; label: string; desc: string }> = [
  { value: 'beginner', label: '入門', desc: '色塊大、色數少' },
  { value: 'elementary', label: '初級', desc: '稍多細節' },
  { value: 'intermediate', label: '中級', desc: '一般細緻度' },
  { value: 'advanced', label: '進階', desc: '精細色塊' },
]

// 即時試算
const currentPrice = computed<number | null>(() => {
  const rows = pricesQuery.data.value?.items ?? []
  const s = selectedSize.value
  if (!s) return null
  const found = rows.find(
    (r) =>
      r.canvas_w === s.canvas_w_cm
      && r.canvas_h === s.canvas_h_cm
      && r.difficulty === selectedDifficulty.value,
  )
  return found?.price ?? null
})

// 該尺寸 4 難度全價（左右切換時用）
const pricesForSelectedSize = computed<Record<Difficulty, number | null>>(() => {
  const rows = pricesQuery.data.value?.items ?? []
  const s = selectedSize.value
  const result: Record<Difficulty, number | null> = {
    beginner: null, elementary: null, intermediate: null, advanced: null,
  }
  if (!s) return result
  for (const r of rows) {
    if (r.canvas_w === s.canvas_w_cm && r.canvas_h === s.canvas_h_cm) {
      result[r.difficulty] = r.price
    }
  }
  return result
})

// 完整 table：row 是 size, column 是 4 個 difficulty
interface TableRow {
  size: CanvasSize
  prices: Record<Difficulty, number | null>
}

const allRows = computed<TableRow[]>(() => {
  const prices = pricesQuery.data.value?.items ?? []
  return canvasOptions.value.map((s) => {
    const row: Record<Difficulty, number | null> = {
      beginner: null, elementary: null, intermediate: null, advanced: null,
    }
    for (const p of prices) {
      if (p.canvas_w === s.canvas_w_cm && p.canvas_h === s.canvas_h_cm) {
        row[p.difficulty] = p.price
      }
    }
    return { size: s, prices: row }
  })
})

// 加費項目（admin 之後可以接 API；目前寫死）
const SURCHARGES = [
  { Icon: Users, label: '人物 2 人', amount: 200 },
  { Icon: Users, label: '人物 3 人以上', amount: 400 },
  { Icon: PawPrint, label: '寵物毛髮細節', amount: 250 },
  { Icon: Layers, label: '複雜背景', amount: 300 },
  { Icon: Zap, label: '加急（5 工作天）', amount: 500 },
]

// 範例（從即時試算動態挑選代表性的兩個）
function fmtMoney(n: number | null): string {
  if (n === null) return '—'
  return `NT$ ${n.toLocaleString('zh-TW')}`
}

function sizeLabel(s: CanvasSize): string {
  return `${s.canvas_w_cm}×${s.canvas_h_cm} cm`
}

// 視覺方塊比例（最大邊對應 60，每 cm 對應 2.5px）
const SCALE = 2.5
function sizePreview(s: CanvasSize) {
  return {
    width: `${s.canvas_w_cm * SCALE}px`,
    height: `${s.canvas_h_cm * SCALE}px`,
  }
}
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="04"
      chapter="Pricing"
      title="客製大概多少錢？"
      caption="Reference Quote"
    />

    <p class="lede">
      客製化照片的售價依<strong>畫布尺寸</strong>與<strong>難易度</strong>決定。<br />
      選下方的尺寸 × 難度即時試算，或往下看完整價格表。
    </p>

    <!-- Loading / Error states -->
    <div v-if="isLoading" class="state">
      <Loader2 class="spin" />
      <span>載入價格資料中…</span>
    </div>
    <div v-else-if="isError" class="state error">
      載入失敗，請稍後再試或聯絡我們
    </div>

    <template v-else-if="selectedSize">
      <!-- 互動試算器 -->
      <section class="section">
        <header class="section-head">
          <Calculator :size="18" class="section-icon" />
          <h2 class="section-title">即時試算</h2>
        </header>

        <div class="calc-card">
          <div class="calc-grid">
            <!-- 左側：尺寸選擇 -->
            <div class="calc-left">
              <p class="calc-step-no">01　選尺寸</p>
              <div class="size-chips">
                <button
                  v-for="s in canvasOptions"
                  :key="s.id"
                  type="button"
                  class="size-chip"
                  :class="{ 'size-chip-active': s.id === selectedSize?.id }"
                  @click="selectedSizeId = s.id"
                >{{ sizeLabel(s) }}</button>
              </div>

              <p class="calc-step-no calc-step-no-spaced">02　選難度</p>
              <div class="diff-chips">
                <button
                  v-for="d in DIFFICULTIES"
                  :key="d.value"
                  type="button"
                  class="diff-chip"
                  :class="{ 'diff-chip-active': d.value === selectedDifficulty }"
                  @click="selectedDifficulty = d.value"
                >
                  <span class="diff-chip-label">{{ d.label }}</span>
                  <span class="diff-chip-desc">{{ d.desc }}</span>
                </button>
              </div>
            </div>

            <!-- 右側：價格結果 + 視覺 -->
            <div class="calc-right">
              <div class="result-card">
                <div class="result-visual">
                  <div class="visual-frame">
                    <div class="visual-block" :style="sizePreview(selectedSize)">
                      <span class="visual-label">{{ sizeLabel(selectedSize) }}</span>
                    </div>
                  </div>
                </div>
                <div class="result-text">
                  <span class="result-eyebrow">{{ DIFFICULTIES.find(d => d.value === selectedDifficulty)?.label }} ・ {{ sizeLabel(selectedSize) }}</span>
                  <span class="result-price">{{ fmtMoney(currentPrice) }}</span>
                  <span class="result-note">起，依照片內容微調</span>
                </div>
                <RouterLink to="/custom/apply" class="result-cta">
                  申請報價
                  <ArrowRight :size="14" :stroke-width="1.5" />
                </RouterLink>
              </div>

              <!-- 同尺寸其他難度 quick switch -->
              <div class="result-other">
                <span class="result-other-label">同尺寸其他難度：</span>
                <span
                  v-for="d in DIFFICULTIES.filter(d => d.value !== selectedDifficulty)"
                  :key="d.value"
                  class="result-other-item"
                  @click="selectedDifficulty = d.value"
                >
                  {{ d.label }} {{ fmtMoney(pricesForSelectedSize[d.value]) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 完整價格表 -->
      <section class="section">
        <header class="section-head">
          <h2 class="section-title">完整價格表</h2>
        </header>

        <div class="full-table-wrap">
          <table class="full-table">
            <thead>
              <tr>
                <th class="col-size">尺寸</th>
                <th v-for="d in DIFFICULTIES" :key="d.value" class="col-price">
                  {{ d.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in allRows" :key="row.size.id">
                <td class="col-size">
                  <strong>{{ sizeLabel(row.size) }}</strong>
                </td>
                <td
                  v-for="d in DIFFICULTIES"
                  :key="d.value"
                  class="col-price"
                  :class="{
                    'col-price-current': row.size.id === selectedSize?.id && d.value === selectedDifficulty,
                  }"
                >{{ fmtMoney(row.prices[d.value]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 加費項目 -->
      <section class="section">
        <header class="section-head">
          <h2 class="section-title">常見加費項目</h2>
        </header>

        <p class="section-lede">
          以下加費依照片內容適用，**不會疊加**，由管理員依實際照片判斷後納入正式報價。
        </p>

        <ul class="surcharge-grid">
          <li v-for="s in SURCHARGES" :key="s.label" class="surcharge-card">
            <component :is="s.Icon" :size="20" class="surcharge-icon" />
            <span class="surcharge-label">{{ s.label }}</span>
            <span class="surcharge-amount">+ NT$ {{ s.amount }}</span>
          </li>
        </ul>
      </section>

      <!-- 試算範例 -->
      <section class="section">
        <header class="section-head">
          <h2 class="section-title">試算範例</h2>
        </header>

        <div class="example-grid">
          <article class="example-card">
            <span class="example-no">範例 01</span>
            <h3 class="example-title">30×40 中級・單人物</h3>
            <div class="example-calc">
              <div class="example-line">
                <span>基礎價</span>
                <span class="example-line-val">NT$ 1,020</span>
              </div>
              <div class="example-line example-line-total">
                <span><strong>總計</strong></span>
                <span class="example-total"><strong>NT$ 1,020</strong></span>
              </div>
            </div>
          </article>

          <article class="example-card">
            <span class="example-no">範例 02</span>
            <h3 class="example-title">40×50 進階・家庭照（3 人）・複雜背景</h3>
            <div class="example-calc">
              <div class="example-line">
                <span>基礎價</span>
                <span class="example-line-val">NT$ 1,850</span>
              </div>
              <div class="example-line">
                <span>+ 人物 3 人以上</span>
                <span class="example-line-val">NT$ 400</span>
              </div>
              <div class="example-line">
                <span>+ 複雜背景</span>
                <span class="example-line-val">NT$ 300</span>
              </div>
              <div class="example-line example-line-total">
                <span><strong>總計</strong></span>
                <span class="example-total"><strong>NT$ 2,550</strong></span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- 重要說明 -->
      <section class="section section-light">
        <h2 class="section-title-sm">重要說明</h2>
        <ul class="notes-list">
          <li>
            <strong>實際金額以管理員報價為準</strong> — 我們會依您提供的照片實際內容微調
          </li>
          <li>報價有效期 24 小時，可申請延長一次（再 +24h）</li>
          <li>加入購物車後可與一般商品合併結帳</li>
          <li>客製商品<strong>不計入</strong>免運門檻（除非使用免運券）</li>
        </ul>

        <RouterLink to="/custom/apply" class="apply-cta">
          上傳照片開始申請 →
        </RouterLink>
      </section>
    </template>
  </main>
</template>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 8px 0 64px;
  max-width: 640px;
}
.lede strong { font-weight: 500; color: var(--color-ink-strong); }

.state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  color: var(--color-ink-muted);
  font-size: 14px;
}
.state.error { color: var(--color-state-danger); }
.spin {
  width: 16px;
  height: 16px;
  stroke-width: 1.5;
  animation: spin 900ms linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.section { margin-bottom: 80px; }

.section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.section-icon {
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
}
.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.section-title-sm {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.section-lede {
  font-size: 13px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  margin: 0 0 20px;
  letter-spacing: 0.02em;
}

/* ── Interactive Calculator ── */
.calc-card {
  padding: 28px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
}
.calc-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 36px;
}

.calc-step-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
  margin: 0 0 14px;
}
.calc-step-no-spaced { margin-top: 24px; }

.size-chips, .diff-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.size-chip {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--color-ink-default);
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  padding: 7px 12px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 150ms;
}
.size-chip:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.size-chip-active {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}

.diff-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 10px 14px;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 150ms;
  text-align: left;
  flex: 1;
  min-width: 110px;
}
.diff-chip:hover { border-color: var(--color-accent); }
.diff-chip-active {
  background: var(--color-accent-tint);
  border-color: var(--color-accent);
}
.diff-chip-label {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
}
.diff-chip-desc {
  font-size: 11px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}

/* Right column — result */
.calc-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  padding: 24px;
  background: linear-gradient(135deg, var(--color-paper-canvas) 0%, var(--color-paper-deep) 100%);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 16px;
}
.result-visual {
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.visual-frame { display: inline-flex; }
.visual-block {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-deep) 100%);
  border-radius: var(--radius-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
  transition: width 240ms cubic-bezier(0.4, 0, 0.2, 1), height 240ms cubic-bezier(0.4, 0, 0.2, 1);
}
.visual-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--color-paper-canvas);
  font-weight: 500;
}
.result-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}
.result-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.result-price {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 38px;
  letter-spacing: 0.02em;
  color: var(--color-accent-wine);
  line-height: 1;
}
.result-note {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.result-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 1px solid var(--color-ink-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background 150ms, border-color 150ms;
}
.result-cta:hover {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.result-cta :deep(svg) { stroke: currentColor; fill: none; }

.result-other {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
  text-align: center;
  padding: 8px 4px;
}
.result-other-label { margin-right: 4px; }
.result-other-item {
  display: inline-block;
  margin: 0 6px;
  cursor: pointer;
  color: var(--color-ink-default);
  border-bottom: 1px dotted transparent;
  transition: color 150ms, border-color 150ms;
}
.result-other-item:hover {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

/* ── Full table ── */
.full-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.full-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 480px;
}
.full-table th {
  background: var(--color-paper-deep);
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--color-line);
}
.full-table th.col-price { text-align: right; }
.full-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-line-subtle);
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.full-table td.col-size strong {
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 12px;
  color: var(--color-ink-strong);
}
.full-table td.col-price {
  font-family: var(--font-mono);
  text-align: right;
  color: var(--color-ink-default);
}
.full-table tr:last-child td { border-bottom: none; }
.full-table tr:hover { background: var(--color-paper-surface); }
.full-table td.col-price-current {
  background: var(--color-accent-tint);
  color: var(--color-accent-wine);
  font-weight: 600;
}

/* ── Surcharges ── */
.surcharge-grid {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.surcharge-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.surcharge-icon {
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
}
.surcharge-label {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.surcharge-amount {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-accent-wine);
  letter-spacing: 0.04em;
}

/* ── Examples ── */
.example-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.example-card {
  padding: 22px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.example-no {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
  margin-bottom: 8px;
}
.example-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 16px;
  line-height: 1.5;
}
.example-calc {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.example-line {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.example-line-val {
  font-family: var(--font-mono);
  color: var(--color-ink-strong);
}
.example-line-total {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--color-line-subtle);
}
.example-total {
  font-family: var(--font-mono);
  font-size: 15px;
  color: var(--color-accent-wine);
}

/* ── Notes ── */
.notes-list {
  list-style: none;
  padding: 0;
  margin: 0 0 32px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.notes-list li {
  position: relative;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.85;
  letter-spacing: 0.02em;
  color: var(--color-ink-default);
}
.notes-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.85em;
  width: 8px;
  height: 1px;
  background: var(--color-accent);
}
.notes-list strong { color: var(--color-ink-strong); font-weight: 500; }

.apply-cta {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 3px;
}
.apply-cta:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
  .calc-grid { grid-template-columns: 1fr; gap: 24px; }
  .result-visual { height: 140px; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 20px; }
  .result-price { font-size: 30px; }
  .calc-card { padding: 20px; }
}
</style>
