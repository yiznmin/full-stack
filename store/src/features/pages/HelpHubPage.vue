<script setup lang="ts">
// /help — 5 個資訊頁的集中入口（情境式分組）
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import { Ruler, Coins, Sparkles, Truck, ShieldCheck, BookOpen, Brush, MessageCircleQuestion, Heart } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('購物說明｜易木 YIIMUI')

interface InfoCard {
  to: string
  title: string
  desc: string
  Icon: typeof Ruler
}

const INTRO: InfoCard[] = [
  {
    to: '/about-pbn',
    title: '什麼是數字油畫',
    desc: '4 步驟說明、療癒氛圍、適合誰',
    Icon: BookOpen,
  },
  {
    to: '/painting-tips',
    title: '新手教學',
    desc: '4 個畫得順利的小技巧 + 5 個常見小疑問',
    Icon: Brush,
  },
]

const BUYING: InfoCard[] = [
  {
    to: '/size-guide',
    title: '尺寸指南',
    desc: '生活化對照、適合擺放、完整 16 種尺寸表',
    Icon: Ruler,
  },
  {
    to: '/pricing',
    title: '報價參考',
    desc: '客製化照片的尺寸 × 難度價格區間',
    Icon: Coins,
  },
]

const ORDER: InfoCard[] = [
  {
    to: '/custom-process',
    title: '訂製流程',
    desc: '從上傳照片到出貨的 4 個步驟 + 照片指南',
    Icon: Sparkles,
  },
  {
    to: '/shipping-info',
    title: '配送與付款',
    desc: '付款方式、製作天數、出貨方式、運費規則',
    Icon: Truck,
  },
  {
    to: '/refund-policy',
    title: '退換貨政策',
    desc: '現成款 vs 客製款規則、退款流程',
    Icon: ShieldCheck,
  },
]

const MORE: InfoCard[] = [
  {
    to: '/faq',
    title: '常見問題',
    desc: '15 個問題依「產品 / 下單 / 客製 / 配送」分類',
    Icon: MessageCircleQuestion,
  },
  {
    to: '/about',
    title: '關於易木 YIIMUI',
    desc: '慢生活、減塑包裝、視覺與調性的選擇',
    Icon: Heart,
  },
]

interface FaqItem {
  q: string
  to: string
}

const POPULAR_QUESTIONS: FaqItem[] = [
  { q: '我從來沒畫過，會不會太難？', to: '/faq' },
  { q: 'kit 裡面有什麼？需要再買畫框嗎？', to: '/faq' },
  { q: '結帳怎麼付款？', to: '/shipping-info' },
  { q: '客製多久收到？', to: '/custom-process' },
  { q: '線稿可以修改幾次？', to: '/custom-process' },
  { q: '客製商品可以退貨嗎？', to: '/refund-policy' },
]
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="00"
      chapter="Help"
      title="購物說明"
      caption="Reference & Policies"
    />

    <p class="lede">
      下面整理了購物前後最常被問的事 — 點下方卡片或常見問題，找到您要的答案。
    </p>

    <section class="group">
      <h2 class="group-title">先了解一下</h2>
      <div class="cards">
        <RouterLink
          v-for="c in INTRO"
          :key="c.to"
          :to="c.to"
          class="card"
        >
          <component :is="c.Icon" :size="22" class="card-icon" />
          <div class="card-text">
            <span class="card-title">{{ c.title }}</span>
            <span class="card-desc">{{ c.desc }}</span>
          </div>
          <span class="card-arrow">→</span>
        </RouterLink>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">買之前想知道</h2>
      <div class="cards">
        <RouterLink
          v-for="c in BUYING"
          :key="c.to"
          :to="c.to"
          class="card"
        >
          <component :is="c.Icon" :size="22" class="card-icon" />
          <div class="card-text">
            <span class="card-title">{{ c.title }}</span>
            <span class="card-desc">{{ c.desc }}</span>
          </div>
          <span class="card-arrow">→</span>
        </RouterLink>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">下單後</h2>
      <div class="cards">
        <RouterLink
          v-for="c in ORDER"
          :key="c.to"
          :to="c.to"
          class="card"
        >
          <component :is="c.Icon" :size="22" class="card-icon" />
          <div class="card-text">
            <span class="card-title">{{ c.title }}</span>
            <span class="card-desc">{{ c.desc }}</span>
          </div>
          <span class="card-arrow">→</span>
        </RouterLink>
      </div>
    </section>

    <section class="group">
      <h2 class="group-title">更深入</h2>
      <div class="cards">
        <RouterLink
          v-for="c in MORE"
          :key="c.to"
          :to="c.to"
          class="card"
        >
          <component :is="c.Icon" :size="22" class="card-icon" />
          <div class="card-text">
            <span class="card-title">{{ c.title }}</span>
            <span class="card-desc">{{ c.desc }}</span>
          </div>
          <span class="card-arrow">→</span>
        </RouterLink>
      </div>
    </section>

    <section class="group">
      <header class="group-popular-head">
        <h2 class="group-title-inline">熱門問題</h2>
        <RouterLink to="/faq" class="group-more">看全部 15 題 →</RouterLink>
      </header>
      <ul class="faq-list">
        <li v-for="f in POPULAR_QUESTIONS" :key="f.q">
          <RouterLink :to="f.to" class="faq-link">
            <span class="faq-q">{{ f.q }}</span>
            <span class="faq-arrow">→</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section class="contact">
      <p class="contact-text">沒找到您要的答案？</p>
      <a href="mailto:contact@yiimui.com" class="contact-mail">
        contact@yiimui.com
      </a>
      <p class="contact-urgent">
        緊急聯絡：<a href="mailto:yiimui.studio@gmail.com">yiimui.studio@gmail.com</a>
      </p>
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
  font-size: 15px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 8px 0 56px;
  max-width: 580px;
}

.group {
  margin-bottom: 56px;
}
.group-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0 0 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-line-subtle);
}

.group-popular-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin: 0 0 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.group-title-inline {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 0;
}
.group-more {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 2px;
}
.group-more:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }

.cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  text-decoration: none;
  color: inherit;
  transition: border-color 150ms, transform 200ms ease, background 150ms;
}
.card:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  transform: translateY(-1px);
}
.card-icon {
  flex-shrink: 0;
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
}
.card-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.card-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.card-desc {
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.card-arrow {
  flex-shrink: 0;
  font-family: var(--font-mono);
  color: var(--color-accent);
  font-size: 16px;
}

.faq-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.faq-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  text-decoration: none;
  color: var(--color-ink-default);
  border-radius: var(--radius-xs);
  transition: background 150ms, color 150ms;
}
.faq-link:hover {
  background: var(--color-paper-deep);
  color: var(--color-accent);
}
.faq-q {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
}
.faq-arrow {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0;
}
.faq-link:hover .faq-arrow { color: var(--color-accent); }

.contact {
  margin-top: 72px;
  padding: 32px 24px;
  text-align: center;
  background: var(--color-paper-deep);
  border-radius: var(--radius-sm);
}
.contact-text {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 12px;
}
.contact-mail {
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.16em;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 2px;
}
.contact-mail:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.contact-urgent {
  margin: 14px 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}
.contact-urgent a {
  color: var(--color-state-danger);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.contact-urgent a:hover { opacity: 0.75; }

@media (max-width: 1023px) {
  .page { padding: 48px 32px 72px; }
  .cards { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
}
</style>
