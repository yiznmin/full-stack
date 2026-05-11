<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Loader2, Package, Sparkles } from 'lucide-vue-next'
import { useProductDetailQuery, useRelatedProductsQuery } from '../queries'
import type { ProductDetail, ProductVariant, ProductImage, ProductBrief } from '../api'
import ProductGallery from '../components/ProductGallery.vue'
import VariantSelector from '../components/VariantSelector.vue'
import ProductDescription from '../components/ProductDescription.vue'
import ProductCard from '../components/ProductCard.vue'
import { useAddCartItemMutation } from '@/features/cart/queries'
import { useAuthStore } from '@/features/auth/store'
import type { ApiError } from '@/features/cart/api'
import { useSeo } from '@/shared/composables/useSeo'

const route = useRoute()

const id = computed(() => String(route.params.id || ''))
const isPreview = computed(() => id.value === 'preview' && import.meta.env.DEV)

// Real API
const detailQuery = useProductDetailQuery(id)
const relatedQuery = useRelatedProductsQuery(id)

// Preview mock data
const PREVIEW_PRODUCT: ProductDetail = {
  id: 'preview',
  title: '京都嵐山的秋',
  description:
    '11 月，渡月橋邊的楓紅。這是一張在霜降後拍下的早晨，路人很少、風很慢、整個山谷只有水聲。',
  cover_image_url: '',
  images: [],
  series: {
    id: 'preview-series',
    name: '京都四季',
    products: [
      { id: 'p2', title: '冬日的祇園小徑', cover_image_url: '', price_min: 397, is_preorder: false },
      { id: 'p3', title: '春櫻沿岸', cover_image_url: '', price_min: 397, is_preorder: false },
    ],
  },
  tags: [
    { id: 't1', name: '療癒' },
    { id: 't2', name: '居家裝飾' },
  ],
  variants: [
    { id: 'v1', canvas_w_cm: 30, canvas_h_cm: 40, difficulty: 'beginner', detail: 'standard', color_count: 18, price: 397, is_active: true, is_preorder: false, filled_template_url: null },
    { id: 'v2', canvas_w_cm: 30, canvas_h_cm: 40, difficulty: 'elementary', detail: 'standard', color_count: 24, price: 460, is_active: true, is_preorder: false, filled_template_url: null },
    { id: 'v3', canvas_w_cm: 40, canvas_h_cm: 50, difficulty: 'beginner', detail: 'standard', color_count: 22, price: 540, is_active: true, is_preorder: false, filled_template_url: null },
    { id: 'v4', canvas_w_cm: 40, canvas_h_cm: 50, difficulty: 'elementary', detail: 'detailed', color_count: 32, price: 680, is_active: true, is_preorder: false, filled_template_url: null },
    { id: 'v5', canvas_w_cm: 50, canvas_h_cm: 60, difficulty: 'intermediate', detail: 'detailed', color_count: 40, price: 860, is_active: true, is_preorder: true, filled_template_url: null },
  ],
}

const product = computed<ProductDetail | null>(() => {
  if (isPreview.value) return PREVIEW_PRODUCT
  return detailQuery.data.value ?? null
})

const isLoading = computed(() => !isPreview.value && detailQuery.isPending.value)
const isError = computed(() => !isPreview.value && detailQuery.isError.value)

// SEO — 每次 product 載入更新 title / og / JSON-LD Product schema
useSeo(() => {
  const p = product.value
  if (!p) return {}
  const activeVariants = p.variants.filter((v) => v.is_active)
  const prices = activeVariants.map((v) => v.price)
  const minPrice = prices.length ? Math.min(...prices) : 0
  const maxPrice = prices.length ? Math.max(...prices) : 0
  const offers = activeVariants.length === 0
    ? undefined
    : minPrice === maxPrice
      ? {
          '@type': 'Offer',
          price: String(minPrice),
          priceCurrency: 'TWD',
          availability: activeVariants.every((v) => v.is_preorder)
            ? 'https://schema.org/PreOrder'
            : 'https://schema.org/InStock',
        }
      : {
          '@type': 'AggregateOffer',
          lowPrice: String(minPrice),
          highPrice: String(maxPrice),
          priceCurrency: 'TWD',
          offerCount: activeVariants.length,
        }
  const shortDesc = p.description ? p.description.slice(0, 140) : `${p.title} — 易木 YIIMUI 數字油畫`
  return {
    title: p.title,
    description: shortDesc,
    ogImage: p.cover_image_url || undefined,
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: p.title,
      description: shortDesc,
      image: p.cover_image_url ? [p.cover_image_url] : undefined,
      brand: { '@type': 'Brand', name: '易木 YIIMUI' },
      ...(offers ? { offers } : {}),
    } as Record<string, unknown>,
  }
})

// Normalize images (response.images can be { items } or array)
const productImages = computed<ProductImage[]>(() => {
  const imgs = product.value?.images
  if (!imgs) return []
  if (Array.isArray(imgs)) return imgs
  return imgs.items ?? []
})

