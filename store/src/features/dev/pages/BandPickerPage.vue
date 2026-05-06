<script setup lang="ts">
// Dev-only — band 顏色挑選頁
// 給 user 看 8 個候選色號實際 render 在 band 上的效果

const CANDIDATES = [
  {
    hex: '#F4EAD0',
    name: 'A · Pale Sand',
    desc: '⚠️ user 反饋：太黃',
    cn: '淡米沙',
    ref: 'too-yellow',
  },
  // ↓ 5 個 in-between 候選 — 比 A 冷、比 B 亮 ↓
  {
    hex: '#F2E8D5',
    name: '①  Pearl Linen',
    desc: '比 A 略冷一點，亮度差不多',
    cn: '珍珠亞麻',
  },
  {
    hex: '#F1E7D2',
    name: '②  Soft Cream',
    desc: '中間偏亮，黃度中和',
    cn: '柔奶白',
  },
  {
    hex: '#F0E6D0',
    name: '③  Mid Linen',
    desc: '正中間（亮度與黃度都取中）',
    cn: '中亞麻',
  },
  {
    hex: '#F1E5CD',
    name: '④  Warm Cream',
    desc: '比 ③ 略暖一點點，偏奶油',
    cn: '暖奶白',
  },
  {
    hex: '#EFE5CF',
    name: '⑤  Pale Linen',
    desc: '比 B 亮但 hue 一致，最接近 B 的同調',
    cn: '淡亞麻',
  },
  {
    hex: '#EFE3CC',
    name: 'B · Soft Linen',
    desc: '⚠️ user 反饋：太暗',
    cn: '亞麻乳',
    ref: 'too-dark',
  },
]
</script>

<template>
  <main class="page">
    <header class="head">
      <span class="eyebrow">— Band Color Picker —</span>
      <h1 class="title">挑選 band 區塊顏色</h1>
      <p class="meta">
        canvas <code>#F4EFE2</code> · 目前 band <code>#EBDDC8</code><br />
        A 跟 B 是你之前嫌「太黃 / 太暗」的兩個（紅虛線標示）。<br />
        中間 ① ~ ⑤ 都比 A 冷、比 B 亮，找你對胃口的。
      </p>
    </header>

    <div class="bands">
      <article
        v-for="c in CANDIDATES"
        :key="c.hex"
        class="band-sample"
        :class="{
          'is-ref-yellow': c.ref === 'too-yellow',
          'is-ref-dark': c.ref === 'too-dark',
        }"
        :style="{ background: c.hex }"
      >
        <div class="content">
          <div class="rule-row">
            <span class="no">{{ c.hex }}</span>
            <span class="dot"></span>
            <span class="cap">{{ c.name }}</span>
            <span class="line"></span>
            <span v-if="c.current" class="badge">CURRENT</span>
          </div>
          <h2 class="band-title">
            依<em class="em">主題</em>挑選
          </h2>
          <p class="band-desc">{{ c.cn }} — {{ c.desc }}</p>
        </div>
      </article>
    </div>

    <footer class="foot">
      <p>選定後告訴我色號，我把 <code>--color-paper-deep</code> 換成它。</p>
    </footer>
  </main>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 56px 40px 96px;
}

.head { margin-bottom: 48px; }
.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
}
.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 36px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 12px 0 12px;
}
.meta {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
  margin: 0;
}
.meta code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
}

.bands {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.band-sample {
  position: relative;
  padding: 56px 56px 64px;
  border: 1px solid var(--color-line-subtle);
  transition: border-color 200ms;
}
.band-sample:hover {
  border-color: var(--color-line);
}
.is-ref-yellow,
.is-ref-dark {
  outline: 2px dashed var(--color-state-danger);
  outline-offset: -2px;
  opacity: 0.85;
}

.content { max-width: 720px; }

.rule-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.no {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--color-ink-strong);
  font-weight: 500;
}
.dot {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--color-accent);
}
.cap {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
}
.line {
  flex: 1;
  height: 1px;
  background: var(--color-accent-soft);
  opacity: 0.5;
  min-width: 40px;
}
.badge {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  border: 1px solid var(--color-fresh);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
}

.band-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 40px;
  line-height: 1.2;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0 0 14px;
}
.em {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  margin: 0 0.04em;
}

.band-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.85;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 0;
}

.foot {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
  font-size: 13px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}
.foot code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
}

@media (max-width: 767px) {
  .page { padding: 40px 24px 64px; }
  .band-sample { padding: 36px 24px 40px; }
  .band-title { font-size: 28px; }
}
</style>
