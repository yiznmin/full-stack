<script setup lang="ts">
// /faq — 常見問題
// 對應 docs/yii_mui_static_pages_spec.md 第七頁
// 4 分類 + 15 題折疊式
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useTitle } from '@vueuse/core'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

useTitle('常見問題｜易木 YIIMUI')

interface Qa { q: string; a: string }
interface Group { title: string; aux: string; items: Qa[] }

const GROUPS: Group[] = [
  {
    title: '關於產品',
    aux: 'Product',
    items: [
      {
        q: '我從來沒畫過，會不會太難？',
        a: '數字油畫不需要美術底子。每個區塊都有對應數字，只要照數字塗就好。建議從入門款的 20×20 或 30×30 開始，完成一幅後你會比想像中還有信心。',
      },
      {
        q: 'kit 裡面有什麼？需要再買畫框嗎？',
        a: '每份 kit 包含：已繃好的畫布（含基底框架）、配好色號的顏料、3 支不同粗細的畫筆、色號對照表、操作說明書。基本款不額外附畫框，但畫布本身已可掛牆。',
      },
      {
        q: '顏料會不會有毒？小孩或寵物碰到安全嗎？',
        a: '我們使用的是水性壓克力顏料，通過安全認證，不含有害物質。但仍建議避免幼兒誤食、寵物舔食。畫畫過程中保持通風即可。',
      },
      {
        q: '完成的畫可以保存多久？會褪色嗎？',
        a: '壓克力顏料完全乾燥後具備不錯的耐久度，在正常室內環境下可保存 5–10 年以上。避免長時間日曬，可延緩褪色。',
      },
    ],
  },
  {
    title: '關於下單',
    aux: 'Order',
    items: [
      {
        q: '結帳怎麼付款？',
        a: '目前提供銀行轉帳付款。下單後 24 小時內完成轉帳並回填末五碼，即可進入製作流程。',
      },
      {
        q: '多久會收到？',
        a: '現成款下單後 5–10 個工作天製作 + 1–3 天配送。客製款轉檔 1–2 天 + 確認後 5–10 天製作 + 1–3 天配送。節慶旺季前下單建議多預留時間。',
      },
    ],
  },
  {
    title: '關於客製',
    aux: 'Custom',
    items: [
      {
        q: '什麼樣的照片適合做客製？',
        a: '主體清楚、光線充足、背景單純的照片最適合。逆光、過度模糊、低解析度截圖會影響線稿品質。客製化流程頁面有完整的照片指南。',
      },
      {
        q: '客製多久收到？',
        a: '上傳照片後 1–2 個工作天內，我們會把線稿傳給你確認。確認後進入印製，約 5–10 個工作天 + 1–3 天配送。',
      },
      {
        q: '線稿可以修改幾次？',
        a: '確認前最多可修改 3 次。每次修改我們會根據你的回饋調整線稿，直到你滿意為止。',
      },
      {
        q: '可以做明星 / 偶像的肖像嗎？',
        a: '不行。我們不接受公眾人物肖像、卡通角色、品牌商標等涉及肖像權與智慧財產權的客製。客製內容請以你自己的照片（寵物、家人、朋友、自己）為主。',
      },
    ],
  },
  {
    title: '關於配送',
    aux: 'Shipping',
    items: [
      {
        q: '大尺寸超商真的不能取嗎？',
        a: '任一邊長超過 40 cm 的尺寸建議改選宅配。雖然有些超商可以勉強寄送，但運送過程中包裹擠壓會影響畫布品質，所以我們預設大尺寸採宅配。',
      },
      {
        q: '包裝會不會壓壞？',
        a: '每份 kit 都用紙板加固 + 減塑緩衝包裝，正常運送下不會變形。如收到時包裝有明顯損傷，請拍照在 7 天內告知，我們會處理。',
      },
      {
        q: '偏遠地區會加運費嗎？',
        a: '台灣本島不加價。離島（澎湖、金門、馬祖）需另計運費，下單時系統會提示。',
      },
    ],
  },
]