// Selected variant
const selectedVariant = ref<ProductVariant | null>(null)

const priceLabel = computed(() => {
  if (selectedVariant.value) {
    return `NT$ ${selectedVariant.value.price.toLocaleString()}`
  }
  if (!product.value || product.value.variants.length === 0) return ''
  const prices = product.value.variants.filter((v) => v.is_active).map((v) => v.price)
  if (prices.length === 0) return ''
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  return min === max ? `NT$ ${min.toLocaleString()}` : `NT$ ${min.toLocaleString()} — ${max.toLocaleString()}`
})

const stockStatus = computed(() => {
  if (!selectedVariant.value) return null
  return selectedVariant.value.is_preorder ? 'preorder' : 'in_stock'
})

// Related products
const related = computed(() => {
  if (isPreview.value) {
    return PREVIEW_PRODUCT.series?.products.map<ProductBrief>((p) => ({
      id: p.id,
      title: p.title,
      cover_image_url: p.cover_image_url,
      difficulty_range: ['beginner', 'beginner'],
      price_min: p.price_min,
      price_max: p.price_min,
      is_preorder: p.is_preorder,
    })) ?? []
  }
  return relatedQuery.data.value?.items.map<ProductBrief>((p) => ({
    id: p.id,
    title: p.title,
    cover_image_url: p.cover_image_url,
    difficulty_range: null,
    price_min: p.price_min,
    price_max: p.price_min,
    is_preorder: p.is_preorder,
  })) ?? []
})

// Cart
const router = useRouter()
const auth = useAuthStore()
const addCartMut = useAddCartItemMutation()

const toast = ref<string | null>(null)
const toastKind = ref<'info' | 'success' | 'error'>('info')
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string, kind: 'info' | 'success' | 'error' = 'info') {
  toast.value = msg
  toastKind.value = kind
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = null
  }, 3500)
}

async function onAddToCart() {
  if (isPreview.value) {
    showToast('預覽模式無法加入購物車', 'info')
    return
  }
  if (!selectedVariant.value) {
    showToast('請先選擇尺寸 / 難易度', 'info')
    return
  }
  if (!auth.isLoggedIn) {
    // 未登入 → 跳登入帶 redirect 回來
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  try {
    await addCartMut.mutateAsync({
      variantId: selectedVariant.value.id,
      quantity: 1,
    })
    showToast('✓ 已加入購物車', 'success')
  } catch (e) {
    const err = e as ApiError
    if (err.status === 401) {
      router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    showToast(err.detail || '加入失敗，請稍後再試', 'error')
  }
}
</script>

<template>
  <section v-if="isLoading" class="page page-loading">
    <Loader2 :size="20" />
  </section>

  <section v-else-if="isError || !product" class="page page-empty">
    <Package class="empty-icon" />
    <h1 class="empty-title">找不到這件商品</h1>
    <p class="empty-hint">商品已下架或網址錯誤。</p>
    <RouterLink to="/products" class="empty-cta">回商品列表</RouterLink>
  </section>

  <section v-else class="page">
    <div v-if="isPreview" class="preview-banner">
      <span class="preview-eyebrow">Design Preview</span>
      <span>商品建設中 — 以下為設計示意，dev mode only。</span>
    </div>

    <div class="layout">
      <!-- 左：圖片輪播 -->
      <div class="left">
        <ProductGallery
          :cover="product.cover_image_url"
          :extras="productImages"
          :variant-image="selectedVariant?.filled_template_url ?? null"
          :alt="product.title"
        />
      </div>

      <!-- 右：資訊 + 規格 + 加購 -->
      <div class="right">
        <nav class="breadcrumb">
          <RouterLink to="/products">商品</RouterLink>
          <span>/</span>
          <RouterLink v-if="product.series" :to="`/series/${product.series.id}`">{{ product.series.name }}</RouterLink>
          <span v-if="product.series">/</span>
          <span class="current">{{ product.title }}</span>
        </nav>

        <h1 class="title">{{ product.title }}</h1>

        <div class="meta">
          <span v-for="t in product.tags" :key="t.id" class="tag">{{ t.name }}</span>
        </div>

        <div class="price-block">
          <span class="price-label">售價</span>
          <span class="price">{{ priceLabel }}</span>
          <span
            v-if="stockStatus === 'preorder'"
            class="stock-badge stock-preorder"
          >預購中</span>
          <span
            v-else-if="stockStatus === 'in_stock'"
            class="stock-badge stock-in-stock"
          >現貨</span>
        </div>

        <div class="divider" />

        <VariantSelector :variants="product.variants" @select="selectedVariant = $event" />

        <div class="actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!selectedVariant || addCartMut.isPending.value"
            @click="onAddToCart"
          >
            <Loader2 v-if="addCartMut.isPending.value" class="btn-spin" />
            <span>{{ addCartMut.isPending.value ? '加入中...' : '加入購物車' }}</span>
          </button>
          <Transition name="toast">
            <span v-if="toast" class="toast" :class="`toast-${toastKind}`">{{ toast }}</span>
          </Transition>
        </div>

        <RouterLink to="/custom/apply" class="custom-cta">
          <Sparkles class="custom-cta-icon" />
          <span class="custom-cta-text">
            <span class="custom-cta-title">想要不同規格？</span>
            <span class="custom-cta-desc">用照片做一張專屬於你的客製油畫 →</span>
          </span>
        </RouterLink>

        <div class="divider" />

        <ProductDescription :description="product.description" />
      </div>
    </div>

    <!-- 同系列商品 -->
    <section v-if="related.length > 0" class="related">
      <header class="related-header">
        <div>
          <div class="related-eyebrow">Related</div>
          <h2 class="related-title">
            同系列商品
            <span v-if="product.series" class="related-series">— {{ product.series.name }}</span>
          </h2>
        </div>
      </header>
      <div class="related-grid">
        <ProductCard v-for="p in related" :key="p.id" :product="p" :preview="isPreview" />
      </div>
    </section>
  </section>
</template>

<style scoped>
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 56px 56px 96px;
}

.page-loading {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-muted);
}
.page-loading :deep(svg) {
  animation: spin 1s linear infinite;
  stroke-width: 1.5; fill: none; stroke: currentColor;
}
@keyframes spin { to { transform: rotate(360deg); } }

