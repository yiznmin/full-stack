<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  AlertTriangle, ArrowRight, ChevronRight, Clock, Loader2,
  LogOut, MapPin, Package, Quote, ShoppingBag, Ticket, User,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { useAuthStore } from '@/features/auth/store'
import * as profileApi from '../api'

const auth = useAuthStore()

const profileQuery = useQuery({
  queryKey: ['user-profile'] as const,
  queryFn: profileApi.fetchProfile,
})
const statsQuery = useQuery({
  queryKey: ['user-stats'] as const,
  queryFn: profileApi.fetchMemberStats,
})

const profile = computed(() => profileQuery.data.value ?? null)
const stats = computed(() => statsQuery.data.value ?? null)

async function logout() {
  try {
    await auth.logout()
  } finally {
    // 刷新到首頁清掉所有 query cache（含個人 cart / orders）
    window.location.assign('/')
  }
}

const ENTRY_CARDS = [
  {
    key: 'info',
    title: '個人資料',
    desc: '姓名 / Email / 性別 / 生日 / 密碼',
    to: '/profile/info',
    icon: User,
  },
  {
    key: 'shipping',
    title: '收件資料',
    desc: '宅配地址 / 超商門市',
    to: '/profile/shipping',
    icon: MapPin,
  },
  {
    key: 'coupons',
    title: '折扣券錢包',
    desc: '可用 / 已使用 / 已過期',
    to: '/profile/coupons',
    icon: Ticket,
  },
  {
    key: 'orders',
    title: '我的訂單',
    desc: '查看訂單與付款狀態',
    to: '/orders',
    icon: ShoppingBag,
  },
  {
    key: 'custom',
    title: '客製申請',
    desc: '客製作品申請與報價歷程',
    to: '/custom/requests',
    icon: Quote,
  },
] as const
</script>

<template>
  <main class="page">
    <SectionMasthead
      no="06"
      chapter="Account"
      title="會員中心"
      caption="My Account"
    />

    <nav class="sub-nav">
      <RouterLink to="/profile" class="sub-link" exact-active-class="is-active">概覽</RouterLink>
      <RouterLink to="/profile/info" class="sub-link" active-class="is-active">個人資料</RouterLink>
      <RouterLink to="/profile/shipping" class="sub-link" active-class="is-active">收件資料</RouterLink>
      <RouterLink to="/profile/coupons" class="sub-link" active-class="is-active">折扣券錢包</RouterLink>
    </nav>

    <div v-if="profileQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入中…
    </div>

    <template v-else-if="profile">
      <!-- ── Summary card ────────────────────────────────────────── -->
      <section class="summary">
        <div class="summary-left">
          <p class="summary-eyebrow">尊貴的</p>
          <h2 class="summary-name">{{ profile.name }}</h2>
          <p class="summary-email">{{ profile.email }}</p>
        </div>
        <div class="summary-stats">
          <div class="stat">
            <span class="stat-num">{{ stats?.orders_total ?? '—' }}</span>
            <span class="stat-label">總訂單</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ stats?.orders_completed ?? '—' }}</span>
            <span class="stat-label">已完成</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ stats?.available_coupons ?? '—' }}</span>
            <span class="stat-label">可用券</span>
          </div>
        </div>
      </section>

      <!-- ── 提醒 banners ────────────────────────────────────────── -->
      <section v-if="stats" class="banners">
        <RouterLink
          v-if="stats.orders_pending_payment > 0"
          to="/orders?status=pending_payment"
          class="banner banner-warn"
        >
          <Clock :size="18" :stroke-width="1.5" class="banner-icon" />
          <div class="banner-text">
            <p class="banner-title">您有 {{ stats.orders_pending_payment }} 筆訂單待付款</p>
            <p class="banner-sub">點此查看付款方式 → 完成付款後我們會立即排入製作</p>
          </div>
          <ArrowRight :size="16" :stroke-width="1.5" class="banner-arrow" />
        </RouterLink>

        <RouterLink
          v-if="stats.custom_quote_pending > 0"
          to="/custom/requests"
          class="banner banner-info"
        >
          <AlertTriangle :size="18" :stroke-width="1.5" class="banner-icon" />
          <div class="banner-text">
            <p class="banner-title">您有 {{ stats.custom_quote_pending }} 個客製報價待確認</p>
            <p class="banner-sub">24 小時內未確認報價會自動逾期</p>
          </div>
          <ArrowRight :size="16" :stroke-width="1.5" class="banner-arrow" />
        </RouterLink>
      </section>

      <!-- ── Entry cards ─────────────────────────────────────────── -->
      <section class="entries">
        <RouterLink
          v-for="entry in ENTRY_CARDS"
          :key="entry.key"
          :to="entry.to"
          class="entry"
        >
          <component :is="entry.icon" :size="22" :stroke-width="1.5" class="entry-icon" />
          <div class="entry-text">
            <h3 class="entry-title">{{ entry.title }}</h3>
            <p class="entry-desc">{{ entry.desc }}</p>
          </div>
          <ChevronRight :size="16" :stroke-width="1.5" class="entry-arrow" />
        </RouterLink>
      </section>

      <!-- ── 登出 ────────────────────────────────────────────────── -->
      <section class="logout-block">
        <button type="button" class="logout-btn" @click="logout">
          <LogOut :size="14" :stroke-width="1.5" />
          登出帳號
        </button>
      </section>
    </template>
  </main>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.spin { animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.state {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}

.sub-nav {
  display: flex; gap: 24px;
  margin: 32px 0 32px;
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

/* ── Summary card ───────────────────────────────────────────────── */
.summary {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 32px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 32px;
  align-items: center;
  margin-bottom: 24px;
}
.summary-left { min-width: 0; }
.summary-eyebrow {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
  margin: 0 0 8px;
}
.summary-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 6px;
}
.summary-email {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-ink-muted);
  margin: 0;
  letter-spacing: 0.04em;
}

