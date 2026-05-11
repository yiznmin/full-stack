<script setup lang="ts">
// /refund-policy — 退換貨政策
// 對應 docs/yii_mui_static_pages_spec.md 第五頁
// 自訂元件：✓/✗ 對照清單、現成款 vs 客製款 兩段、確認製作分水嶺 callout、聯絡方式
import { useTitle } from '@vueuse/core'
import { Check, X, Mail, Instagram, MessageCircle } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('退換貨政策｜易木 YIIMUI')

interface Rule { ok: boolean; title: string; desc?: string }

const STANDARD_RULES: Rule[] = [
  {
    ok: true,
    title: '未拆封 7 天內可退貨',
    desc: '運費自負；商品需保持原始狀態與外包裝完整。',
  },
  {
    ok: true,
    title: '瑕疵品 7 天內反映可換貨',
    desc: '運費由易木 YIIMUI 負擔；請拍照留存證明。',
  },
  {
    ok: false,
    title: '已拆封不可退',
    desc: '顏料、畫布拆封後無法復原，請務必確認再開封。',
  },
  {
    ok: false,
    title: '「畫起來不像」不適用退換貨',
    desc: '畫面成果與個人技巧、上色狀況有關，恕不視為瑕疵。',
  },
]

const CUSTOM_RULES: Rule[] = [
  {
    ok: true,
    title: '按下「確認製作」之前可全額退款',
    desc: '報價確認前都還有彈性，請放心討論。',
  },
  {
    ok: true,
    title: '線稿不滿意，最多可修改 3 次',
    desc: '每次修改我們會根據你的回饋調整，直到你滿意為止。',
  },
  {
    ok: true,
    title: '瑕疵品 7 天內反映，可重新印製',
    desc: '請拍照留存證明，我們會儘快處理。',
  },
  {
    ok: false,
    title: '按下「確認製作」之後不可退換',
    desc: '已進入印製階段，材料已配置、無法復原。',
  },
  {
    ok: false,
    title: '「畫起來不像」不適用退換貨',
    desc: '畫面成果取決於上色技巧，與線稿品質無關。',
  },
  {
    ok: false,
    title: '客人提供照片不適合導致的不滿不適用',
    desc: '我們會在報價前主動說明照片限制，請務必詳閱。',
  },
]

const FLOW_STEPS = [
  { no: '1', title: '客戶申請退款', desc: '訂單詳情頁站內訊息 / Email / IG 私訊' },
  { no: '2', title: '管理員審核', desc: '標記訂單為「退款處理中」' },
  { no: '3', title: '5 個工作天內匯回', desc: '匯回您下單時提供的銀行帳戶' },
  { no: '4', title: '確認收到退款', desc: '在訂單頁點「我已收到退款」協助關單' },
]
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="05"
      chapter="Policy"
      title="收到後，如果有狀況"
      caption="Refund & Return"
    />

    <p class="lede">
      為了讓每一份 kit 都能順利送達，<br />
      退換貨的規則寫得有點清楚 — 但我相信你會理解。
    </p>

    <!-- 01 現成款 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">01</span>
        <h2 class="section-title">現成款 退換貨</h2>
      </header>

      <ul class="rules">
        <li
          v-for="r in STANDARD_RULES"
          :key="r.title"
          :class="['rule', r.ok ? 'rule-ok' : 'rule-no']"
        >
          <span :class="['rule-mark', r.ok ? 'mark-ok' : 'mark-no']">
            <Check v-if="r.ok" :size="13" :stroke-width="2.5" />
            <X v-else :size="13" :stroke-width="2.5" />
          </span>
          <div class="rule-text">
            <span class="rule-title">{{ r.title }}</span>
            <span v-if="r.desc" class="rule-desc">{{ r.desc }}</span>
          </div>
        </li>
      </ul>
    </section>

    <!-- 02 客製款 -->
    <section class="section">
      <header class="section-head">
        <span class="section-no">02</span>
        <h2 class="section-title">客製款 退換貨</h2>
      </header>

      <ul class="rules">
        <li
          v-for="r in CUSTOM_RULES"
          :key="r.title"
          :class="['rule', r.ok ? 'rule-ok' : 'rule-no']"
        >
          <span :class="['rule-mark', r.ok ? 'mark-ok' : 'mark-no']">
            <Check v-if="r.ok" :size="13" :stroke-width="2.5" />
            <X v-else :size="13" :stroke-width="2.5" />
          </span>
          <div class="rule-text">
            <span class="rule-title">{{ r.title }}</span>
            <span v-if="r.desc" class="rule-desc">{{ r.desc }}</span>
          </div>
        </li>
      </ul>

      <!-- 確認製作分水嶺 callout -->
      <aside class="watershed">
        <span class="watershed-tag">分水嶺</span>
        <h3 class="watershed-title">「確認製作」按鈕是客製流程的分水嶺</h3>
        <p>
          按下之前，所有討論都可以重來；按下之後，印製就會開始。<br />
          我希望你按下那一刻，是真的滿意了。
        </p>
      </aside>
    </section>

    <!-- 03 退款流程 -->
    <section class="section">
      <header class="section-head section-head-simple">
        <h2 class="section-title-sm">退款流程</h2>
      </header>

      <ol class="flow">
        <li v-for="s in FLOW_STEPS" :key="s.no">
          <span class="flow-no">{{ s.no }}</span>
          <div class="flow-text">
            <strong>{{ s.title }}</strong>
            <span>{{ s.desc }}</span>
          </div>
        </li>
      </ol>

      <p class="hint">
        退款處理中可在「我的訂單 → 退款」分頁追蹤狀態。
      </p>
    </section>

    <!-- 04 聯絡方式 -->
    <section class="section">
      <header class="section-head section-head-simple">
        <h2 class="section-title-sm">怎麼聯絡我們</h2>
      </header>

      <p class="contact-lede">
        瑕疵品、退換貨請透過以下方式聯絡，我們會在 <strong>24 小時</strong>內回覆你。
      </p>

      <ul class="contact-list">
        <li>
          <div class="contact-row">
            <MessageCircle :size="18" class="contact-icon" />
            <div class="contact-text">
              <strong>訂單站內訊息</strong>
              <span>登入後在訂單詳情頁送出；最快回覆</span>
            </div>
          </div>
        </li>
        <li>
          <a href="mailto:contact@yiimui.com" class="contact-row contact-row-link">
            <Mail :size="18" class="contact-icon" />
            <div class="contact-text">
              <strong>contact@yiimui.com</strong>
              <span>Email 寄信（主要聯絡管道）</span>
            </div>
            <span class="contact-arrow">→</span>
          </a>
        </li>
        <li>
          <a href="mailto:yiimui.studio@gmail.com" class="contact-row contact-row-link">
            <Mail :size="18" class="contact-icon" />
            <div class="contact-text">
              <strong>yiimui.studio@gmail.com</strong>
              <span>緊急聯絡（系統異常或主信箱無回時的備用管道）</span>
            </div>
            <span class="contact-arrow">→</span>
          </a>
        </li>
        <li>
          <a href="https://instagram.com/yiimui" target="_blank" rel="noopener noreferrer" class="contact-row contact-row-link">
            <Instagram :size="18" class="contact-icon" />
            <div class="contact-text">
              <strong>@yiimui</strong>
              <span>Instagram 私訊</span>
            </div>
            <span class="contact-arrow">→</span>
          </a>
        </li>
      </ul>
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
  margin-bottom: 28px;
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

