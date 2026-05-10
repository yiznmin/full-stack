<script setup lang="ts">
// /about-pbn — 什麼是數字油畫
// 對應 docs/yii_mui_static_pages_spec.md 第一頁
// 用 yiimui walnut paper 視覺；4-step + 氛圍區 + CTA
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { Package, Hash, Brush, Frame } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('什麼是數字油畫｜易木 YIIMUI')

const STEPS = [
  { no: '01', title: '打開 kit', body: '畫布、顏料、畫筆、色號表，一次到齊。', Icon: Package },
  { no: '02', title: '沿著色號', body: '畫布上每個區塊都有對應的數字。', Icon: Hash },
  { no: '03', title: '一筆一筆', body: '不用思考，慢慢上色就好。', Icon: Brush },
  { no: '04', title: '掛起來', body: '完成的那一刻，它就屬於你了。', Icon: Frame },
]
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="00"
      chapter="What is PBN"
      title="一個人、一杯茶、一下午，一幅屬於你的畫"
      caption="What is Paint by Number"
    />

    <p class="lede">
      數字油畫 kit 把畫畫拆解成「對應數字、塗上顏色」<br />
      讓沒接觸過畫畫的你，也能完成一幅可以掛起來的作品。
    </p>

    <!-- 4 step -->
    <section class="steps-section">
      <div class="section-rule">
        <span class="rule-aux">how it works</span>
        <span class="rule-line"></span>
      </div>
      <h2 class="section-title">四個步驟，慢慢來就好</h2>

      <div class="steps">
        <div v-for="s in STEPS" :key="s.no" class="step">
          <div class="step-icon-wrap">
            <component :is="s.Icon" :size="32" class="step-icon" />
          </div>
          <span class="step-no">STEP {{ s.no }}</span>
          <h3 class="step-title">{{ s.title }}</h3>
          <p class="step-body">{{ s.body }}</p>
        </div>
      </div>
    </section>

    <!-- 療癒氛圍區 -->
    <section class="vibe">
      <blockquote class="vibe-text">
        一個週末。<br />
        一首喜歡的歌。<br />
        一杯咖啡。<br />
        一幅慢慢誕生的畫。
        <footer class="vibe-foot">這就是易木 YIIMUI 想送你的下午。</footer>
      </blockquote>
    </section>

    <!-- CTA -->
    <section class="cta">
      <h2 class="cta-title">準備好了嗎？</h2>
      <div class="cta-grid">
        <RouterLink to="/products" class="cta-card">
          <span class="cta-card-eyebrow">現成款</span>
          <span class="cta-card-title">選一幅你喜歡的<br />立刻開始</span>
          <span class="cta-card-arrow">看現成款 →</span>
        </RouterLink>
        <RouterLink to="/custom" class="cta-card">
          <span class="cta-card-eyebrow">客製服務</span>
          <span class="cta-card-title">把照片變成畫<br />專屬於你</span>
          <span class="cta-card-arrow">聊客製 →</span>
        </RouterLink>
      </div>
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

/* Section header rule */
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
.rule-line {
  flex: 1;
  height: 1px;
  background: var(--color-line-subtle);
}

.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 26px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 48px;
}

/* Steps */
.steps-section { margin-bottom: 96px; }
.steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 32px;
}
.step {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.step-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  color: var(--color-accent);
}
.step-icon {
  stroke: currentColor;
  stroke-width: 1.25;
  fill: none;
}
.step-no {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  color: var(--color-fresh);
  font-weight: 500;
  margin-bottom: 8px;
}
.step-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.step-body {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  line-height: 1.8;
  letter-spacing: 0.02em;
  color: var(--color-ink-muted);
  margin: 0;
}

/* Vibe quote */
.vibe {
  margin: 0 0 96px;
  padding: 64px 32px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-sm);
  text-align: center;
}
.vibe-text {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  line-height: 2.2;
  letter-spacing: 0.08em;
  color: var(--color-ink-default);
  margin: 0;
  border: none;
  padding: 0;
}
.vibe-foot {
  display: block;
  margin-top: 32px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 500;
}

/* CTA */
.cta-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 24px;
  text-align: center;
}
.cta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.cta-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 32px 28px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  text-decoration: none;
  color: inherit;
  text-align: center;
  transition: border-color 150ms, background 150ms, transform 200ms ease;
}
.cta-card:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  transform: translateY(-1px);
}
.cta-card-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.cta-card-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.06em;
  line-height: 1.7;
  color: var(--color-ink-strong);
}
.cta-card-arrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-top: 4px;
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
  .steps { grid-template-columns: repeat(2, 1fr); gap: 40px 24px; }
  .vibe { padding: 48px 24px; }
  .cta-grid { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 22px; margin-bottom: 36px; }
  .vibe-text { font-size: 16px; }
}
</style>
