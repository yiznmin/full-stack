<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { Loader2, Trash2, Minus, Plus, ShoppingBag } from 'lucide-vue-next'
import {
  useCartQuery,
  useUpdateCartItemMutation,
  useDeleteCartItemMutation,
} from '../queries'
import type { CartItem, VariantSpec } from '../api'

const router = useRouter()
const cartQuery = useCartQuery()
const updateMut = useUpdateCartItemMutation()
const deleteMut = useDeleteCartItemMutation()

const items = computed(() => cartQuery.data.value?.items ?? [])
const subtotal = computed(() => cartQuery.data.value?.subtotal ?? 0)
const isEmpty = computed(
  () => !cartQuery.isPending.value && items.value.length === 0,
)

const totalQty = computed(() =>
  items.value.reduce((sum, i) => sum + i.quantity, 0),
)
const FREE_SHIPPING_AMOUNT = 800
const FREE_SHIPPING_QTY = 3
const freeShippingProgress = computed(() => {
  const byAmount = Math.min(subtotal.value / FREE_SHIPPING_AMOUNT, 1)
  const byQty = Math.min(totalQty.value / FREE_SHIPPING_QTY, 1)
  return Math.max(byAmount, byQty)
})
const freeShippingHit = computed(
  () => subtotal.value >= FREE_SHIPPING_AMOUNT || totalQty.value >= FREE_SHIPPING_QTY,
)
const freeShippingRemaining = computed(() => {
  if (freeShippingHit.value) return null
  const amountGap = FREE_SHIPPING_AMOUNT - subtotal.value
  const qtyGap = FREE_SHIPPING_QTY - totalQty.value
  if (amountGap <= 0 && qtyGap <= 0) return null
  return { amount: amountGap, qty: qtyGap }
})

function isJobSpec(spec: CartItem['variant_spec']): spec is VariantSpec {
  return 'canvas_w_cm' in spec
}

function specSummary(item: CartItem): string {
  const s = item.variant_spec
  if (!isJobSpec(s)) return ''
  const parts: string[] = []
  if (s.canvas_w_cm && s.canvas_h_cm) {
    parts.push(`${s.canvas_w_cm}×${s.canvas_h_cm}cm`)
  }
  const difficultyLabel: Record<string, string> = {
    beginner: '入門',
    elementary: '初級',
    intermediate: '中級',
    advanced: '進階',
  }
  if (s.difficulty && difficultyLabel[s.difficulty]) {
    parts.push(difficultyLabel[s.difficulty])
  }
  if (s.color_count) parts.push(`${s.color_count} 色`)
  return parts.join(' · ')
}

function inc(item: CartItem) {
  if (updateMut.isPending.value) return
  updateMut.mutate({ itemId: item.id, quantity: item.quantity + 1 })
}
function dec(item: CartItem) {
  if (updateMut.isPending.value) return
  if (item.quantity <= 1) {
    deleteMut.mutate(item.id)
  } else {
    updateMut.mutate({ itemId: item.id, quantity: item.quantity - 1 })
  }
}
function remove(item: CartItem) {
  if (deleteMut.isPending.value) return
  if (!confirm(`確定移除「${item.product_title}」？`)) return
  deleteMut.mutate(item.id)
}

function goCheckout() {
  router.push('/checkout')
}
</script>

