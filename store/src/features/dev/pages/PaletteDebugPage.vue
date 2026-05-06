<script setup lang="ts">
// Dev-only 色票總覽頁，看完整 design tokens
// 路由：/_palette

interface Swatch {
  token: string
  hex: string
  desc: string
  textOn?: 'dark' | 'light'
}

const paper: Swatch[] = [
  { token: '--color-paper-canvas', hex: '#F7F1E3', desc: '頁面底色（米白）' },
  { token: '--color-paper-surface', hex: '#F4EAD0', desc: '卡片表面（暖沙奶油）' },
  { token: '--color-paper-deep', hex: '#E5D9BC', desc: '較深背景（hero/fallback）' },
]

const ink: Swatch[] = [
  { token: '--color-ink-strong', hex: '#1F1A15', desc: '主文字（標題）', textOn: 'dark' },
  { token: '--color-ink-default', hex: '#3F362C', desc: '一般文字', textOn: 'dark' },
  { token: '--color-ink-muted', hex: '#7E7163', desc: '次要文字 / 標籤' },
  { token: '--color-ink-disabled', hex: '#BBB1A1', desc: '禁用狀態' },
]

const line: Swatch[] = [
  { token: '--color-line-subtle', hex: '#EBE2D0', desc: '極細 hairline' },
  { token: '--color-line', hex: '#C8B99F', desc: '一般邊線' },
]

const accent: Swatch[] = [
  { token: '--color-accent', hex: '#8C6E52', desc: '主 accent（taupe walnut）', textOn: 'dark' },
  { token: '--color-accent-deep', hex: '#5E4732', desc: 'hover / 深 accent', textOn: 'dark' },
  { token: '--color-accent-soft', hex: '#B8A084', desc: '較淺 accent' },
  { token: '--color-accent-tint', hex: '#ECE3D2', desc: 'tint / chip 底' },
]

const fresh: Swatch[] = [
  { token: '--color-fresh', hex: '#6B7F5C', desc: '苔綠（清新輔色 / Series eyebrow）', textOn: 'dark' },
  { token: '--color-fresh-soft', hex: '#97A687', desc: '苔綠 soft' },
  { token: '--color-fresh-tint', hex: '#DDE5D2', desc: 'success icon 底' },
]

const wine: Swatch[] = [
  { token: '--color-accent-wine', hex: '#7B2E40', desc: '酒紅（FEATURED chip / pop）', textOn: 'dark' },
  { token: '--color-accent-wine-soft', hex: '#A85D6C', desc: '酒紅 soft' },
]

const states: Swatch[] = [
  { token: '--color-state-success', hex: '#6B7F5C', desc: 'success', textOn: 'dark' },
  { token: '--color-state-warning', hex: '#B6924E', desc: 'warning' },
  { token: '--color-state-danger', hex: '#7B2E40', desc: 'danger', textOn: 'dark' },
  { token: '--color-state-info', hex: '#74819A', desc: 'info' },
]

const fonts = [
  { token: '--font-display', val: "'Cormorant Garamond', serif", sample: 'Yiimui Atelier · 易木' },
  { token: '--font-cn-serif', val: "'Noto Serif TC', serif", sample: '慢慢畫一幅，屬於自己的時光' },
  { token: '--font-body', val: "'Manrope', system-ui", sample: 'Sign in to your atelier · 親手畫的療癒' },
  { token: '--font-mono', val: "'JetBrains Mono'", sample: 'NT$ 1,180 · 2026/05/06' },
]
</script>

