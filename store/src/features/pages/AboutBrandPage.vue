<script setup lang="ts">
// /about — 關於易木 YIIMUI
// 對應 docs/yii_mui_static_pages_spec.md 第八頁
// brand statement + 3 主張 + CTA
// 設計：hero 大字 statement + 編號豎排 pillar + 巨型 pull quote + 結語 + CTA
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { Hourglass, Leaf, Sparkles, Instagram } from 'lucide-vue-next'

useTitle('關於易木 YIIMUI｜我們是誰')

const PILLARS = [
  {
    no: '01',
    aux: 'slow living',
    Icon: Hourglass,
    title: '慢的選擇',
    question: '為什麼選擇「讓你自己畫」？',
    body: [
      '因為現在這個時代，什麼都太快了。',
      '訂餐 30 分鐘到、影片開 2 倍速、新聞 5 秒滑過。我們有太多東西可以「直接買」，但越來越少時間「親手做」。',
      '我們想留給你一段「不能加速的時間」 —— 顏料乾燥需要它的時間，你的手需要它的節奏，一筆一筆，沒有快進鍵。',
    ],
    pull: '完成的那一刻，你會發現：你買到的不是畫，是這幾個小時的自己。',
  },
  {
    no: '02',
    aux: 'sustainable packaging',
    Icon: Leaf,
    title: '包裝的選擇',
    question: '為什麼用減塑包裝？',
    body: [
      '一份送給自己的禮物，不應該開封的瞬間就製造垃圾。',
      '我們的每一份 kit 使用：可分解塑膠袋（取代一般 PE 袋）、牛皮紙膠帶（取代膠帶）、紙盒包裝（取代泡棉、塑膠盒）。',
      '成本會高一些，但這是我們想給你的小儀式。',
    ],
    pull: '拆開的瞬間，什麼都不需要丟。',
  },
  {
    no: '03',
    aux: 'aesthetic choice',
    Icon: Sparkles,
    title: '美的選擇',
    question: '為什麼是這個視覺、這個調性？',
    body: [
      '大部分數字油畫是給孩子的玩具：大眼睛、粉色臉頰、卡通感。',
      '但畫畫不只是孩子的事。30 歲的你也想要在週末有個療癒的儀式，也想要一幅「掛在客廳不會違和」的畫。',
      '我們選了「日系編輯誌」風格 —— 米白紙感、木質暖棕、天然顏料色。柔和、有溫度、有故事感，但不幼稚。',
    ],
    pull: '長大不是放棄美好，是換一種方式擁有它。',
  },
]
</script>

<template>
  <main class="page">
    <!-- Hero brand statement -->
    <header class="hero">
      <div class="hero-rule">
        <span class="hero-no">No. 00</span>
        <span class="hero-dot"></span>
        <span class="hero-cap">About</span>
        <span class="hero-line"></span>
      </div>

      <h1 class="hero-title">
        <span class="hero-mark">易木</span>
        <span class="hero-mark hero-mark-en">YIIMUI</span>
      </h1>

      <p class="hero-statement">
        是一份慢慢給你的<em>禮物</em>
      </p>

      <p class="hero-sub">
        不是賣顏料，是賣一個下午；<br />
        不是賣畫，是賣一段慢慢誕生的時光。
      </p>
    </header>

    <!-- 3 Pillars -->
    <section v-for="p in PILLARS" :key="p.no" class="pillar">
      <aside class="pillar-mark">
        <span class="pillar-no">{{ p.no }}</span>
        <span class="pillar-no-divider"></span>
        <span class="pillar-aux">{{ p.aux }}</span>
        <component :is="p.Icon" :size="24" class="pillar-icon" />
      </aside>

      <div class="pillar-content">
        <h2 class="pillar-title">{{ p.title }}</h2>
        <h3 class="pillar-question">{{ p.question }}</h3>

        <div class="pillar-body">
          <p v-for="(line, idx) in p.body" :key="idx">{{ line }}</p>
        </div>

        <blockquote class="pillar-pull">
          <span class="pull-quote">&ldquo;</span>
          <span class="pull-text">{{ p.pull }}</span>
        </blockquote>
      </div>
    </section>

    <!-- 結語 -->
    <section class="closing">
      <div class="closing-rule">
        <span class="closing-rule-line"></span>
        <span class="closing-rule-mark">crafted slowly</span>
        <span class="closing-rule-line"></span>
      </div>

      <p class="closing-text">
        易木 YIIMUI 是一個還在慢慢長大的品牌，<br />
        每一張線稿、每一份包裝、每一次客製，<br />
        都希望你感受到一點點<em>被在乎的痕跡</em>。
      </p>

      <p class="closing-hint">歡迎你跟著我們一起，慢慢來。</p>

      <div class="closing-cta">
        <RouterLink to="/products" class="cta-btn">開始逛逛 →</RouterLink>
        <a
          href="https://instagram.com/yiimui"
          target="_blank"
          rel="noopener noreferrer"
          class="cta-btn cta-btn-ghost"
        >
          <Instagram :size="14" :stroke-width="1.5" />
          <span>在 IG 找到我們</span>
        </a>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 800px;
  margin: 0 auto;
  padding: 80px 56px 120px;
}

