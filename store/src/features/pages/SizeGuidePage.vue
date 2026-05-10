<script setup lang="ts">
// /size-guide — 尺寸指南
// 對應 docs/yii_mui_static_pages_spec.md 第三頁
// 自訂元件：真實比例方塊 + 生活化對照 + 摺疊式完整尺寸表
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { ChevronDown } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('尺寸指南｜易木 YIIMUI')

// 視覺渲染比例：1cm = 3px，max 60cm = 180px
const SCALE = 3

interface SignatureSize {
  label: string       // "20×20"
  unit: string        // "cm"
  w: number           // visual width cm
  h: number           // visual height cm
  compare: string     // "≈ 一張 CD 大小"
  place: string       // "書桌、床頭櫃、層架小角"
  topic: string       // "迷你花卉、寵物大頭照"
  duration: string    // "半天 ~ 一天"
  tag?: string        // "直幅" / "橫幅"
}

const SIGNATURE: SignatureSize[] = [
  {
    label: '20×20', unit: 'cm', w: 20, h: 20,
    compare: '≈ 一張 CD 大小',
    place: '書桌、床頭櫃、層架小角',
    topic: '迷你花卉、寵物大頭照',
    duration: '半天 ~ 一天',
  },
  {
    label: '30×30', unit: 'cm', w: 30, h: 30,
    compare: '≈ 一本雜誌大小',
    place: '書桌、玄關、茶几',
    topic: '單一花朵、單一動物',
    duration: '1 ~ 2 天',
  },
  {
    label: '30×40', unit: 'cm', w: 30, h: 40, tag: '直幅',
    compare: '≈ A3 紙',
    place: '沙發牆、臥室掛畫',
    topic: '風景、人物半身、寵物全身',
    duration: '1 週左右',
  },
  {
    label: '40×50', unit: 'cm', w: 50, h: 40, tag: '橫幅',
    compare: '≈ 筆電打開的螢幕',
    place: '客廳主視覺、玄關大牆',
    topic: '完整風景、家庭合照、紀念場景',
    duration: '2-3 週',
  },
]

const CUSTOM: { label: string; w: number; h: number; tag: string; title: string; suit: string }[] = [
  {
    label: '40×40', w: 40, h: 40, tag: '正方形',
    title: '客製入門款',
    suit: '單一寵物、單一人像',
  },
  {
    label: '50×50', w: 50, h: 50, tag: '正方形',
    title: '客製主流款',
    suit: '情侶、寵物全身、家庭照',
  },
  {
    label: '50×60', w: 60, h: 50, tag: '橫幅',
    title: '客製旗艦款',
    suit: '家庭橫照、情侶橫照、紀念場景',
  },
]

interface FullRow { sizes: string; price: string; pickup: 'ok' | 'warn' }
const FULL_TABLE: FullRow[] = [
  { sizes: '20×20', price: 'NT$ 205–296', pickup: 'ok' },
  { sizes: '30×30', price: 'NT$ 309–416', pickup: 'ok' },
  { sizes: '30×40 / 40×30', price: 'NT$ 397–518', pickup: 'ok' },
  { sizes: '30×50 / 40×40 / 50×30', price: 'NT$ 413–537', pickup: 'ok' },
  { sizes: '30×60 / 40×50 / 50×40', price: 'NT$ 501–638', pickup: 'ok' },
  { sizes: '40×60 / 60×40 / 50×50', price: 'NT$ 517–657', pickup: 'warn' },
  { sizes: '50×60 / 60×50', price: 'NT$ 605–759', pickup: 'warn' },
  { sizes: '60×60', price: 'NT$ 693–860', pickup: 'warn' },
]

