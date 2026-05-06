<script setup lang="ts">
// Dev-only — band 顏色挑選頁
// 給 user 看 8 個候選色號實際 render 在 band 上的效果

const CANDIDATES = [
  {
    hex: '#F4EAD0',
    name: 'Pale Sand',
    desc: '比 canvas 微暖一階，幾乎察覺不到，最克制',
    cn: '淡米沙',
  },
  {
    hex: '#EFE3CC',
    name: 'Soft Linen',
    desc: '輕微 linen 感，溫和分層',
    cn: '亞麻乳',
  },
  {
    hex: '#EBDDC8',
    name: 'Cream Peach（現在）',
    desc: '當前使用 — 淡桃米',
    cn: '奶油桃',
    current: true,
  },
  {
    hex: '#E8D5BC',
    name: 'Wheat',
    desc: '小麥色，溫暖但仍偏淺',
    cn: '麥色',
  },
  {
    hex: '#E0CDB0',
    name: 'Oat Beige',
    desc: '燕麥米，明確的「比 canvas 暗」',
    cn: '燕麥米',
  },
  {
    hex: '#D9C5A6',
    name: 'Light Camel',
    desc: '淺駝，比較有存在感（接近 line tone）',
    cn: '淺駝',
  },
  {
    hex: '#ECDED5',
    name: 'Dusty Rose Cream',
    desc: '帶點玫瑰粉的米，比較柔',
    cn: '玫瑰米',
  },
  {
    hex: '#E2DCC2',
    name: 'Sage Cream',
    desc: '帶點苔綠 hint 的米，呼應 fresh accent',
    cn: '苔米',
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
        以下 8 個候選都跟我們 v5 色票同色系，只是不同明度 / 暖度。
      </p>
    </header>

    <div class="bands">
      <article
        v-for="c in CANDIDATES"
        :key="c.hex"
        class="band-sample"
        :class="{ 'is-current': c.current }"
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
.is-current {
  outline: 2px solid var(--color-fresh);
  outline-offset: -2px;
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
