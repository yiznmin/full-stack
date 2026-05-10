<script setup lang="ts">
import { ref } from 'vue'
import { ArrowLeft, Coins } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import InfoDrawer from '@/features/info/InfoDrawer.vue'
import CustomApplyForm from '../components/CustomApplyForm.vue'

const pricingOpen = ref(false)
</script>

<template>
  <main class="page">
    <RouterLink to="/custom" class="back-link">
      <ArrowLeft :size="14" /> 客製化首頁
    </RouterLink>

    <SectionMasthead
      no="04"
      chapter="Apply"
      title="開始申請"
      caption="Bring your photo to canvas"
    />

    <p class="intro">
      上傳一張您喜歡的照片，留下基本偏好，<br />
      我們將在 1–3 個工作天內回覆報價。
    </p>

    <button
      type="button"
      class="pricing-banner"
      @click="pricingOpen = true"
    >
      <Coins :size="18" class="pricing-icon" />
      <div class="pricing-text">
        <span class="pricing-title">不確定大概多少錢？</span>
        <span class="pricing-desc">查看尺寸 × 難度的報價區間</span>
      </div>
      <span class="pricing-cta">查看 →</span>
    </button>

    <CustomApplyForm />

    <InfoDrawer
      :open="pricingOpen"
      slug="pricing_reference"
      title="報價參考"
      full-page-path="/pricing"
      @close="pricingOpen = false"
    />
  </main>
</template>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 32px 24px 96px; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); text-decoration: none; margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }
.intro {
  font-size: 15px; line-height: 1.85; color: var(--color-ink-default);
  margin: 12px 0 24px;
}

.pricing-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  margin: 0 0 32px;
  padding: 16px 20px;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  cursor: pointer;
  text-align: left;
  transition: border-color 150ms, background 150ms;
}
.pricing-banner:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.pricing-icon {
  flex-shrink: 0;
  stroke: var(--color-accent);
  stroke-width: 1.5;
  fill: none;
}
.pricing-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.pricing-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.pricing-desc {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}
.pricing-cta {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
}
</style>
