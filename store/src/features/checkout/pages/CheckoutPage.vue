<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Loader2, MapPin, Store, Tag, Check } from 'lucide-vue-next'
import {
  useCartQuery,
  useCheckoutPreviewQuery,
  useCreateOrderMutation,
} from '@/features/cart/queries'
import * as profileApi from '@/features/profile/api'
import type { ShippingType, ShippingPreference, ApiError } from '@/features/cart/api'

const router = useRouter()

const cartQuery = useCartQuery()
const cartItems = computed(() => cartQuery.data.value?.items ?? [])
const cartSubtotal = computed(() => cartQuery.data.value?.subtotal ?? 0)

// 收件資料
const shippingQuery = useQuery({
  queryKey: ['shipping-profiles'],
  queryFn: profileApi.listShippingProfiles,
})
const profiles = computed(() => shippingQuery.data.value ?? [])
const selectedProfileId = ref<string | null>(null)

// 自動選預設 profile
watch(profiles, (list) => {
  if (selectedProfileId.value) return
  const def = list.find((p) => p.is_default) ?? list[0]
  if (def) selectedProfileId.value = def.id
}, { immediate: true })

const selectedProfile = computed(() =>
  profiles.value.find((p) => p.id === selectedProfileId.value) ?? null,
)

// profile.shipping_type 是 'home' | 'seven_eleven' | 'family_mart'
// 但 cart checkout-preview API 只收 'home' | 'convenience'，所以做 mapping
const shippingType = computed<ShippingType>(() => {
  const t = selectedProfile.value?.shipping_type
  if (!t || t === 'home') return 'home'
  return 'convenience'
})

// 折扣碼
const promoCode = ref('')
const appliedPromoCode = ref<string | null>(null)
function applyPromo() {
  appliedPromoCode.value = promoCode.value.trim() || null
}
function clearPromo() {
  promoCode.value = ''
  appliedPromoCode.value = null
}

// 出貨偏好（合併 / 分開）
const shippingPreference = ref<ShippingPreference>('merge')

// 客戶備註
const customerNotes = ref('')

// Checkout preview
const previewParams = computed(() => ({
  shipping_type: shippingType.value,
  promo_code: appliedPromoCode.value,
}))
const previewQuery = useCheckoutPreviewQuery(previewParams, {
  enabled: computed(() => cartItems.value.length > 0),
})
const preview = computed(() => previewQuery.data.value)

// 建單
const createMut = useCreateOrderMutation()
const apiError = ref<string | null>(null)

const canPlaceOrder = computed(() =>
  cartItems.value.length > 0 &&
  !!selectedProfileId.value &&
  !createMut.isPending.value,
)

async function placeOrder() {
  if (!selectedProfileId.value) {
    apiError.value = '請選擇收件資料'
    return
  }
  apiError.value = null
  try {
    const order = await createMut.mutateAsync({
      shipping_profile_id: selectedProfileId.value,
      shipping_preference: preview.value?.has_preorder ? shippingPreference.value : null,
      promo_code: appliedPromoCode.value,
      customer_notes: customerNotes.value.trim() || null,
    })
    router.push(`/checkout/complete?order=${order.order_id}`)
  } catch (e) {
    const err = e as ApiError
    apiError.value = err.detail || '送出失敗，請稍後再試'
  }
}

function profileSummary(p: profileApi.ShippingProfile): string {
  if (p.shipping_type === 'home') {
    const parts = [p.city, p.district, p.address_detail].filter(Boolean)
    return parts.join('') || '宅配地址'
  }
  return p.store_name || `超商 ${p.store_id ?? ''}`
}
</script>