const fullOpen = ref(false)
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="01"
      chapter="Reference"
      title="該選多大？跟著畫面感覺走"
      caption="Canvas Sizes"
    />

    <p class="lede">
      從 20×20 的書桌小品，到 60×60 的客廳主視覺，<br />
      找到適合你空間的那一幅。
    </p>

    <!-- 首波 4 個尺寸 -->
    <section class="section">
      <header class="section-rule">
        <span class="rule-aux">signature sizes</span>
        <span class="rule-line"></span>
      </header>
      <h2 class="section-title">首波 4 個尺寸</h2>

      <ul class="size-list">
        <li v-for="s in SIGNATURE" :key="s.label" class="size-card">
          <div class="size-visual">
            <div class="visual-frame">
              <div
                class="visual-block"
                :style="{
                  width: `${s.w * SCALE}px`,
                  height: `${s.h * SCALE}px`,
                }"
              >
                <span class="visual-label">{{ s.label }}</span>
              </div>
              <span class="visual-unit">{{ s.unit }}</span>
            </div>
          </div>

          <div class="size-meta">
            <header class="meta-head">
              <h3 class="meta-title">{{ s.label }} {{ s.unit }}</h3>
              <span v-if="s.tag" class="meta-tag">{{ s.tag }}</span>
            </header>
            <p class="meta-compare">{{ s.compare }}</p>

            <dl class="meta-rows">
              <div class="meta-row">
                <dt>適合擺放</dt>
                <dd>{{ s.place }}</dd>
              </div>
              <div class="meta-row">
                <dt>適合題材</dt>
                <dd>{{ s.topic }}</dd>
              </div>
              <div class="meta-row">
                <dt>完成時間</dt>
                <dd>{{ s.duration }}</dd>
              </div>
            </dl>
          </div>
        </li>
      </ul>
    </section>

    <!-- 想做更大 — 客製推薦 -->
    <section class="section">
      <header class="section-rule">
        <span class="rule-aux">custom recommended</span>
        <span class="rule-line"></span>
      </header>
      <h2 class="section-title">想做更大？這幾個尺寸最適合客製</h2>

      <div class="custom-grid">
        <div v-for="c in CUSTOM" :key="c.label" class="custom-card">
          <div class="custom-visual">
            <div
              class="visual-block visual-block-sm"
              :style="{
                width: `${c.w * SCALE * 0.7}px`,
                height: `${c.h * SCALE * 0.7}px`,
              }"
            >
              <span class="visual-label">{{ c.label }}</span>
            </div>
          </div>
          <span class="custom-tag">{{ c.tag }}</span>
          <h3 class="custom-title">{{ c.title }}</h3>
          <p class="custom-suit">{{ c.suit }}</p>
        </div>
      </div>

      <RouterLink to="/custom-process" class="custom-cta">
        看客製化流程 →
      </RouterLink>
    </section>

    <!-- 完整 16 種尺寸 (摺疊) -->
    <section class="section">
      <button
        type="button"
        class="full-toggle"
        :class="{ 'full-toggle-open': fullOpen }"
        :aria-expanded="fullOpen"
        @click="fullOpen = !fullOpen"
      >
        <ChevronDown :size="16" class="toggle-icon" />
        <span>查看完整 16 種尺寸與售價區間</span>
      </button>

      <Transition name="fold">
        <div v-if="fullOpen" class="full-body">
          <table class="full-table">
            <thead>
              <tr>
                <th>尺寸</th>
                <th>參考售價</th>
                <th>超商取貨</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in FULL_TABLE" :key="r.sizes">
                <td>{{ r.sizes }}</td>
                <td class="price-cell">{{ r.price }}</td>
                <td>
                  <span :class="['pickup-badge', `pickup-${r.pickup}`]">
                    {{ r.pickup === 'ok' ? '✓ 可' : '⚠ 建議宅配' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="full-note">
            任一邊長超過 40 cm 的尺寸建議改選宅配，以避免超商包裹尺寸限制。<br />
            售價會依難易度與細緻度加乘，實際售價以商品頁標示為準。
          </p>
        </div>
      </Transition>
    </section>

    <!-- 框架規格 -->
    <section class="section section-light">
      <h2 class="section-title-sm">框架規格</h2>
      <ul class="spec-list">
        <li>
          <strong>畫布材質</strong>
          <span>加厚棉麻織布裱於 1.5 cm MDF 板上</span>
        </li>
        <li>
          <strong>表面</strong>
          <span>已上 acrylic primer 底劑，可直接上色</span>
        </li>
        <li>
          <strong>完成後</strong>
          <span>自帶背框，無需額外裱框，可直接掛牆</span>
        </li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
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
  margin: 8px 0 80px;
  max-width: 620px;
}

.section { margin-bottom: 96px; }

.section-rule {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.rule-aux {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.rule-line { flex: 1; height: 1px; background: var(--color-line-subtle); }

.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 26px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 36px;
}
.section-title-sm {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-line-subtle);
}

/* Signature size cards — left visual (real proportional block), right meta */
.size-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.size-card {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 32px;
  align-items: center;
  padding: 28px 32px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}

.size-visual {
  width: 220px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.visual-frame {
  position: relative;
  display: inline-flex;
  align-items: flex-end;
  justify-content: center;
}
.visual-block {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-deep) 100%);
  border-radius: var(--radius-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.visual-block-sm {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-deep) 100%);
}
.visual-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-paper-canvas);
  font-weight: 500;
}
.visual-unit {
  position: absolute;
  bottom: -22px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

/* Right meta panel */
.size-meta { min-width: 0; }
.meta-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 4px;
}
.meta-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.meta-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-fresh);
  border: 1px solid var(--color-fresh);
  padding: 1px 8px;
  border-radius: 999px;
  font-weight: 500;
}
.meta-compare {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
  margin: 0 0 16px;
}

