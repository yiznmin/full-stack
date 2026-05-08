<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  ArrowRight, BookOpen, Image as ImageIcon, Sparkles,
  ImagePlus, MessageSquare, CheckCircle2, Palette,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { useCustomRequestListQuery } from '../queries'
import { STATUS_LABEL, listCustomCases, DIFFICULTY_LABEL, type CustomCase, type Difficulty } from '../api'
import CustomApplyForm from '../components/CustomApplyForm.vue'
import CaseDetailDialog from '../components/CaseDetailDialog.vue'

function scrollToApply(e: MouseEvent) {
  e.preventDefault()
  document.getElementById('apply-section')?.scrollIntoView({ behavior: 'smooth' })
}

// 案例靈感 inline（取最新 6 件）
const casesQuery = useQuery({
  queryKey: ['custom-cases-hub', { page_size: 6 }] as const,
  queryFn: () => listCustomCases({ page: 1, page_size: 6 }),
  staleTime: 5 * 60 * 1000,
})
const cases = computed<CustomCase[]>(() => casesQuery.data.value?.items ?? [])

const activeCase = ref<CustomCase | null>(null)
function openCase(c: CustomCase) { activeCase.value = c }
function closeCase() { activeCase.value = null }

// 從 modal 點「諮詢類似規格」→ 預填表單 + scroll 到表單
const applyFormRef = ref<InstanceType<typeof CustomApplyForm> | null>(null)
function consultCase(c: CustomCase) {
  closeCase()
  applyFormRef.value?.applyCaseInspiration({
    canvas_w_cm: c.canvas_w_cm,
    canvas_h_cm: c.canvas_h_cm,
    difficulty: c.difficulty,
    title: c.title,
  })
  setTimeout(() => {
    document.getElementById('apply-section')?.scrollIntoView({ behavior: 'smooth' })
  }, 100)
}

// 已登入：顯示自己的進行中申請（不包含已完成）
const myListQuery = useCustomRequestListQuery(() => ({ page: 1, page_size: 5 }))
const inflightRequests = computed(() =>
  (myListQuery.data.value?.items ?? []).filter(
    (r) => r.status !== 'quote_confirmed' && r.status !== 'quote_rejected',
  ),
)
</script>