<template>
  <main class="page">
    <nav class="breadcrumb">
      <RouterLink to="/cart">購物車</RouterLink>
      <span>/</span>
      <span class="current">結帳</span>
    </nav>

    <header class="head">
      <span class="eyebrow">— Checkout —</span>
      <h1 class="title">結帳</h1>
    </header>

    <div v-if="cartQuery.isPending.value" class="loading">
      <Loader2 :size="22" />
    </div>

    <section v-else-if="cartItems.length === 0" class="empty">
      <p class="empty-text">購物車是空的，無法結帳。</p>
      <RouterLink to="/products" class="empty-cta">看看商品 →</RouterLink>
    </section>

    <section v-else class="content">
      <div class="form-side">
        <section class="block">
          <h2 class="block-title">
            <span class="block-no">01</span>
            收件資料
          </h2>

          <div v-if="shippingQuery.isPending.value" class="block-loading">
            <Loader2 :size="16" />
          </div>

          <div v-else-if="profiles.length === 0" class="block-empty">
            <p>尚未有收件資料。請先到會員中心新增。</p>
            <RouterLink to="/profile/shipping" class="block-link">前往會員中心 →</RouterLink>
          </div>

          <ul v-else class="profile-list">
            <li v-for="p in profiles" :key="p.id">
              <button
                type="button"
                class="profile-card"
                :class="{ 'profile-active': selectedProfileId === p.id }"
                @click="selectedProfileId = p.id"
              >
                <span class="profile-icon">
                  <MapPin v-if="p.shipping_type === 'home'" :size="14" />
                  <Store v-else :size="14" />
                </span>
                <!-- shipping_type 顯示用：home / 7-Eleven / 全家 -->

                <div class="profile-info">
                  <div class="profile-name">
                    {{ p.recipient_name }}
                    <span v-if="p.is_default" class="profile-default">預設</span>
                  </div>
                  <div class="profile-meta">{{ p.phone }}</div>
                  <div class="profile-addr">{{ profileSummary(p) }}</div>
                </div>
                <span v-if="selectedProfileId === p.id" class="profile-check">
                  <Check :size="14" />
                </span>
              </button>
            </li>
          </ul>
        </section>

        <section v-if="preview?.has_preorder" class="block">
          <h2 class="block-title">
            <span class="block-no">02</span>
            預購出貨
          </h2>
          <p class="block-desc">訂單包含預購商品，請選擇出貨方式：</p>
          <div class="radio-row">
            <label class="radio-card" :class="{ 'radio-active': shippingPreference === 'merge' }">
              <input v-model="shippingPreference" type="radio" value="merge" />
              <span class="radio-title">合併出貨</span>
              <span class="radio-desc">等預購商品到貨後一起寄出</span>
            </label>
            <label class="radio-card" :class="{ 'radio-active': shippingPreference === 'split' }">
              <input v-model="shippingPreference" type="radio" value="split" />
              <span class="radio-title">分開出貨</span>
              <span class="radio-desc">現貨先寄、預購到貨再寄（額外運費）</span>
            </label>
          </div>
        </section>

        <section class="block">
          <h2 class="block-title">
            <span class="block-no">{{ preview?.has_preorder ? '03' : '02' }}</span>
            折扣碼
          </h2>
          <div class="promo-row">
            <Tag class="promo-icon" :size="16" />
            <input
              v-model="promoCode"
              type="text"
              class="promo-input"
              placeholder="輸入折扣碼"
              :disabled="!!appliedPromoCode"
              @keydown.enter="applyPromo"
            />
            <button
              v-if="!appliedPromoCode"
              type="button"
              class="promo-btn"
              :disabled="!promoCode.trim()"
              @click="applyPromo"
            >套用</button>
            <button
              v-else
              type="button"
              class="promo-btn promo-btn-clear"
              @click="clearPromo"
            >移除</button>
          </div>
          <p v-if="appliedPromoCode && preview && preview.discount_amount > 0" class="promo-hit">
            ✓ 已套用「{{ appliedPromoCode }}」 — 折抵 NT$ {{ preview.discount_amount.toLocaleString() }}
          </p>
          <p v-else-if="appliedPromoCode && preview && preview.discount_amount === 0" class="promo-miss">
            折扣碼無效或已過期
          </p>
        </section>

        <section class="block">
          <h2 class="block-title">
            <span class="block-no">{{ preview?.has_preorder ? '04' : '03' }}</span>
            訂單備註
            <span class="block-optional">（可選）</span>
          </h2>
          <textarea
            v-model="customerNotes"
            class="notes-input"
            rows="3"
            placeholder="有什麼想告訴我們的嗎？"
            maxlength="500"
          />
        </section>
      </div>

      <aside class="summary-side">
        <div class="summary-card">
          <h2 class="summary-title">訂單摘要</h2>

          <ul class="summary-items">
            <li v-for="i in cartItems" :key="i.id" class="summary-item">
              <span class="summary-item-name">{{ i.product_title }} × {{ i.quantity }}</span>
              <span class="summary-item-price">NT$ {{ (i.unit_price * i.quantity).toLocaleString() }}</span>
            </li>
          </ul>

          <dl class="summary-rows">
            <div class="row">
              <dt>小計</dt>
              <dd>NT$ {{ cartSubtotal.toLocaleString() }}</dd>
            </div>
            <div v-if="preview && preview.discount_amount > 0" class="row row-discount">
              <dt>折扣</dt>
              <dd>− NT$ {{ preview.discount_amount.toLocaleString() }}</dd>
            </div>
            <div class="row">
              <dt>運費</dt>
              <dd v-if="preview && preview.free_shipping_reason">
                <span class="ship-free">{{ preview.free_shipping_reason }}</span>
              </dd>
              <dd v-else-if="preview">NT$ {{ preview.shipping_fee.toLocaleString() }}</dd>
              <dd v-else class="row-muted">計算中...</dd>
            </div>
          </dl>

          <div class="total-row">
            <span class="total-label">應付總額</span>
            <span class="total-value">NT$ {{ (preview?.total ?? cartSubtotal).toLocaleString() }}</span>
          </div>

          <p v-if="apiError" class="api-err">{{ apiError }}</p>

          <button
            type="button"
            class="place-btn"
            :disabled="!canPlaceOrder"
            @click="placeOrder"
          >
            <Loader2 v-if="createMut.isPending.value" class="spin" />
            <span>{{ createMut.isPending.value ? '建立訂單中...' : '送出訂單' }}</span>
          </button>

          <p class="legal">
            送出訂單即同意《<RouterLink to="/refund-policy">退款政策</RouterLink>》。
          </p>
        </div>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 56px 56px 96px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 24px;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