// 開合狀態：用 "{groupIdx}-{itemIdx}" 當 key
const opened = ref<Set<string>>(new Set())
function toggle(g: number, i: number) {
  const k = `${g}-${i}`
  if (opened.value.has(k)) opened.value.delete(k)
  else opened.value.add(k)
  opened.value = new Set(opened.value)
}
function isOpen(g: number, i: number): boolean {
  return opened.value.has(`${g}-${i}`)
}
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="00"
      chapter="FAQ"
      title="想到什麼問題？這裡找答案"
      caption="Frequently Asked"
    />

    <p class="lede">
      下面整理了客人最常問的 15 個問題，依分類列出。<br />
      點題目展開答案；找不到答案請見頁尾聯絡方式。
    </p>

    <section v-for="(g, gi) in GROUPS" :key="g.title" class="group">
      <header class="group-head">
        <span class="group-aux">{{ g.aux }}</span>
        <h2 class="group-title">{{ g.title }}</h2>
        <span class="group-count">{{ g.items.length }} 題</span>
      </header>

      <ul class="qa-list">
        <li v-for="(item, ii) in g.items" :key="item.q" class="qa">
          <button
            type="button"
            class="qa-q"
            :class="{ 'qa-q-open': isOpen(gi, ii) }"
            :aria-expanded="isOpen(gi, ii)"
            @click="toggle(gi, ii)"
          >
            <span class="qa-q-text">{{ item.q }}</span>
            <span class="qa-q-toggle">{{ isOpen(gi, ii) ? '▾' : '▸' }}</span>
          </button>
          <Transition name="qa-fade">
            <div v-if="isOpen(gi, ii)" class="qa-a">
              <p>{{ item.a }}</p>
            </div>
          </Transition>
        </li>
      </ul>
    </section>

    <!-- 找不到答案 -->
    <section class="contact">
      <p class="contact-title">找不到答案？</p>
      <p class="contact-body">私訊或來信，我們在 24 小時內回覆。</p>
      <div class="contact-links">
        <a href="https://instagram.com/yiimui" target="_blank" rel="noopener noreferrer" class="contact-link">
          IG @yiimui →
        </a>
        <a href="mailto:contact@yiimui.com" class="contact-link">
          contact@yiimui.com →
        </a>
        <a href="mailto:yiimui.studio@gmail.com" class="contact-link contact-link-urgent">
          緊急聯絡 yiimui.studio@gmail.com →
        </a>
      </div>
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
  font-size: 15px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 8px 0 64px;
}

.group { margin-bottom: 56px; }

.group-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line);
}
.group-aux {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.group-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
  flex: 1;
}
.group-count {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
}

.qa-list { list-style: none; padding: 0; margin: 0; }
.qa { border-bottom: 1px solid var(--color-line-subtle); }
.qa:last-child { border-bottom: none; }

.qa-q {
  width: 100%;
  background: transparent;
  border: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 18px 4px;
  cursor: pointer;
  text-align: left;
  transition: color 150ms;
}
.qa-q:hover { color: var(--color-accent); }
.qa-q-text {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: inherit;
  line-height: 1.6;
}
.qa-q-toggle {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-accent);
  flex-shrink: 0;
}
.qa-q-open { color: var(--color-accent); }

.qa-a {
  padding: 0 4px 18px;
  overflow: hidden;
}
.qa-a p {
  margin: 0;
  font-size: 14px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  background: var(--color-paper-deep);
  padding: 14px 18px;
  border-left: 2px solid var(--color-accent);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}

.qa-fade-enter-active, .qa-fade-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}
.qa-fade-enter-from, .qa-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* contact */
.contact {
  margin-top: 72px;
  padding: 40px 32px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-sm);
  text-align: center;
}
.contact-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 17px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.contact-body {
  font-size: 13px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 20px;
}
.contact-links {
  display: flex;
  gap: 24px;
  justify-content: center;
  flex-wrap: wrap;
}
.contact-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 2px;
}
.contact-link:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }
.contact-link-urgent {
  color: var(--color-state-danger);
  border-color: var(--color-state-danger);
}
.contact-link-urgent:hover { color: var(--color-state-danger); border-color: var(--color-state-danger); opacity: 0.75; }

@media (max-width: 1023px) { .page { padding: 48px 32px 72px; } }
@media (max-width: 767px) {
  .page { padding: 36px 24px 56px; }
  .group-title { font-size: 17px; }
  .qa-q-text { font-size: 14px; }
}
</style>