<template>
  <main class="page">
    <nav class="breadcrumb">
      <RouterLink to="/">首頁</RouterLink>
      <span>/</span>
      <span class="current">購物車</span>
    </nav>

    <header class="head">
      <span class="eyebrow">— Cart —</span>
      <h1 class="title">購物車</h1>
      <p v-if="!isEmpty" class="meta">{{ totalQty }} 件商品</p>
    </header>

    <div v-if="cartQuery.isPending.value" class="loading">
      <Loader2 :size="22" />
    </div>

    <section v-else-if="isEmpty" class="empty">
      <ShoppingBag class="empty-icon" />
      <h2 class="empty-title">購物車是空的</h2>
      <p class="empty-hint">開始挑選喜歡的商品，慢慢畫一幅屬於自己的時光。</p>
      <RouterLink to="/products" class="empty-cta">看看商品 →</RouterLink>
    </section>

    <section v-else class="content">
      <!-- 商品列表 -->
      <div class="items">
        <article
          v-for="(item, idx) in items"
          :key="item.id"
          class="item"
          :class="{ 'item-inactive': !item.is_active }"
        >
          <div class="item-no">{{ String(idx + 1).padStart(2, '0') }}</div>

          <RouterLink
            v-if="item.product_id"
            :to="`/products/${item.product_id}`"
            class="item-thumb"
          >
            <img
              v-if="item.thumb_url"
              :src="item.thumb_url"
              :alt="item.product_title"
              loading="lazy"
            />
            <div v-else class="thumb-fallback"></div>
          </RouterLink>
          <div v-else class="item-thumb item-thumb-static">
            <img
              v-if="item.thumb_url"
              :src="item.thumb_url"
              :alt="item.product_title"
              loading="lazy"
            />
            <div v-else class="thumb-fallback"></div>
          </div>

          <div class="item-main">
            <h3 class="item-title">
              <RouterLink
                v-if="item.product_id"
                :to="`/products/${item.product_id}`"
                class="title-link"
              >{{ item.product_title }}</RouterLink>
              <span v-else>{{ item.product_title }}</span>
              <span v-if="!item.is_active" class="item-badge">已下架</span>
            </h3>
            <p v-if="specSummary(item)" class="item-spec">{{ specSummary(item) }}</p>
            <p v-if="item.preorder_units > 0" class="item-preorder">
              現貨 {{ item.fulfilled_units }} 件 · 預購 {{ item.preorder_units }} 件
            </p>
          </div>

          <div class="item-qty">
            <button
              type="button"
              class="qty-btn"
              :disabled="updateMut.isPending.value || deleteMut.isPending.value"
              @click="dec(item)"
              aria-label="減少數量"
            >
              <Minus :size="14" />
            </button>
            <span class="qty-num">{{ item.quantity }}</span>
            <button
              type="button"
              class="qty-btn"
              :disabled="updateMut.isPending.value"
              @click="inc(item)"
              aria-label="增加數量"
            >
              <Plus :size="14" />
            </button>
          </div>

          <div class="item-price">
            <div class="item-unit">NT$ {{ item.unit_price.toLocaleString() }}</div>
            <div class="item-total">
              小計 NT$ {{ (item.unit_price * item.quantity).toLocaleString() }}
            </div>
          </div>

          <button
            type="button"
            class="item-remove"
            :disabled="deleteMut.isPending.value"
            @click="remove(item)"
            aria-label="移除"
          >
            <Trash2 :size="14" />
          </button>
        </article>
      </div>

      <!-- Summary 小卡 -->
      <aside class="summary">
        <div class="summary-card">
          <h2 class="summary-title">訂單摘要</h2>

          <!-- 免運進度 -->
          <div class="ship-progress">
            <p v-if="freeShippingHit" class="ship-hit">已享免運 ✓</p>
            <p v-else class="ship-pending">
              再 NT$ {{ Math.max(0, FREE_SHIPPING_AMOUNT - subtotal).toLocaleString() }}
              或加 {{ Math.max(0, FREE_SHIPPING_QTY - totalQty) }} 件 即享免運
            </p>
            <div class="ship-bar">
              <div class="ship-bar-fill" :style="{ width: `${freeShippingProgress * 100}%` }"></div>
            </div>
          </div>

          <dl class="summary-rows">
            <div class="row">
              <dt>小計</dt>
              <dd>NT$ {{ subtotal.toLocaleString() }}</dd>
            </div>
            <div class="row row-muted">
              <dt>運費</dt>
              <dd>結帳時計算</dd>
            </div>
          </dl>

          <button
            type="button"
            class="checkout-btn"
            :disabled="items.length === 0"
            @click="goCheckout"
          >
            前往結帳 →
          </button>

          <RouterLink to="/products" class="continue">繼續逛逛</RouterLink>
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
  flex-wrap: wrap;
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
  margin: 12px 0 8px;
}
.meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
  margin: 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 96px 0;
  color: var(--color-ink-muted);
}
.loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty */
.empty {
  text-align: center;
  padding: 96px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-icon {
  width: 40px; height: 40px;
  stroke: var(--color-ink-muted);
  stroke-width: 1.25;
  fill: none;
  margin-bottom: 24px;
  opacity: 0.6;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 12px;
}
.empty-hint {
  font-size: 14px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 28px;
  max-width: 360px;
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
.empty-cta:hover { color: var(--color-accent-deep); border-color: var(--color-accent-deep); }

/* Content layout — items 列表 + 右側摘要 */
.content {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 56px;
  align-items: start;
}

/* Items */
.items {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--color-line);
}
.item {
  display: grid;
  grid-template-columns: 32px 84px 1fr auto auto 32px;
  align-items: center;
  gap: 24px;
  padding: 24px 0;
  border-bottom: 1px solid var(--color-line-subtle);
  transition: opacity 200ms;
}
.item-inactive { opacity: 0.55; }

.item-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-fresh);
  font-weight: 500;
}

