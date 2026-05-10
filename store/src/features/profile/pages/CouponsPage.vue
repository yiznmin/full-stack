<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { ArrowLeft, Loader2, Wallet } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import * as profileApi from '../api'
import CouponCard from '../components/CouponCard.vue'

const tab = ref<'available' | 'used' | 'expired'>('available')

const couponsQuery = useQuery({
  queryKey: ['user-coupons'] as const,
  queryFn: profileApi.listUserCoupons,
})

const data = computed(() => couponsQuery.data.value ?? null)
const counts = computed(() => ({
  available: data.value?.available.length ?? 0,
  used: data.value?.used.length ?? 0,
  expired: data.value?.expired.length ?? 0,
}))

const activeList = computed(() => data.value?.[tab.value] ?? [])

const TAB_LABEL = {
  available: '可使用',
  used: '已使用',
  expired: '已過期',
} as const
</script>

<template>
  <main class="page">
    <RouterLink to="/profile" class="back-link">
      <ArrowLeft :size="14" />
      會員中心
    </RouterLink>

    <SectionMasthead
      no="24"
      chapter="Wallet"
      title="折扣券錢包"
      caption="My Coupons"
    />

    <nav class="sub-nav">
      <RouterLink to="/profile" class="sub-link" exact-active-class="is-active">概覽</RouterLink>
      <RouterLink to="/profile/info" class="sub-link" active-class="is-active">個人資料</RouterLink>
      <RouterLink to="/profile/shipping" class="sub-link" active-class="is-active">收件資料</RouterLink>
      <RouterLink to="/profile/coupons" class="sub-link" active-class="is-active">折扣券錢包</RouterLink>
    </nav>

    <div class="tabs">
      <button
        v-for="key in ['available', 'used', 'expired'] as const"
        :key="key"
        type="button"
        class="tab"
        :class="{ 'is-active': tab === key }"
        @click="tab = key"
      >
        <span class="tab-label">{{ TAB_LABEL[key] }}</span>
        <span class="tab-count">{{ counts[key] }}</span>
      </button>
    </div>

    <div v-if="couponsQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入中…
    </div>
    <div v-else-if="couponsQuery.isError.value" class="state error">
      <p>無法載入折扣券</p>
    </div>

    <div v-else-if="activeList.length === 0" class="empty">
      <Wallet :size="32" :stroke-width="1.25" />
      <p>{{
        tab === 'available' ? '目前沒有可用的折扣券'
        : tab === 'used' ? '尚無使用紀錄'
        : '沒有過期的折扣券'
      }}</p>
      <RouterLink v-if="tab === 'available'" to="/products" class="cta">
        前往逛逛 →
      </RouterLink>
    </div>

    <div v-else class="grid">
      <CouponCard
        v-for="c in activeList"
        :key="c.id"
        :coupon="c"
        :state="tab"
      />
    </div>
  </main>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted); text-decoration: none;
  margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.spin { animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.sub-nav {
  display: flex; gap: 24px;
  margin: 32px 0 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.sub-link {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 14px; letter-spacing: 0.06em;
  color: var(--color-ink-muted); text-decoration: none;
  padding-bottom: 12px; margin-bottom: -13px;
  border-bottom: 1px solid transparent;
  transition: color 150ms, border-color 150ms;
}
.sub-link:hover { color: var(--color-accent-deep); }
.sub-link.is-active {
  color: var(--color-ink-strong);
  border-bottom-color: var(--color-accent);
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 32px;
}
.tab {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 18px;
  background: transparent; border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif); font-size: 13px;
  color: var(--color-ink-default);
  transition: border-color 150ms, color 150ms, background 150ms;
}
.tab:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.tab.is-active {
  background: var(--color-ink-strong);
  border-color: var(--color-ink-strong);
  color: var(--color-paper-canvas);
}
.tab-count {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 18px;
  padding: 0 6px;
  background: var(--color-paper-canvas); color: var(--color-ink-strong);
  border-radius: 9px;
  font-family: var(--font-mono); font-size: 10px;
}
.tab.is-active .tab-count {
  background: var(--color-paper-canvas); color: var(--color-ink-strong);
}

.state, .empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px;
  color: var(--color-ink-muted);
}
.state.error { color: var(--color-state-danger); }
.empty p { margin: 0; font-size: 14px; }
.cta {
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent); text-decoration: none;
  border-bottom: 1px solid currentColor; padding-bottom: 2px;
  margin-top: 8px;
}
.cta:hover { color: var(--color-accent-deep); }

.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 640px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1024px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