.meta-rows {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.meta-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 14px;
  align-items: baseline;
}
.meta-row dt {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.meta-row dd {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0;
}

/* Custom recommendations — 3 column simplified */
.custom-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}
.custom-card {
  padding: 24px 20px 22px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  text-align: center;
}
.custom-visual {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.custom-tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 6px;
}
.custom-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 6px;
}
.custom-suit {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
  margin: 0;
}

.custom-cta {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 3px;
}
.custom-cta:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }

/* Full table toggle */
.full-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  transition: border-color 150ms, background 150ms;
}
.full-toggle:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.toggle-icon {
  stroke: var(--color-accent);
  stroke-width: 1.75;
  fill: none;
  transition: transform 240ms ease;
}
.full-toggle-open .toggle-icon { transform: rotate(180deg); }

.full-body {
  margin-top: 16px;
  overflow: hidden;
}
.full-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  overflow: hidden;
  margin-bottom: 16px;
}
.full-table th {
  background: var(--color-paper-deep);
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-line);
}
.full-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-line-subtle);
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.full-table tr:last-child td { border-bottom: none; }
.price-cell {
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--color-accent-wine) !important;
}
.pickup-badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 500;
}
.pickup-ok {
  background: rgba(127, 159, 121, 0.12);
  color: var(--color-fresh);
}
.pickup-warn {
  background: rgba(123, 46, 64, 0.08);
  color: var(--color-accent-wine);
}

.full-note {
  font-size: 12px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}

.fold-enter-active, .fold-leave-active {
  transition: opacity 240ms ease, max-height 240ms ease;
  max-height: 1200px;
}
.fold-enter-from, .fold-leave-to { opacity: 0; max-height: 0; }

/* Frame spec */
.spec-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.spec-list li {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 16px;
  align-items: baseline;
  padding: 12px 16px;
  background: var(--color-paper-surface);
  border-radius: var(--radius-xs);
}
.spec-list strong {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  font-weight: 500;
}
.spec-list span {
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
  .size-card { grid-template-columns: 180px 1fr; gap: 24px; padding: 24px; }
  .size-visual { width: 180px; height: 180px; }
  .custom-grid { grid-template-columns: 1fr; }
  .custom-visual { height: 120px; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 22px; margin-bottom: 28px; }
  .size-card { grid-template-columns: 1fr; gap: 20px; padding: 20px; }
  .size-visual { width: 100%; height: 200px; }
  .meta-row { grid-template-columns: 70px 1fr; gap: 10px; }
  .full-table { font-size: 12px; }
  .full-table th, .full-table td { padding: 10px 12px; }
}
</style>