<template>
  <main class="custom-hub">
    <!-- ── HERO ──────────────────────────────────────────────────────── -->
    <section class="hero">
      <div class="hero-inner">
        <div class="kicker">
          <span class="kicker-no">No. 07</span>
          <span class="kicker-dot"></span>
          <span class="kicker-chapter">Custom · 客製化</span>
        </div>
        <h1 class="hero-title">把你的回憶<br />做成一幅畫</h1>
        <p class="hero-desc">
          上傳一張照片，我們將它轉換為數字油畫模板。<br />
          每一份客製，從理解您的故事開始。
        </p>
      </div>
    </section>

    <!-- 已登入：進行中申請 quick access -->
    <section v-if="inflightRequests.length > 0" class="inflight">
      <SectionMasthead
        no="00"
        chapter="In progress"
        title="進行中的申請"
        link-text="查看全部 →"
        link-to="/custom/requests"
      />
      <ul class="inflight-list">
        <li v-for="req in inflightRequests" :key="req.id" class="inflight-item">
          <RouterLink :to="{ name: 'custom-request-detail', params: { id: req.id } }">
            <div class="inflight-status">{{ STATUS_LABEL[req.status] }}</div>
            <div class="inflight-meta">
              <span>{{ new Date(req.created_at).toLocaleDateString('zh-TW') }}</span>
              <span v-if="req.quoted_price">NT$ {{ req.quoted_price }}</span>
            </div>
          </RouterLink>
        </li>
      </ul>
    </section>

    <!-- ── 三大區塊卡片 ────────────────────────────────────────────── -->
    <section class="hub-cards">
      <SectionMasthead
        no="01"
        chapter="Explore"
        title="從這裡開始"
      />
      <div class="hub-grid">
        <RouterLink to="/custom/about" class="hub-card hub-card-about">
          <div class="hub-card-header">
            <span class="hub-no">01</span>
            <BookOpen :size="22" :stroke-width="1.4" class="hub-icon" />
          </div>
          <h3>客製化內容說明</h3>
          <p>服務介紹、適合的照片、流程細節、價格邏輯、常見問題。</p>
          <span class="hub-cta">了解服務 <ArrowRight :size="14" /></span>
        </RouterLink>

        <RouterLink to="/custom/cases" class="hub-card hub-card-cases">
          <div class="hub-card-header">
            <span class="hub-no">02</span>
            <ImageIcon :size="22" :stroke-width="1.4" class="hub-icon" />
          </div>
          <h3>客製案例參考</h3>
          <p>過去客戶完成的作品。喜歡的話，可以「諮詢類似規格」直接帶入您的申請。</p>
          <span class="hub-cta">瀏覽案例 <ArrowRight :size="14" /></span>
        </RouterLink>

        <a href="#apply-section" class="hub-card hub-card-apply" @click="scrollToApply">
          <div class="hub-card-header">
            <span class="hub-no">03</span>
            <Sparkles :size="22" :stroke-width="1.4" class="hub-icon" />
          </div>
          <h3>開始申請</h3>
          <p>上傳照片、選擇偏好，1–3 個工作天內收到專屬報價。</p>
          <span class="hub-cta">下方填寫 <ArrowRight :size="14" /></span>
        </a>
      </div>
    </section>

    <!-- ── 案例靈感 inline ───────────────────────────────────────── -->
    <section v-if="cases.length > 0 || casesQuery.isPending.value" class="cases-section">
      <SectionMasthead
        no="02"
        chapter="Inspiration"
        title="客製案例參考"
        caption="From our archive"
        link-text="瀏覽全部案例 →"
        link-to="/custom/cases"
      />
      <div v-if="casesQuery.isPending.value" class="cases-loading">案例載入中…</div>
      <div v-else class="cases-grid">
        <article
          v-for="c in cases"
          :key="c.id"
          class="case-card"
          @click="openCase(c)"
        >
          <div class="case-img">
            <img :src="c.image_url" :alt="c.title" loading="lazy" />
          </div>
          <div class="case-meta">
            <h4>{{ c.title }}</h4>
            <p v-if="c.canvas_w_cm" class="case-spec">
              {{ c.canvas_w_cm }}×{{ c.canvas_h_cm }} cm
              <span v-if="c.difficulty"> · {{ DIFFICULTY_LABEL[c.difficulty as Difficulty] || c.difficulty }}</span>
            </p>
          </div>
        </article>
      </div>
    </section>

    <!-- ── 申請表單區（直接在 hub 底部讓使用者 scroll 填寫） ──────── -->
    <section class="apply-section" id="apply-section">
      <SectionMasthead
        no="03"
        chapter="Apply"
        title="開始申請"
        caption="Bring your photo to canvas"
      />
      <p class="apply-intro">
        上傳一張您喜歡的照片、留下基本偏好，<br />
        我們將在 1–3 個工作天內回覆專屬報價。
      </p>
      <CustomApplyForm ref="applyFormRef" />
    </section>

    <!-- ── 4-step quick overview ────────────────────────────────────── -->
    <section class="quick-flow">
      <SectionMasthead
        no="02"
        chapter="At a glance"
        title="客製流程"
        link-text="查看完整流程 →"
        link-to="/custom/about"
      />
      <ol class="steps">
        <li class="step">
          <div class="step-icon"><ImagePlus :size="18" :stroke-width="1.4" /></div>
          <div class="step-no">01</div>
          <h4>提交申請</h4>
          <p>上傳照片，留下偏好。</p>
        </li>
        <li class="step">
          <div class="step-icon"><MessageSquare :size="18" :stroke-width="1.4" /></div>
          <div class="step-no">02</div>
          <h4>回覆報價</h4>
          <p>1–3 工作天內 Email 通知。</p>
        </li>
        <li class="step">
          <div class="step-icon"><CheckCircle2 :size="18" :stroke-width="1.4" /></div>
          <div class="step-no">03</div>
          <h4>確認下單</h4>
          <p>看預覽圖，24 小時內付款。</p>
        </li>
        <li class="step">
          <div class="step-icon"><Palette :size="18" :stroke-width="1.4" /></div>
          <div class="step-no">04</div>
          <h4>專屬製作</h4>
          <p>製作完成後寄送高解析數字稿。</p>
        </li>
      </ol>
    </section>

    <CaseDetailDialog
      :case-data="activeCase"
      @close="closeCase"
      @consult="consultCase"
    />
  </main>
</template>

<style scoped>
.custom-hub {
  max-width: 1080px; margin: 0 auto;
  padding: 32px 24px 96px;
}