<template>
  <main class="page">
    <header class="head">
      <span class="eyebrow">— Design Tokens —</span>
      <h1 class="title">色票與字體總覽</h1>
      <p class="meta">store/src/style.css · 共 {{ paper.length + ink.length + line.length + accent.length + fresh.length + wine.length + states.length }} 個色 token</p>
    </header>

    <section class="group">
      <h2 class="group-title">Paper（紙張層級）</h2>
      <div class="swatches">
        <div v-for="s in paper" :key="s.token" class="swatch">
          <div class="chip" :style="{ background: s.hex }"></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Ink（文字色階）</h2>
      <div class="swatches">
        <div v-for="s in ink" :key="s.token" class="swatch">
          <div
            class="chip"
            :style="{ background: s.hex, color: s.textOn === 'dark' ? '#F7F1E3' : '#1F1A15' }"
          >Aa 易木</div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Line（邊線）</h2>
      <div class="swatches">
        <div v-for="s in line" :key="s.token" class="swatch">
          <div class="chip" :style="{ background: s.hex }"></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Accent — Taupe Walnut（主 accent）</h2>
      <div class="swatches">
        <div v-for="s in accent" :key="s.token" class="swatch">
          <div
            class="chip"
            :style="{ background: s.hex, color: s.textOn === 'dark' ? '#F7F1E3' : '#1F1A15' }"
          ></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Fresh — 苔綠（清新輔色）</h2>
      <div class="swatches">
        <div v-for="s in fresh" :key="s.token" class="swatch">
          <div
            class="chip"
            :style="{ background: s.hex, color: s.textOn === 'dark' ? '#F7F1E3' : '#1F1A15' }"
          ></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Wine — 酒紅（pop 點綴）</h2>
      <div class="swatches">
        <div v-for="s in wine" :key="s.token" class="swatch">
          <div
            class="chip"
            :style="{ background: s.hex, color: s.textOn === 'dark' ? '#F7F1E3' : '#1F1A15' }"
          ></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">States（狀態色）</h2>
      <div class="swatches">
        <div v-for="s in states" :key="s.token" class="swatch">
          <div
            class="chip"
            :style="{ background: s.hex, color: s.textOn === 'dark' ? '#F7F1E3' : '#1F1A15' }"
          ></div>
          <div class="info">
            <div class="hex">{{ s.hex }}</div>
            <div class="token">{{ s.token }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">Typography（字體）</h2>
      <div class="font-list">
        <div v-for="f in fonts" :key="f.token" class="font-row">
          <div class="font-meta">
            <div class="token">{{ f.token }}</div>
            <div class="desc">{{ f.val }}</div>
          </div>
          <div class="font-sample" :style="{ fontFamily: f.val }">
            {{ f.sample }}
          </div>
        </div>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">組合預覽 — Background × Card</h2>
      <div class="combo">
        <div class="combo-canvas">
          <div class="combo-card">
            <div class="combo-eyebrow">Sample</div>
            <div class="combo-title">登入</div>
            <div class="combo-rule"></div>
            <div class="combo-body">
              這是 canvas 上鋪一張 surface 卡片的視覺，加上 hairline 邊。
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 64px 40px 96px;
}

.head { margin-bottom: 56px; }
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
  margin: 12px 0 8px;
}
.meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
  margin: 0;
}

.group {
  margin-bottom: 56px;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
}
.group-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 24px;
}

.swatches {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.swatch {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  overflow: hidden;
}
.chip {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  letter-spacing: 0.04em;
}
.info {
  padding: 10px 14px 14px;
}
.hex {
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  font-weight: 500;
}
.token {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  margin: 4px 0;
  word-break: break-all;
}
.desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}

/* Typography */
.font-list { display: flex; flex-direction: column; gap: 16px; }
.font-row {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  align-items: center;
  padding: 16px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
}
.font-meta { display: flex; flex-direction: column; gap: 4px; }
.font-sample {
  font-size: 22px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
}

/* Combo */
.combo-canvas {
  background: var(--color-paper-canvas);
  border: 1px dashed var(--color-line);
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.combo-card {
  width: 100%;
  max-width: 360px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 32px;
  position: relative;
  box-shadow: 0 12px 32px -16px rgba(31, 26, 21, 0.08);
}
.combo-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--color-fresh), var(--color-accent-soft), var(--color-accent-wine-soft));
}
.combo-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
  margin-bottom: 12px;
}
.combo-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin-bottom: 16px;
}
.combo-rule {
  width: 32px;
  height: 1px;
  background: var(--color-accent);
  margin-bottom: 16px;
}
.combo-body {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
}

@media (max-width: 767px) {
  .page { padding: 40px 20px 64px; }
  .font-row { grid-template-columns: 1fr; }
}
</style>