/* Rules ✓/✗ */
.rules {
  list-style: none;
  padding: 0;
  margin: 0 0 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rule {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 20px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--color-line-subtle);
}
.rule-ok {
  background: rgba(127, 159, 121, 0.06);
  border-color: rgba(127, 159, 121, 0.2);
}
.rule-no {
  background: var(--color-paper-canvas);
  border-color: var(--color-line);
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
  margin-top: 1px;
}
.rule-mark :deep(svg) { stroke: currentColor; fill: none; }
.mark-ok { background: var(--color-fresh); }
.mark-no {
  background: transparent;
  color: var(--color-ink-default);
  border: 1.5px solid var(--color-ink-default);
}

.rule-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.rule-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  line-height: 1.6;
  color: var(--color-ink-strong);
}
.rule-no .rule-title { color: var(--color-ink-default); }
.rule-desc {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}

/* Watershed callout (確認製作分水嶺) */
.watershed {
  margin: 24px 0 0;
  padding: 24px 28px;
  background: linear-gradient(135deg, var(--color-accent-tint) 0%, var(--color-paper-deep) 100%);
  border: 1px solid var(--color-accent-soft);
  border-radius: var(--radius-xs);
  position: relative;
}
.watershed-tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 500;
  margin-bottom: 10px;
  padding: 3px 10px;
  border: 1px solid var(--color-accent);
  border-radius: 999px;
  background: var(--color-paper-canvas);
}
.watershed-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 17px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 10px;
  line-height: 1.5;
}
.watershed p {
  margin: 0;
  font-size: 13px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}

/* Flow */
.flow {
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.flow li {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 14px;
  align-items: center;
  padding: 12px 4px;
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
.hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}

/* Contact */
.contact-lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0 0 20px;
}
.contact-lede strong {
  font-weight: 500;
  color: var(--color-accent);
}

.contact-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.contact-row {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  padding: 16px 20px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  text-decoration: none;
  color: inherit;
}
.contact-row-link {
  cursor: pointer;
  transition: border-color 150ms, background 150ms;
}
.contact-row-link:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.contact-icon {
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
}
.contact-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.contact-text strong {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.contact-text span {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.contact-arrow {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-accent);
}

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .section-title { font-size: 20px; }
  .rule { padding: 14px 16px; }
  .watershed { padding: 20px 22px; }
  .watershed-title { font-size: 15px; }
  .flow li { grid-template-columns: 32px 1fr; }
}
</style>