.page-empty {
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.empty-icon {
  width: 32px; height: 32px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none;
  margin-bottom: 24px;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 16px;
}
.empty-hint {
  font-size: 13px; color: var(--color-ink-muted); letter-spacing: 0.04em; margin: 0 0 24px;
}
.empty-cta {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}

.preview-banner {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-paper-deep);
  border: 1px dashed var(--color-line);
  border-radius: var(--radius-xs);
  margin-bottom: 32px;
  font-size: 12px;
  color: var(--color-ink-muted);
}
.preview-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-accent);
}

.layout {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  gap: 64px;
  align-items: flex-start;
}

.right {
  display: flex;
  flex-direction: column;
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
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 38px;
  letter-spacing: 0.04em;
  line-height: 1.4;
  color: var(--color-ink-strong);
  margin: 0 0 18px;
}

.meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 28px;
}
.tag {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  padding: 4px 12px;
  border: 1px solid var(--color-line);
  border-radius: 999px;
}

.price-block {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 28px;
}
.price-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.price {
  font-family: var(--font-mono);
  font-size: 28px;
  color: var(--color-ink-strong);
  font-weight: 500;
  letter-spacing: 0.02em;
}
.stock-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: var(--radius-xs);
}
.stock-in-stock {
  background: rgba(122, 140, 90, 0.12);
  color: var(--color-state-success);
}
.stock-preorder {
  background: rgba(184, 145, 73, 0.12);
  color: var(--color-state-warning);
}

.divider {
  height: 1px;
  background: var(--color-line-subtle);
  margin: 32px 0;
}

.actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 32px;
  position: relative;
  flex-wrap: wrap;
}

.btn {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  padding: 16px 36px;
  border: 1px solid;
  background: transparent;
  cursor: pointer;
  transition: all 200ms;
}
.btn-primary {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border-color: var(--color-ink-strong);
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toast {
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  padding: 8px 16px;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
}
.toast-success {
  color: var(--color-fresh);
  background: var(--color-fresh-tint);
  border-color: var(--color-fresh);
}
.toast-error {
  color: var(--color-state-danger);
  background: rgba(123, 46, 64, 0.06);
  border-color: var(--color-state-danger);
}

.btn-spin {
  width: 14px; height: 14px;
  stroke: currentColor; stroke-width: 1.75; fill: none;
  animation: btn-spin 1s linear infinite;
  margin-right: 8px;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }
.btn-primary { display: inline-flex; align-items: center; justify-content: center; }

.toast-enter-active, .toast-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(4px); }

.custom-cta {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  padding: 18px 20px;
  margin-top: 28px;
  text-decoration: none;
  color: inherit;
  transition: all 180ms;
}
.custom-cta:hover {
  border-color: var(--color-accent);
  background: var(--color-paper-canvas);
}
.custom-cta-icon {
  width: 22px; height: 22px;
  stroke: var(--color-accent); stroke-width: 1.5; fill: none;
  flex-shrink: 0;
}
.custom-cta-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.custom-cta-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}
.custom-cta-desc {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

/* Related */
.related {
  margin-top: 96px;
  padding-top: 48px;
  border-top: 1px solid var(--color-line);
}
.related-header { margin-bottom: 40px; }
.related-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 12px;
}
.related-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0;
}
.related-series {
  font-size: 18px;
  color: var(--color-ink-muted);
  margin-left: 8px;
}
.related-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 28px;
}

@media (max-width: 1279px) {
  .layout { gap: 48px; }
  .related-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .layout { grid-template-columns: 1fr; gap: 40px; }
  .title { font-size: 30px; }
  .related-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .title { font-size: 24px; }
  .price { font-size: 22px; }
  .related-grid { grid-template-columns: 1fr; }
}
</style>
