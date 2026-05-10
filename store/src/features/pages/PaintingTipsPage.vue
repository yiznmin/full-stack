<script setup lang="ts">
// /painting-tips — 新手教學
// 對應 docs/yii_mui_static_pages_spec.md 第六頁
// 4 技巧 + 5 Q&A + 雙 CTA
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { Layers, Lock, Repeat, Droplet } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('新手教學｜易木 YIIMUI')

const TIPS = [
  {
    Icon: Layers,
    title: '從大色塊開始畫，留小細節最後',
    body: '這樣不容易卡關，也比較有成就感。',
  },
  {
    Icon: Lock,
    title: '顏料用完蓋緊，不會乾',
    body: '蓋緊就好，不需要冰起來。',
  },
  {
    Icon: Repeat,
    title: '塗超出邊線？等乾了再用旁邊顏色蓋',
    body: '數字油畫的顏料是壓克力顏料，可以多次覆蓋。',
  },
  {
    Icon: Droplet,
    title: '換顏色時，畫筆用清水沖一下',
    body: '不用洗很乾淨，沖一下就好。',
  },
]

const FAQS = [
  { q: '我可以中途停下來嗎？', a: '可以。蓋上顏料、收好就好。下次接著畫。' },
  { q: '一定要按照數字順序畫嗎？', a: '不用。建議從大色塊開始，最後處理細節。' },
  { q: '顏料會不會不夠？', a: '我們會多附 10–15% 的份量，正常使用都會夠。' },
  { q: '塗錯了怎麼辦？', a: '等顏料乾，用旁邊正確的顏色蓋掉就好。' },
  { q: '大概要畫多久？', a: '看尺寸與細緻度。小尺寸約半天到一天、中尺寸約 3–7 天、大尺寸約 1–3 週。' },
]
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="00"
      chapter="Painting Tips"
      title="第一次拿起畫筆，會緊張一下下，沒關係"
      caption="Beginner's Guide"
    />

    <p class="lede">
      顏料怎麼用、塗錯怎麼辦、要花多久 ——<br />
      這頁是寫給第一次畫的你的小提醒。
    </p>

    <!-- 4 tips -->
    <section class="section">
      <h2 class="section-title">畫得順利的小技巧</h2>
      <ul class="tips-list">
        <li v-for="(t, idx) in TIPS" :key="idx" class="tip">
          <div class="tip-icon-wrap">
            <component :is="t.Icon" :size="22" class="tip-icon" />
          </div>
          <div class="tip-text">
            <h3 class="tip-title">{{ t.title }}</h3>
            <p class="tip-body">{{ t.body }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- 5 FAQs -->
    <section class="section">
      <h2 class="section-title">你可能會想問</h2>
      <ul class="qa-list">
        <li v-for="(f, idx) in FAQS" :key="idx" class="qa">
          <div class="qa-q">
            <span class="qa-q-mark">Q{{ idx + 1 }}</span>
            <span class="qa-q-text">{{ f.q }}</span>
          </div>
          <p class="qa-a">{{ f.a }}</p>
        </li>
      </ul>
    </section>

    <!-- Dual CTA -->
    <section class="cta">
      <RouterLink to="/products" class="cta-btn">準備好了，去看看現成款 →</RouterLink>
      <RouterLink to="/faq" class="cta-btn cta-btn-ghost">還有問題？看 FAQ →</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 8px 0 64px;
}

.section { margin-bottom: 72px; }

.section-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 28px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}

/* Tips */
.tips-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.tip {
  display: flex;
  gap: 18px;
  padding: 22px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.tip-icon-wrap {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
}
.tip-icon { stroke: currentColor; stroke-width: 1.5; fill: none; }
.tip-text { flex: 1; min-width: 0; }
.tip-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 6px;
  line-height: 1.5;
}
.tip-body {
  font-size: 13px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
  margin: 0;
}

/* QA */
.qa-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.qa { padding: 0 0 24px; border-bottom: 1px solid var(--color-line-subtle); }
.qa:last-child { border-bottom: none; padding-bottom: 0; }
.qa-q {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}
.qa-q-mark {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 16px;
  color: var(--color-accent);
  font-weight: 400;
  flex-shrink: 0;
}
.qa-q-text {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  line-height: 1.5;
}
.qa-a {
  margin: 0 0 0 28px;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
}

/* CTA */
.cta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 32px;
}
.cta-btn {
  display: inline-flex;
  align-items: center;
  padding: 14px 28px;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 1px solid var(--color-ink-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background 150ms, border-color 150ms, color 150ms;
}
.cta-btn:hover { background: var(--color-accent-deep); border-color: var(--color-accent-deep); }
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

@media (max-width: 1023px) { .page { padding: 48px 32px 72px; } }
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 19px; }
  .tip { padding: 18px 18px; gap: 14px; }
  .tip-icon-wrap { width: 40px; height: 40px; }
}
</style>
