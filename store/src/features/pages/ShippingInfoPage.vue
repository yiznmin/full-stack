<script setup lang="ts">
// /shipping-info — 配送與付款
// 對應 docs/yii_mui_static_pages_spec.md 第四頁
// 自訂元件：5 sections，重點數字大字呈現 + 品牌說明 footnote
import { useTitle } from '@vueuse/core'
import { CreditCard, Calendar, Package, Truck } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('配送與付款｜易木 YIIMUI')
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="04"
      chapter="Shipping & Payment"
      title="下單前，你會想知道的幾件事"
      caption="Logistics"
    />

    <p class="lede">
      下面是付款、製作、出貨、運費的所有規則 ——<br />
      寫得有點直白，但希望省下你來回詢問的時間。
    </p>

    <!-- 01 付款方式 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">01</span>
        <CreditCard :size="18" class="section-icon" />
        <h2 class="section-title">付款方式</h2>
      </header>

      <div class="hero-stat">
        <span class="stat-eyebrow">目前提供</span>
        <span class="stat-value">銀行轉帳</span>
        <span class="stat-foot">下單後 24 小時內完成轉帳並回填末五碼</span>
      </div>

      <aside class="brand-note">
        <h3 class="brand-note-title">為什麼是銀行轉帳？</h3>
        <p>
          易木 YIIMUI 是一個小型獨立品牌，把信用卡手續費省下來，
          換成更好的顏料、更紮實的畫布、更友善的減塑包裝。
          一筆轉帳的時間，是我們之間第一個共同完成的小儀式。
        </p>
      </aside>
    </section>

    <!-- 02 製作天數 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">02</span>
        <Calendar :size="18" class="section-icon" />
        <h2 class="section-title">製作天數</h2>
      </header>

      <div class="day-grid">
        <div class="day-card">
          <span class="day-eyebrow">現成款</span>
          <span class="day-value">5 – 10</span>
          <span class="day-unit">個工作天</span>
          <p class="day-note">下單付款確認後，立即進入製作排程。</p>
        </div>
        <div class="day-card">
          <span class="day-eyebrow">客製款</span>
          <span class="day-value">7 – 12</span>
          <span class="day-unit">個工作天</span>
          <p class="day-note">轉檔 1–2 天 + 確認後印製 5–10 天。</p>
        </div>
      </div>

      <aside class="callout">
        <span class="callout-tag">節慶提醒</span>
        <p>
          母親節、情人節、聖誕節等節日前下單的客人，建議至少預留
          <strong>14 天</strong>緩衝。我們是手工為你準備每一份 kit，
          趕件可能會犧牲品質。
        </p>
      </aside>
    </section>

    <!-- 03 出貨方式 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">03</span>
        <Package :size="18" class="section-icon" />
        <h2 class="section-title">出貨方式</h2>
      </header>

      <div class="ship-grid">
        <div class="ship-card">
          <span class="ship-method">超商取貨</span>
          <span class="ship-fee">NT$ <strong>60</strong></span>
          <span class="ship-suit">單邊 ≤ 40 cm 的尺寸</span>
        </div>
        <div class="ship-card">
          <span class="ship-method">宅配</span>
          <span class="ship-fee">NT$ <strong>120</strong></span>
          <span class="ship-suit">所有尺寸均適用</span>
        </div>
      </div>

      <p class="hint">
        任一邊長超過 <strong>40 cm</strong> 的尺寸建議改選宅配，以避免超商包裹尺寸限制。
      </p>
    </section>

    <!-- 04 運費規則 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">04</span>
        <Truck :size="18" class="section-icon" />
        <h2 class="section-title">運費規則</h2>
      </header>

      <ul class="rule-list">
        <li>
          <div class="rule-text">
            <span class="rule-label">現成款</span>
            <span class="rule-body">滿 <strong class="rule-strong">NT$ 1,000</strong> 免運</span>
          </div>
        </li>
        <li>
          <div class="rule-text">
            <span class="rule-label">客製款</span>
            <span class="rule-body">依實際運送方式收取（不適用滿額免運）</span>
          </div>
        </li>
      </ul>

      <aside class="brand-note">
        <p>
          客製款是為你獨立準備的作品，從照片轉檔到顏料配色都是專屬製作。
          因此客製款的運費獨立計算，不參與滿額活動。
        </p>
      </aside>
    </section>

    <!-- 05 訂單流程 -->
    <section class="section">
      <header class="section-head section-head-simple">
        <h2 class="section-title-sm">訂單流程</h2>
      </header>

      <ol class="flow">
        <li>
          <span class="flow-no">1</span>
          <div class="flow-text">
            <strong>付款確認</strong>
            <span>管理員核對您提供的轉帳資訊（24 小時內）</span>
          </div>
        </li>
        <li>
          <span class="flow-no">2</span>
          <div class="flow-text">
            <strong>進入製作</strong>
            <span>現貨商品立即備貨；客製商品安排 5–10 天製作期</span>
          </div>
        </li>
        <li>
          <span class="flow-no">3</span>
          <div class="flow-text">
            <strong>打包出貨</strong>
            <span>以物流寄出，發送出貨通知 email + 站內通知</span>
          </div>
        </li>
        <li>
          <span class="flow-no">4</span>
          <div class="flow-text">
            <strong>追蹤狀態</strong>
            <span>可在「我的訂單」查詢即時物流進度</span>
          </div>
        </li>
        <li>
          <span class="flow-no">5</span>
          <div class="flow-text">
            <strong>完成收貨</strong>
            <span>物流送達後請確認收貨，協助我們關單</span>
          </div>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 800px;
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