.summary-stats {
  display: flex; gap: 24px;
  padding-left: 24px;
  border-left: 1px solid var(--color-line-subtle);
}
.stat {
  display: flex; flex-direction: column; align-items: center;
  min-width: 64px;
}
.stat-num {
  font-family: var(--font-mono);
  font-size: 28px;
  letter-spacing: 0.04em;
  color: var(--color-accent-deep);
  font-weight: 500;
}
.stat-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-top: 4px;
}

/* ── Banners ────────────────────────────────────────────────────── */
.banners {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 36px;
}
.banner {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 18px;
  border: 1px solid;
  border-radius: var(--radius-xs);
  text-decoration: none;
  transition: background 150ms, border-color 150ms;
}
.banner-icon { flex-shrink: 0; }
.banner-text { flex: 1; min-width: 0; }
.banner-title {
  margin: 0; font-size: 14px; font-weight: 500;
  letter-spacing: 0.04em;
}
.banner-sub {
  margin: 2px 0 0; font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}
.banner-arrow { flex-shrink: 0; opacity: 0.6; transition: transform 150ms, opacity 150ms; }
.banner:hover .banner-arrow { transform: translateX(3px); opacity: 1; }

.banner-warn {
  background: var(--color-paper-surface);
  border-color: var(--color-state-warning);
  color: var(--color-state-warning);
}
.banner-warn:hover { background: var(--color-paper-deep); }

.banner-info {
  background: var(--color-fresh-tint);
  border-color: var(--color-fresh-soft);
  color: var(--color-fresh);
}
.banner-info:hover { background: var(--color-paper-deep); }

/* ── Entry cards grid ───────────────────────────────────────────── */
.entries {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-bottom: 56px;
}

.entry {
  display: flex; align-items: center; gap: 18px;
  padding: 20px 24px;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--color-ink-default);
  transition: border-color 150ms, transform 150ms;
}
.entry:hover {
  border-color: var(--color-accent);
  transform: translateY(-1px);
}
.entry-icon {
  flex-shrink: 0;
  color: var(--color-accent);
}
.entry-text { flex: 1; min-width: 0; }
.entry-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0;
}
.entry-desc {
  font-size: 12px;
  color: var(--color-ink-muted);
  margin: 4px 0 0;
  letter-spacing: 0.04em;
}
.entry-arrow {
  flex-shrink: 0;
  color: var(--color-ink-muted);
  transition: transform 150ms, color 150ms;
}
.entry:hover .entry-arrow { transform: translateX(3px); color: var(--color-accent-deep); }

@media (min-width: 768px) {
  .entries { grid-template-columns: repeat(2, 1fr); }
}

/* ── Logout ─────────────────────────────────────────────────────── */
.logout-block {
  text-align: center;
  padding: 24px 0;
  border-top: 1px solid var(--color-line-subtle);
}
.logout-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 0; cursor: pointer;
  padding: 10px 18px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  transition: color 150ms;
}
.logout-btn:hover { color: var(--color-state-danger); }

@media (max-width: 767px) {
  .summary {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .summary-stats {
    padding-left: 0;
    padding-top: 24px;
    border-left: 0;
    border-top: 1px solid var(--color-line-subtle);
    justify-content: space-between;
  }
}
</style>