/* hero */
.hero {
  padding: 80px 0 56px;
  border-bottom: 1px solid var(--color-line);
  margin-bottom: 64px;
}
.hero-inner { max-width: 720px; }
.kicker { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
.kicker-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); }
.kicker-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.kicker-chapter { font-family: var(--font-display); font-style: italic; font-size: 14px; color: var(--color-accent); }
.hero-title {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: clamp(36px, 5vw, 56px); letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 24px; line-height: 1.25;
}
.hero-desc { font-size: 16px; color: var(--color-ink-default); letter-spacing: 0.02em; line-height: 1.8; margin: 0; }

/* inflight */
.inflight { margin-bottom: 64px; }
.inflight-list {
  list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.inflight-item a {
  display: block; padding: 20px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  text-decoration: none; color: var(--color-ink-strong);
  transition: border-color 150ms;
}
.inflight-item a:hover { border-color: var(--color-accent); }
.inflight-status { font-family: var(--font-cn-serif); font-size: 17px; margin-bottom: 8px; }
.inflight-meta {
  display: flex; gap: 12px;
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.1em; color: var(--color-ink-muted);
}

/* hub cards */
.hub-cards { margin-bottom: 80px; }
.hub-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
}
@media (max-width: 880px) { .hub-grid { grid-template-columns: 1fr; } }

.hub-card {
  display: flex; flex-direction: column; padding: 32px 28px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line); border-radius: var(--radius-md);
  text-decoration: none; color: var(--color-ink-strong);
  transition: border-color 200ms, transform 200ms, box-shadow 200ms;
  min-height: 240px; position: relative;
}
.hub-card:hover {
  border-color: var(--color-accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(43, 36, 27, 0.06);
}
.hub-card:hover .hub-cta { color: var(--color-accent-deep); }

.hub-card-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px;
}
.hub-no {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em;
  color: var(--color-fresh);
  padding: 4px 10px; border: 1px solid var(--color-line); border-radius: 2px;
}
.hub-icon { color: var(--color-accent); }
.hub-card h3 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 22px; letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 12px;
}
.hub-card p {
  font-size: 14px; line-height: 1.8; color: var(--color-ink-muted);
  margin: 0 0 20px; flex: 1;
}
.hub-cta {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-default);
  border-bottom: 1px solid currentColor; padding-bottom: 4px;
  align-self: flex-start;
  transition: color 200ms;
}

/* cases inline section */
.cases-section { margin-bottom: 80px; }
.cases-loading {
  padding: 40px; text-align: center;
  color: var(--color-ink-muted); font-size: 13px;
}
.cases-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); gap: 20px;
}
@media (max-width: 880px) { .cases-grid { grid-template-columns: 1fr 1fr; } }
.case-card {
  cursor: pointer;
  border: 1px solid var(--color-line-subtle);
  border-radius: 4px;
  overflow: hidden;
  background: var(--color-paper-surface);
  transition: border-color 200ms, transform 200ms;
}
.case-card:hover {
  border-color: var(--color-accent);
  transform: translateY(-2px);
}
.case-img {
  aspect-ratio: 4 / 3; overflow: hidden;
  background: var(--color-paper-deep);
}
.case-img img { width: 100%; height: 100%; object-fit: cover; }
.case-meta { padding: 12px 16px 14px; }
.case-meta h4 {
  font-family: var(--font-cn-serif); font-weight: 400;
  font-size: 15px; color: var(--color-ink-strong);
  margin: 0 0 4px;
}
.case-spec {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--color-ink-muted); margin: 0; letter-spacing: 0.06em;
}

/* apply section */
.apply-section {
  margin-bottom: 80px;
  scroll-margin-top: 80px;
}
.apply-section :deep(.apply-form-root) { max-width: 720px; margin: 32px 0 0; }
.apply-intro {
  font-size: 15px; line-height: 1.85; color: var(--color-ink-muted);
  margin: 12px 0 0; max-width: 640px;
}

/* quick flow */
.quick-flow { margin-bottom: 32px; }
.steps {
  list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 24px;
}
.step { padding: 24px 20px; border-top: 1px solid var(--color-line); }
.step-icon {
  width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line);
  border-radius: 50%; margin-bottom: 14px;
  color: var(--color-accent-deep);
}
.step-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); margin-bottom: 6px; }
.step h4 { font-family: var(--font-cn-serif); font-weight: 400; font-size: 16px; letter-spacing: 0.04em; margin: 0 0 6px; color: var(--color-ink-strong); }
.step p { font-size: 13px; color: var(--color-ink-muted); line-height: 1.7; margin: 0; }
</style>