/* ── Hero ────────────────────────────────────────────── */
.hero {
  text-align: center;
  margin-bottom: 120px;
}
.hero-rule {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 32px;
}
.hero-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.hero-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-accent);
}
.hero-cap {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
}
.hero-line {
  width: 60px;
  height: 1px;
  background: var(--color-line);
}

.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  margin: 0 0 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  line-height: 1;
}
.hero-mark {
  font-size: 64px;
  letter-spacing: 0.14em;
  color: var(--color-ink-strong);
  line-height: 1;
}
.hero-mark-en {
  font-family: var(--font-display);
  font-weight: 300;
  font-size: 32px;
  letter-spacing: 0.32em;
  color: var(--color-accent);
}

.hero-statement {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.08em;
  color: var(--color-ink-default);
  margin: 0 0 32px;
  line-height: 1.7;
}
.hero-statement em {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  margin: 0 0.04em;
}

.hero-sub {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  line-height: 2;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
  margin: 0;
  max-width: 460px;
  margin-left: auto;
  margin-right: auto;
}

/* ── Pillar ────────────────────────────────────────── */
.pillar {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 48px;
  margin-bottom: 96px;
  padding-bottom: 96px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.pillar:last-of-type { border-bottom: none; }

.pillar-mark {
  position: sticky;
  top: 100px;
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  padding-top: 6px;
}
.pillar-no {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 64px;
  color: var(--color-accent);
  line-height: 0.9;
}
.pillar-no-divider {
  width: 28px;
  height: 1px;
  background: var(--color-line);
}
.pillar-aux {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.pillar-icon {
  stroke: var(--color-ink-muted);
  stroke-width: 1.25;
  fill: none;
  margin-top: 8px;
  opacity: 0.6;
}

.pillar-content { min-width: 0; }

.pillar-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 30px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0 0 6px;
  line-height: 1.3;
}

.pillar-question {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
  margin: 0 0 28px;
}

.pillar-body { margin-bottom: 32px; }
.pillar-body p {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  line-height: 2.2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 0 0 18px;
}
.pillar-body p:last-child { margin-bottom: 0; }

/* Pull quote — 大字、置中、開引號裝飾 */
.pillar-pull {
  margin: 0;
  padding: 32px 32px 28px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
  position: relative;
  text-align: center;
}
.pull-quote {
  display: block;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 56px;
  color: var(--color-accent);
  line-height: 0.6;
  margin-bottom: 12px;
  opacity: 0.4;
}
.pull-text {
  display: block;
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 18px;
  line-height: 1.95;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}

/* ── Closing ────────────────────────────────────────── */
.closing {
  text-align: center;
  margin-top: 64px;
}
.closing-rule {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 36px;
}
.closing-rule-line {
  width: 60px;
  height: 1px;
  background: var(--color-line);
}
.closing-rule-mark {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.12em;
  color: var(--color-accent);
}

.closing-text {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 17px;
  line-height: 2.2;
  letter-spacing: 0.06em;
  color: var(--color-ink-default);
  margin: 0 0 16px;
}
.closing-text em {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  margin: 0 0.04em;
}

.closing-hint {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin: 0 0 48px;
}

.closing-cta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 32px;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 1px solid var(--color-ink-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background 150ms, border-color 150ms, color 150ms;
}
.cta-btn:hover { background: var(--color-accent-deep); border-color: var(--color-accent-deep); }
.cta-btn :deep(svg) { stroke: currentColor; fill: none; }
.cta-btn-ghost {
  background: transparent;
  color: var(--color-ink-default);
  border-color: var(--color-line);
}
.cta-btn-ghost:hover {
  background: var(--color-paper-deep);
  color: var(--color-accent);
  border-color: var(--color-accent);
}

@media (max-width: 1023px) {
  .page { padding: 56px 32px 80px; }
  .hero-mark { font-size: 48px; }
  .hero-mark-en { font-size: 24px; }
  .hero-statement { font-size: 19px; }
  .pillar { grid-template-columns: 100px 1fr; gap: 32px; }
  .pillar-no { font-size: 48px; }
  .pillar-title { font-size: 26px; }
  .pillar-mark { position: static; }
}
@media (max-width: 767px) {
  .page { padding: 40px 24px 64px; }
  .hero { margin-bottom: 80px; }
  .hero-mark { font-size: 40px; }
  .hero-mark-en { font-size: 20px; }
  .hero-statement { font-size: 17px; }
  .pillar {
    grid-template-columns: 1fr;
    gap: 20px;
    margin-bottom: 64px;
    padding-bottom: 64px;
  }
  .pillar-mark {
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }
  .pillar-no { font-size: 36px; }
  .pillar-no-divider { width: 14px; }
  .pillar-icon { display: none; }
  .pillar-title { font-size: 22px; }
  .pull-text { font-size: 16px; }
  .pull-quote { font-size: 40px; }
}
</style>
