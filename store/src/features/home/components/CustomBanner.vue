<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="wrap">
    <div class="banner">
      <div class="text">
        <div class="eyebrow">Custom — 客製照片</div>
        <h2 class="title">把你最珍惜的那張照片，<br>變成一幅親手畫的畫。</h2>
        <p class="desc">
          上傳照片、告訴我們想要的尺寸，我們手工調色、出樣稿給你看。<br>
          確認後再付款開始製作 — 從報價到送到家，平均 14 個工作天。
        </p>
        <RouterLink to="/custom" class="cta">上傳照片開始 →</RouterLink>
      </div>
      <div class="visual" />
    </div>
  </section>
</template>

<style scoped>
.wrap {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px 56px;
}

.banner {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 96px 80px;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 80px;
  align-items: center;
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-bottom: 24px;
}

.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 42px;
  line-height: 1.45;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 32px;
}

.desc {
  font-size: 14px;
  line-height: 2;
  color: var(--color-ink-default);
  margin: 0 0 40px;
  max-width: 520px;
  letter-spacing: 0.04em;
}

.cta {
  display: inline-block;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  padding: 16px 32px;
  border: 1px solid var(--color-ink-strong);
  color: var(--color-ink-strong);
  text-decoration: none;
  transition: all 200ms;
}
.cta:hover {
  background: var(--color-paper-deep);
}

.visual {
  aspect-ratio: 1;
  background: linear-gradient(
    135deg,
    var(--color-paper-deep) 0%,
    var(--color-accent-soft) 60%,
    var(--color-accent) 100%
  );
  opacity: 0.5;
}

@media (max-width: 1023px) {
  .wrap { padding: 24px 32px; }
  .banner { padding: 64px 40px; gap: 48px; grid-template-columns: 1fr 240px; }
  .title { font-size: 32px; }
}
@media (max-width: 767px) {
  .wrap { padding: 16px 24px; }
  .banner { padding: 48px 24px; grid-template-columns: 1fr; gap: 32px; }
  .title { font-size: 26px; }
  .visual { aspect-ratio: 16 / 9; }
}
</style>
