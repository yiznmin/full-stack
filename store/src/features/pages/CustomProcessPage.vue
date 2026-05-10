<script setup lang="ts">
// /custom-process — 訂製流程
// 對應 docs/yii_mui_static_pages_spec.md 第二頁
// 改為自訂元件（不走 markdown）— 4 step 用垂直 timeline 呈現順序感
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { Check, X, Upload, Wand2, MessageSquareCheck, Package } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('訂製流程｜易木 YIIMUI')

const STEPS = [
  {
    no: '01',
    title: '選尺寸 + 上傳照片',
    body: '選擇你想要的畫布尺寸，上傳一張對你有意義的照片。',
    Icon: Upload,
  },
  {
    no: '02',
    title: '我們幫你轉成線稿',
    body: '1–2 個工作天內，我們會把照片轉成可以畫的線稿並完成報價。',
    Icon: Wand2,
  },
  {
    no: '03',
    title: '你確認、可微調',
    body: '你會看到線稿與報價，可以微調最多 3 次，直到你滿意。',
    Icon: MessageSquareCheck,
  },
  {
    no: '04',
    title: '印製寄出',
    body: '你按下「確認製作」，我們開始印製、配料、寄出。',
    Icon: Package,
  },
]

const PHOTO_OK = [
  { title: '主體清楚', desc: '人 / 寵物 / 物件佔畫面 1/2 以上' },
  { title: '光線充足', desc: '自然光最好' },
  { title: '解析度夠', desc: '手機原檔即可' },
  { title: '背景單純', desc: '純色牆、單色布料最佳' },
]
const PHOTO_NO = [
  { title: '逆光、背光', desc: '看不清主體' },
  { title: '過度模糊或晃動', desc: '線稿無法清楚還原' },
  { title: '低解析度截圖', desc: '社群縮圖、轉發圖' },
  { title: '過度複雜的背景', desc: '雜物多、視覺擁擠' },
]
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="03"
      chapter="Bespoke"
      title="有些照片，值得花一點時間慢慢畫"
      caption="How Custom Works"
    />

    <p class="lede">
      你不用會畫畫。把那張對你有意義的照片交給我們，<br />
      把它變成可以親手完成的畫。
    </p>

    <!-- 4-step timeline -->
    <section class="section">
      <header class="section-rule">
        <span class="rule-aux">how custom works</span>
        <span class="rule-line"></span>
      </header>
      <h2 class="section-title">四個步驟，把照片變成畫</h2>

      <ol class="timeline">
        <li v-for="(s, idx) in STEPS" :key="s.no" class="t-step">
          <div class="t-rail">
            <div class="t-bullet">
              <component :is="s.Icon" :size="22" class="t-icon" />
            </div>
            <div v-if="idx < STEPS.length - 1" class="t-line"></div>
          </div>
          <div class="t-body">
            <span class="t-no">STEP {{ s.no }}</span>
            <h3 class="t-title">{{ s.title }}</h3>
            <p class="t-desc">{{ s.body }}</p>
          </div>
        </li>
      </ol>

      <aside class="callout">
        <strong>※ 按下「確認製作」後即進入印製階段，不可退換。</strong>
        確認前若有疑問，可以無限次討論。
      </aside>
    </section>

    <!-- 照片指南 -->
    <section class="section">
      <header class="section-rule">
        <span class="rule-aux">photo guide</span>
        <span class="rule-line"></span>
      </header>
      <h2 class="section-title">怎麼選一張適合的照片？</h2>

      <div class="photo-grid">
        <div class="photo-col photo-ok">
          <header class="photo-col-head">
            <span class="photo-mark photo-mark-ok"><Check :size="14" :stroke-width="2.5" /></span>
            <h3 class="photo-col-title">適合</h3>
          </header>
          <ul class="photo-list">
            <li v-for="p in PHOTO_OK" :key="p.title">
              <strong>{{ p.title }}</strong>
              <span>{{ p.desc }}</span>
            </li>
          </ul>
        </div>

        <div class="photo-col photo-no">
          <header class="photo-col-head">
            <span class="photo-mark photo-mark-no"><X :size="14" :stroke-width="2.5" /></span>
            <h3 class="photo-col-title">不適合</h3>
          </header>
          <ul class="photo-list">
            <li v-for="p in PHOTO_NO" :key="p.title">
              <strong>{{ p.title }}</strong>
              <span>{{ p.desc }}</span>
            </li>
          </ul>
        </div>
      </div>

      <p class="photo-note">
        不適合的照片我們會在報價前主動說明並建議調整方向。
      </p>
    </section>

    <!-- IP / 隱私 -->
    <section class="section section-light">
      <h2 class="section-title-sm">智慧財產權與隱私</h2>
      <ul class="rules-list">
        <li class="rule-ok">
          <span class="rule-mark"><Check :size="13" :stroke-width="2.5" /></span>
          <span><strong>你自己的照片</strong> — 寵物、家人、朋友、自己，都歡迎</span>
        </li>
        <li class="rule-no">
          <span class="rule-mark"><X :size="13" :stroke-width="2.5" /></span>
          <span><strong>公眾人物肖像</strong> — 明星、偶像、卡通角色、品牌商標，不接受</span>
        </li>
        <li class="rule-no">
          <span class="rule-mark"><X :size="13" :stroke-width="2.5" /></span>
          <span><strong>他人攝影作品</strong> — 未取得授權的網路圖片，不接受</span>
        </li>
      </ul>

      <p class="privacy-note">
        您上傳的照片會儲存在私密路徑，<strong>僅您與管理員可看見</strong>。
        完成的作品如要展示在公開「客製案例」中，會主動徵詢您的同意。
        客人可隨時要求刪除照片，刪除後本服務無法繼續。
      </p>
    </section>

    <!-- CTA -->
    <section class="cta">
      <RouterLink to="/custom/apply" class="cta-btn">立即上傳照片 →</RouterLink>
      <p class="cta-hint">看不到自己想客製的圖？私訊我們聊聊也可以。</p>
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