.item-thumb {
  display: block;
  width: 84px;
  height: 84px;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  overflow: hidden;
  text-decoration: none;
  transition: border-color 150ms;
  flex-shrink: 0;
}
.item-thumb:not(.item-thumb-static):hover { border-color: var(--color-line); }
.item-thumb img {
  width: 100%; height: 100%;
  object-fit: cover;
  filter: sepia(0.05) saturate(0.95);
}
.thumb-fallback {
  width: 100%; height: 100%;
  background: linear-gradient(
    135deg,
    var(--color-paper-deep) 0%,
    var(--color-accent-tint) 60%,
    var(--color-accent-soft) 130%
  );
  opacity: 0.6;
}

.title-link {
  color: inherit;
  text-decoration: none;
  transition: color 150ms;
}
.title-link:hover { color: var(--color-accent); }

.item-main { min-width: 0; }
.item-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 4px;
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.item-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--color-state-danger);
  border: 1px solid var(--color-state-danger);
  padding: 1px 7px;
  border-radius: var(--radius-xs);
  text-transform: uppercase;
}
.item-spec {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin: 0;
}
.item-preorder {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  color: var(--color-state-warning);
  margin: 4px 0 0;
  letter-spacing: 0.04em;
}

.item-qty {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  background: var(--color-paper-surface);
}
.qty-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-default);
  transition: color 150ms;
}
.qty-btn:hover:not(:disabled) { color: var(--color-accent); }
.qty-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.qty-btn :deep(svg) {
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
.qty-num {
  font-family: var(--font-mono);
  font-size: 13px;
  min-width: 28px;
  text-align: center;
  color: var(--color-ink-strong);
}

.item-price { text-align: right; min-width: 110px; }
.item-unit {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
}
.item-total {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-ink-strong);
  margin-top: 2px;
}

.item-remove {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-muted);
  transition: color 150ms;
}
.item-remove:hover:not(:disabled) { color: var(--color-state-danger); }
.item-remove:disabled { opacity: 0.45; cursor: not-allowed; }
.item-remove :deep(svg) {
  stroke: currentColor; stroke-width: 1.5; fill: none;
}

/* Summary */
.summary { position: sticky; top: 96px; }
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
  margin: 0 0 24px;
}

.ship-progress { margin-bottom: 24px; }
.ship-hit {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 13px;
  color: var(--color-fresh);
  margin: 0 0 8px;
  letter-spacing: 0.04em;
}
.ship-pending {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  color: var(--color-ink-default);
  margin: 0 0 8px;
  letter-spacing: 0.04em;
}
.ship-bar {
  height: 4px;
  background: var(--color-line-subtle);
  border-radius: 2px;
  overflow: hidden;
}
.ship-bar-fill {
  height: 100%;
  background: var(--color-fresh);
  transition: width 400ms ease;
}

.summary-rows {
  margin: 0 0 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.summary-rows .row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 8px 0;
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
  font-size: 14px;
  color: var(--color-ink-strong);
  font-weight: 500;
  margin: 0;
}
.summary-rows .row-muted dd { font-weight: 400; font-size: 12px; color: var(--color-ink-muted); }

.checkout-btn {
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
}
.checkout-btn:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.checkout-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.continue {
  display: block;
  text-align: center;
  margin-top: 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}
.continue:hover { color: var(--color-accent-deep); }

@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .content { grid-template-columns: 1fr; gap: 40px; }
  .summary { position: static; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .item {
    grid-template-columns: 72px 1fr 32px;
    grid-template-rows: auto auto auto;
    gap: 8px 14px;
    padding: 20px 0;
  }
  .item-no { display: none; }
  .item-thumb { grid-row: 1 / span 2; grid-column: 1; width: 72px; height: 72px; }
  .item-main { grid-row: 1; grid-column: 2; }
  .item-remove { grid-row: 1; grid-column: 3; }
  .item-qty { grid-row: 2; grid-column: 2; justify-self: start; }
  .item-price { grid-row: 3; grid-column: 1 / 4; justify-self: end; min-width: auto; padding-top: 8px; border-top: 1px dashed var(--color-line-subtle); width: 100%; text-align: right; }
}
</style>