.head { margin-bottom: 48px; }
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
  font-size: 44px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 12px 0 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 96px 0;
  color: var(--color-ink-muted);
}
.loading :deep(svg),
.spin {
  animation: spin 1s linear infinite;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
.spin { width: 14px; height: 14px; }
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  text-align: center;
  padding: 96px 24px;
}
.empty-text {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  color: var(--color-ink-default);
  margin: 0 0 24px;
}
.empty-cta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 4px;
}

.content {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 56px;
  align-items: start;
}

.form-side { display: flex; flex-direction: column; gap: 36px; }

.block-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 18px;
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.block-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--color-fresh);
  font-weight: 500;
}
.block-optional {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
  margin-left: 6px;
}

.block-loading {
  padding: 16px 0;
  color: var(--color-ink-muted);
}
.block-empty {
  padding: 24px;
  background: var(--color-paper-surface);
  border: 1px dashed var(--color-line);
  border-radius: var(--radius-xs);
  font-size: 13px;
  color: var(--color-ink-muted);
  text-align: center;
}
.block-empty p { margin: 0 0 12px; }
.block-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}
.block-link:hover { color: var(--color-accent-deep); }

.profile-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.profile-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  text-align: left;
  padding: 16px 18px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: border-color 150ms, background 150ms;
}
.profile-card:hover { border-color: var(--color-line); }
.profile-active {
  border-color: var(--color-accent) !important;
  background: var(--color-accent-tint);
}
.profile-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
  flex-shrink: 0;
}
.profile-icon :deep(svg) {
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
.profile-info { flex: 1; min-width: 0; }
.profile-name {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 15px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-default {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-fresh);
  border: 1px solid var(--color-fresh);
  padding: 0 5px;
  border-radius: var(--radius-xs);
  font-weight: 500;
}
.profile-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--color-ink-muted);
  margin-bottom: 4px;
}
.profile-addr {
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.profile-check {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-accent);
  color: var(--color-paper-canvas);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.profile-check :deep(svg) {
  stroke: currentColor; stroke-width: 2.5; fill: none;
}

.radio-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.radio-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: border-color 150ms;
}
.radio-card input { display: none; }
.radio-card:hover { border-color: var(--color-line); }
.radio-active { border-color: var(--color-accent) !important; background: var(--color-accent-tint); }
.radio-title {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
}
.radio-desc {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
}