/* Timeline */
.timeline {
  list-style: none;
  padding: 0;
  margin: 0 0 32px;
}
.t-step {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 24px;
  position: relative;
}
.t-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}
.t-bullet {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
  flex-shrink: 0;
  z-index: 1;
}
.t-icon {
  stroke: currentColor;
  stroke-width: 1.5;
  fill: none;
}
.t-line {
  flex: 1;
  width: 1px;
  background: var(--color-line);
  margin-top: 4px;
  margin-bottom: 4px;
}
.t-body {
  padding: 4px 0 40px;
}
.t-step:last-child .t-body { padding-bottom: 0; }

.t-no {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
  margin-bottom: 6px;
}
.t-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 18px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
  line-height: 1.5;
}
.t-desc {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 0;
}

/* Callout (按下確認製作) */
.callout {
  margin-top: 24px;
  padding: 18px 22px;
  background: var(--color-paper-deep);
  border-left: 2px solid var(--color-accent);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
  font-size: 13px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}
.callout strong {
  display: block;
  margin-bottom: 4px;
  color: var(--color-ink-strong);
  font-weight: 500;
}

/* Photo guide */
.photo-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 16px;
}
.photo-col {
  padding: 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.photo-col-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.photo-col-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.photo-mark {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-paper-canvas);
}
.photo-mark :deep(svg) { stroke: currentColor; fill: none; }
.photo-mark-ok { background: var(--color-fresh); }
.photo-mark-no {
  background: transparent;
  color: var(--color-ink-default);
  border: 1.5px solid var(--color-ink-default);
}

.photo-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.photo-list li {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.photo-list strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.photo-list span {
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.photo-no .photo-list strong { color: var(--color-ink-default); }

.photo-note {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
  text-align: center;
}

/* Rules list (IP) */
.rules-list {
  list-style: none;
  padding: 0;
  margin: 0 0 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rules-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-xs);
  font-size: 13px;
  line-height: 1.7;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}
.rule-ok { background: rgba(127, 159, 121, 0.08); }
.rule-no {
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
}
.rule-mark {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-paper-canvas);
  flex-shrink: 0;
}
.rule-mark :deep(svg) { stroke: currentColor; fill: none; }
.rule-ok .rule-mark { background: var(--color-fresh); }
.rule-no .rule-mark {
  background: transparent;
  color: var(--color-ink-default);
  border: 1.5px solid var(--color-ink-default);
}
.rules-list strong { font-weight: 500; color: var(--color-ink-strong); }

.privacy-note {
  font-size: 13px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  margin: 0;
}
.privacy-note strong { font-weight: 500; color: var(--color-ink-strong); }

/* CTA */
.cta { text-align: center; margin-top: 24px; }
.cta-btn {
  display: inline-flex;
  align-items: center;
  padding: 16px 36px;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 1px solid var(--color-ink-strong);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background 150ms, border-color 150ms;
}
.cta-btn:hover { background: var(--color-accent-deep); border-color: var(--color-accent-deep); }
.cta-hint {
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
  .photo-grid { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 22px; margin-bottom: 36px; }
  .t-step { grid-template-columns: 48px 1fr; gap: 18px; }
  .t-bullet { width: 44px; height: 44px; }
  .t-body { padding-bottom: 32px; }
  .t-title { font-size: 16px; }
}
</style>