.section { margin-bottom: 88px; }

/* Section header */
.section-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.section-head-simple {
  border-bottom: 1px solid var(--color-line-subtle);
  padding-bottom: 12px;
  margin-bottom: 24px;
}
.section-no {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 22px;
  color: var(--color-accent);
  font-weight: 300;
  line-height: 1;
}
.section-icon {
  stroke: var(--color-ink-muted);
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
  margin: 0;
}

/* Hero stat (付款方式) */
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  margin-bottom: 20px;
}
.stat-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}
.stat-value {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.08em;
  color: var(--color-accent);
  line-height: 1.2;
  margin-bottom: 12px;
}
.stat-foot {
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

/* Day grid (製作天數) */
.day-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.day-card {
  padding: 24px 24px 22px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  text-align: center;
}
.day-eyebrow {
  display: block;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
  margin-bottom: 14px;
}
.day-value {
  display: block;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 42px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  line-height: 1;
  margin-bottom: 6px;
}
.day-unit {
  display: block;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
  margin-bottom: 14px;
}
.day-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  letter-spacing: 0.02em;
  color: var(--color-ink-default);
}

/* Ship grid (出貨方式) */
.ship-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.ship-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.ship-method {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}
.ship-fee {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-ink-muted);
  letter-spacing: 0.06em;
}
.ship-fee strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 28px;
  color: var(--color-accent-wine);
  letter-spacing: 0.02em;
  margin: 0 4px;
}
.ship-suit {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}

/* Rule list (運費規則) */
.rule-list {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rule-list li {
  padding: 18px 22px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.rule-text {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 18px;
  align-items: baseline;
}
.rule-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.rule-body {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  line-height: 1.6;
}
.rule-strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 22px;
  color: var(--color-accent);
  margin: 0 2px;
}

/* Brand note (footnote-style) */
.brand-note {
  margin: 0;
  padding: 18px 22px;
  background: var(--color-paper-deep);
  border-left: 2px solid var(--color-accent);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}
.brand-note-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.brand-note p {
  margin: 0;
  font-size: 13px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
}

/* Callout (節慶提醒) */
.callout {
  margin: 0;
  padding: 18px 22px;
  background: rgba(196, 122, 79, 0.08);
  border: 1px solid var(--color-accent-soft);
  border-radius: var(--radius-xs);
}
.callout-tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 500;
  margin-bottom: 6px;
}
.callout p {
  margin: 0;
  font-size: 13px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}
.callout strong {
  font-weight: 500;
  color: var(--color-accent);
}

/* Hint */
.hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}
.hint strong {
  font-weight: 500;
  color: var(--color-ink-default);
}

/* Flow */
.flow {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.flow li {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 14px;
  align-items: center;
  padding: 10px 4px;
}
.flow li:not(:last-child) {
  border-bottom: 1px solid var(--color-line-subtle);
}
.flow-no {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-paper-deep);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-accent);
  letter-spacing: 0;
}
.flow-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.flow-text strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.flow-text span {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 20px; }
  .stat-value { font-size: 28px; }
  .day-value { font-size: 32px; }
  .day-grid, .ship-grid { grid-template-columns: 1fr; }
  .rule-text { grid-template-columns: 1fr; gap: 6px; }
  .rule-strong { font-size: 18px; }
}
</style>
