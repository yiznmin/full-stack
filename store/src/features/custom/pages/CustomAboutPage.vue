<script setup lang="ts">
import { ref } from 'vue'
import {
  ArrowLeft, ChevronDown, Camera, Palette, Clock, MessageSquare,
  CheckCircle2, ImagePlus, Heart, AlertTriangle,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'

// FAQ accordion state
const openFaqId = ref<string | null>(null)
function toggleFaq(id: string) {
  openFaqId.value = openFaqId.value === id ? null : id
}

interface Faq { id: string; q: string; a: string }
const FAQS: Faq[] = [
  {
    id: 'photo-quality',
    q: '什麼樣的照片適合做客製化？',
    a: '構圖清楚、主體明確、解析度足夠（建議 1500px 以上長邊）的照片最理想。光線過暗、嚴重模糊、複雜雜亂背景的照片可能無法呈現預期效果，我們會在收到照片後先評估，如不適合會說明並建議您調整或更換。',
  },
  {
    id: 'who-decides-detail',
    q: '為什麼表單沒有「細緻度」選項？',
    a: '客製照片的線稿細緻度，需依您照片的實際品質與複雜度決定，我們會在報價時連同建議一起說明。這樣可以避免因規格不合而需要重新製作。',
  },
  {
    id: 'pricing',
    q: '客製化怎麼計費？',
    a: '客製照片售價 = (基礎成本 + 顏料費) × 細緻度加成 × 客製服務費率（預設 2.0 倍）。基礎成本依畫布尺寸、顏料費依實際使用色數計算。實際金額由我們依照片複雜度報價，您也可在「申請」表單看到參考價區間。',
  },
  {
    id: 'timeline',
    q: '從申請到收到作品需要多久？',
    a: '申請後 1–3 個工作天內回覆報價；確認後進入製作排程，依排程約 7–14 個工作天完成製作與出貨。實際時程會依當下排程量略有差異。',
  },
  {
    id: 'revision',
    q: '報價可以修改嗎？',
    a: '可以。在收到報價後 24 小時內，您可以提出最多 3 次修改要求（例如調整尺寸、難度、細緻度），我們會重新製作測試稿並重新報價。',
  },
  {
    id: 'extend',
    q: '報價過期了怎麼辦？',
    a: '每筆報價有 24 小時確認期。期限內您可主動延長一次（再 +24 小時）；若仍未確認則自動逾期，可從「我的申請」點「重新申請」會自動帶回上次的規格與備註。',
  },
  {
    id: 'edit-after-submit',
    q: '送出申請後可以修改嗎？',
    a: '送出後尚未進入「洽談中」階段（status = quote_pending）時，您可以隨時修改照片、尺寸偏好、難度和備註。一旦我們開始製作測試稿（status = negotiating）就無法修改，可透過站內訊息與我們溝通。',
  },
  {
    id: 'photo-private',
    q: '我的照片會被公開嗎？',
    a: '不會。您上傳的照片儲存於私密路徑，僅您與我們的管理員可以看到，不會出現在公開頁面或案例展示中。完成的作品如要作為案例展示，會主動徵詢您的同意。',
  },
  {
    id: 'cancel-refund',
    q: '可以取消訂單嗎？退款條件？',
    a: '在尚未付款（pending_payment）時可直接取消申請；付款後若製作尚未開始可申請退款；製作開始後因屬客製商品，恕無法退款，請務必在報價確認前先看清楚預覽圖與規格。',
  },
]
</script>

<template>
  <main class="page">
    <RouterLink to="/custom" class="back-link">
      <ArrowLeft :size="14" /> 客製化首頁
    </RouterLink>

    <header class="hd">
      <div class="kicker">
        <span class="kicker-no">No. 01</span>
        <span class="kicker-dot"></span>
        <span class="kicker-chapter">About · 服務說明</span>
      </div>
      <h1>關於客製化服務</h1>
      <p class="lede">
        把一張照片變成一幅可以親手畫的數字油畫。<br />
        每一份客製，都從理解您的故事開始。
      </p>
    </header>

    <!-- 服務介紹 -->
    <section class="block">
      <SectionMasthead no="01" chapter="What we do" title="服務介紹" />
      <p>
        我們將您的照片轉換為線稿與色號對應，並為您調配對應的顏料套組，
        交給您一份「按數字塗色就能完成」的作品包。
      </p>
      <p>
        從拍照那一刻的構圖、難度、細節層次，到最終手繪完成後的成品感，
        每個環節都有我們會幫您把關。
      </p>
    </section>

    <!-- 適合 / 不適合 -->
    <section class="block">
      <SectionMasthead no="02" chapter="What works" title="什麼照片適合 / 不適合" />
      <div class="suit-grid">
        <div class="suit suit-good">
          <Heart :size="20" :stroke-width="1.4" />
          <h3>適合</h3>
          <ul>
            <li>主體清楚、構圖明確的人像 / 寵物 / 風景</li>
            <li>解析度足夠（長邊 1500px 以上）</li>
            <li>色彩層次豐富、光線均勻</li>
            <li>背景簡單或可被簡化的場景</li>
          </ul>
        </div>
        <div class="suit suit-warn">
          <AlertTriangle :size="20" :stroke-width="1.4" />
          <h3>建議避免</h3>
          <ul>
            <li>嚴重模糊、晃動、失焦的照片</li>
            <li>過暗 / 過曝、細節已遺失的影像</li>
            <li>背景過於繁雜（如人潮、雜物堆）</li>
            <li>內含他人肖像權 / 版權問題的素材</li>
          </ul>
        </div>
      </div>
      <p class="block-note">
        如果您不確定照片是否適合，可以先送出申請 — 我們在收到後會先評估，
        如不適合會主動聯繫並建議您調整方向。
      </p>
    </section>

    <!-- 流程 -->
    <section class="block">
      <SectionMasthead no="03" chapter="How it works" title="完整流程" />
      <ol class="flow">
        <li>
          <div class="flow-icon"><ImagePlus :size="18" /></div>
          <div class="flow-content">
            <h4>01 · 提交申請</h4>
            <p>上傳照片、選擇尺寸偏好（選填）、難度（選填，可讓我們建議）、留下備註。</p>
          </div>
        </li>
        <li>
          <div class="flow-icon"><MessageSquare :size="18" /></div>
          <div class="flow-content">
            <h4>02 · 評估與報價（1–3 個工作天）</h4>
            <p>我們評估照片可呈現程度、色彩與細節、適合的細緻度，回覆建議規格與報價金額。</p>
          </div>
        </li>
        <li>
          <div class="flow-icon"><CheckCircle2 :size="18" /></div>
          <div class="flow-content">
            <h4>03 · 確認報價（24 小時）</h4>
            <p>查看降解析度浮水印預覽圖；24 小時內可選確認 / 拒絕 / 要求修改（限 3 次）/ 延長 24 小時（限 1 次）。</p>
          </div>
        </li>
        <li>
          <div class="flow-icon"><Palette :size="18" /></div>
          <div class="flow-content">
            <h4>04 · 製作與出貨（7–14 個工作天）</h4>
            <p>付款確認後進入製作排程，完成後寄出原寸高解析數字稿與顏料套組。</p>
          </div>
        </li>
      </ol>
    </section>

    <!-- 透明度 -->
    <section class="block">
      <SectionMasthead no="04" chapter="Transparency" title="關於我們的透明度" />
      <div class="trans-grid">
        <div class="trans-item">
          <div class="trans-icon"><Camera :size="18" /></div>
          <h3>您的照片</h3>
          <p>儲存於私密路徑，僅您與管理員可看；如要作為案例會主動徵詢您的同意。</p>
        </div>
        <div class="trans-item">
          <div class="trans-icon"><Palette :size="18" /></div>
          <h3>定價公式</h3>
          <p>(基礎成本 + 顏料費) × 細緻度加成 × 客製服務費率。基礎成本依尺寸表，顏料費依實際色數。</p>
        </div>
        <div class="trans-item">
          <div class="trans-icon"><Clock :size="18" /></div>
          <h3>修改 / 延長</h3>
          <p>修改最多 3 次，延長報價最多 1 次（+24 小時）。逾期可從「我的申請」重新申請帶回規格。</p>
        </div>
      </div>
    </section>

    <!-- FAQ -->
    <section class="block">
      <SectionMasthead no="05" chapter="FAQ" title="常見問題" />
      <ul class="faq-list">
        <li v-for="f in FAQS" :key="f.id" class="faq-item" :class="{ open: openFaqId === f.id }">
          <button class="faq-q" @click="toggleFaq(f.id)" :aria-expanded="openFaqId === f.id">
            <span>{{ f.q }}</span>
            <ChevronDown :size="16" class="faq-icon" />
          </button>
          <div v-show="openFaqId === f.id" class="faq-a">
            <p>{{ f.a }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- CTA bottom -->
    <section class="cta-section">
      <h2>準備好了嗎？</h2>
      <p>從上傳一張照片開始，1–3 個工作天內收到您的專屬報價。</p>
      <div class="cta-actions">
        <RouterLink to="/custom/apply" class="btn-primary">開始申請</RouterLink>
        <RouterLink to="/custom/cases" class="btn-secondary">先看案例</RouterLink>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page { max-width: 880px; margin: 0 auto; padding: 32px 24px 96px; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); text-decoration: none; margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.hd { padding-bottom: 56px; border-bottom: 1px solid var(--color-line); margin-bottom: 56px; }
.kicker { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.kicker-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); }
.kicker-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.kicker-chapter { font-family: var(--font-display); font-style: italic; font-size: 14px; color: var(--color-accent); }
.hd h1 { font-family: var(--font-cn-serif); font-weight: 300; font-size: clamp(28px, 4vw, 40px); letter-spacing: 0.04em; color: var(--color-ink-strong); margin: 0 0 20px; line-height: 1.3; }
.lede { font-size: 17px; line-height: 1.85; color: var(--color-ink-default); margin: 0; }

.block { margin-bottom: 64px; }
.block p {
  font-size: 15px; line-height: 1.85; color: var(--color-ink-default);
  margin: 0 0 16px;
}
.block-note {
  font-size: 13px; color: var(--color-ink-muted); font-style: italic;
  padding: 12px 16px; border-left: 2px solid var(--color-accent);
  background: var(--color-paper-surface, #FCF7E5); margin-top: 24px;
}

/* 適合 / 不適合 grid */
.suit-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
  margin-top: 24px;
}
@media (max-width: 720px) { .suit-grid { grid-template-columns: 1fr; } }
.suit {
  padding: 24px;
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
}
.suit-good { border-left: 3px solid #5A7A4F; }
.suit-warn { border-left: 3px solid #B85B58; }
.suit > svg:first-child { margin-bottom: 12px; }
.suit-good > svg:first-child { color: #5A7A4F; }
.suit-warn > svg:first-child { color: #B85B58; }
.suit h3 { font-family: var(--font-cn-serif); font-weight: 400; font-size: 17px; margin: 0 0 12px; color: var(--color-ink-strong); }
.suit ul { padding: 0 0 0 18px; margin: 0; }
.suit li { font-size: 14px; line-height: 1.8; color: var(--color-ink-default); }

/* 流程 */
.flow { list-style: none; padding: 0; margin: 0; }
.flow li {
  display: flex; gap: 20px; padding: 24px 0;
  border-top: 1px solid var(--color-line);
}
.flow li:last-child { border-bottom: 1px solid var(--color-line); }
.flow-icon {
  flex-shrink: 0; width: 40px; height: 40px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: 50%;
  color: var(--color-accent-deep);
}
.flow-content h4 {
  font-family: var(--font-cn-serif); font-weight: 400; font-size: 16px;
  margin: 0 0 6px; color: var(--color-ink-strong);
}
.flow-content p { font-size: 14px; line-height: 1.7; color: var(--color-ink-muted); margin: 0; }

/* 透明度 */
.trans-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px; margin-top: 24px;
}
.trans-item { padding: 20px; border: 1px solid var(--color-line); border-radius: var(--radius-sm); background: var(--color-paper-surface, #FCF7E5); }
.trans-icon {
  width: 32px; height: 32px;
  display: inline-flex; align-items: center; justify-content: center;
  background: #FFF; border: 1px solid var(--color-line); border-radius: 50%;
  color: var(--color-accent-deep); margin-bottom: 12px;
}
.trans-item h3 { font-family: var(--font-cn-serif); font-weight: 400; font-size: 15px; margin: 0 0 8px; color: var(--color-ink-strong); }
.trans-item p { font-size: 13px; line-height: 1.7; color: var(--color-ink-muted); margin: 0; }

/* FAQ */
.faq-list { list-style: none; padding: 0; margin: 0; }
.faq-item { border-top: 1px solid var(--color-line); }
.faq-item:last-child { border-bottom: 1px solid var(--color-line); }
.faq-q {
  width: 100%; padding: 20px 4px;
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  background: transparent; border: 0; cursor: pointer;
  font-family: var(--font-cn-serif); font-size: 16px;
  color: var(--color-ink-strong); text-align: left;
}
.faq-icon { color: var(--color-ink-muted); transition: transform 200ms; }
.faq-item.open .faq-icon { transform: rotate(180deg); color: var(--color-accent-deep); }
.faq-a { padding: 0 4px 24px; }
.faq-a p { font-size: 14px; line-height: 1.85; color: var(--color-ink-default); margin: 0; }

/* CTA bottom */
.cta-section {
  margin-top: 64px; padding: 56px 24px;
  background: var(--color-paper-surface, #FCF7E5);
  border: 1px solid var(--color-line); border-radius: var(--radius-md);
  text-align: center;
}
.cta-section h2 { font-family: var(--font-cn-serif); font-weight: 300; font-size: 28px; letter-spacing: 0.04em; margin: 0 0 12px; color: var(--color-ink-strong); }
.cta-section p { font-size: 14px; color: var(--color-ink-muted); margin: 0 0 24px; }
.cta-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.btn-primary, .btn-secondary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 12px 24px; cursor: pointer; border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 14px; letter-spacing: 0.06em;
  text-decoration: none;
}
.btn-primary { background: var(--color-accent-deep); color: #FCF7E5; border: 0; }
.btn-primary:hover { background: var(--color-accent); }
.btn-secondary { background: transparent; color: var(--color-ink-default); border: 1px solid var(--color-line); }
.btn-secondary:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
</style>