.block-desc {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0 0 14px;
  letter-spacing: 0.02em;
}

.promo-row {
  display: flex;
  align-items: stretch;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  overflow: hidden;
  max-width: 420px;
  background: var(--color-paper-surface);
}
.promo-icon {
  margin: 0 12px;
  align-self: center;
  stroke: var(--color-ink-muted);
  stroke-width: 1.5;
  fill: none;
}
.promo-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-ink-strong);
  outline: none;
  padding: 12px 0;
}
.promo-btn {
  border: none;
  border-left: 1px solid var(--color-line);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  cursor: pointer;
  padding: 0 18px;
  transition: background 150ms;
}
.promo-btn:hover:not(:disabled) { background: var(--color-accent-tint); }
.promo-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.promo-btn-clear { color: var(--color-state-danger); }

.promo-hit {
  font-size: 12px;
  color: var(--color-fresh);
  margin: 8px 0 0;
  letter-spacing: 0.04em;
}
.promo-miss {
  font-size: 12px;
  color: var(--color-state-danger);
  margin: 8px 0 0;
}

.notes-input {
  width: 100%;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.85;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 12px 14px;
  outline: none;
  resize: vertical;
  transition: border-color 150ms;
}
.notes-input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-tint);
}

.summary-side { position: sticky; top: 96px; }
.summary-card {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 32px 28px;
}
.summary-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 20px;
}

.summary-items {
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
  border-bottom: 1px solid var(--color-line-subtle);
  padding-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.summary-item-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.summary-item-price {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-ink-strong);
  flex-shrink: 0;
}

.summary-rows .row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
}
.summary-rows .row dt {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.summary-rows .row dd {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-strong);
  margin: 0;
}
.summary-rows .row-discount dd { color: var(--color-fresh); }
.row-muted { color: var(--color-ink-muted); }
.ship-free {
  color: var(--color-fresh);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.total-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 16px 0 24px;
  border-top: 1px solid var(--color-line-subtle);
  margin-top: 12px;
}
.total-label {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}
.total-value {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 500;
  color: var(--color-accent-wine);
}

.api-err {
  margin: 0 0 12px;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-state-danger);
  background: rgba(123, 46, 64, 0.06);
  border: 1px solid var(--color-state-danger);
  border-radius: var(--radius-xs);
  letter-spacing: 0.04em;
}

.place-btn {
  width: 100%;
  height: 52px;
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  background: var(--color-ink-strong);
  border: 1px solid var(--color-ink-strong);
  cursor: pointer;
  transition: background 200ms, border-color 200ms;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.place-btn:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.place-btn:disabled { opacity: 0.55; cursor: not-allowed; }

.legal {
  font-size: 11px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 16px 0 0;
  text-align: center;
}
.legal a { color: var(--color-accent); text-decoration: none; }
.legal a:hover { color: var(--color-accent-deep); }

@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .content { grid-template-columns: 1fr; gap: 40px; }
  .summary-side { position: static; }
  .radio-row { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
}
</style>
