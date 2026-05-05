<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useProductsQuery } from '@/features/products/queries'

// Hero 視覺：拿最新一筆商品的封面當 placeholder hero image。
// 之後 admin 後台可以加「Hero 推薦商品」設定（屬 future enhancement，see §1 不做）。
const heroProductQuery = useProductsQuery({ sort: 'latest', page: 1, page_size: 1 })
</script>

<template>
  <section class="hero">
    <div class="hero-text">
      <div class="hero-eyebrow">2026 春 · 新作上架</div>
      <h1 class="hero-title">慢慢畫一幅，<br>屬於自己的時光。</h1>
      <p class="hero-sub">
        親手畫的療癒，從一個下午開始。<br>
        60 色礦物顏料、17 種畫布尺寸 — 一筆一筆，沒有快進鍵。
      </p>
      <div class="hero-actions">
        <RouterLink to="/products" class="btn btn-primary">立即選購</RouterLink>
        <RouterLink to="/custom" class="btn btn-link">用照片客製 →</RouterLink>
      </div>
    </div>
    <div class="hero-visual">
      <img
        v-if="heroProductQuery.data.value?.items[0]?.cover_image_url"
        :src="heroProductQuery.data.value.items[0].cover_image_url"
        :alt="heroProductQuery.data.value.items[0].title"
      />
      <div v-else class="hero-visual-placeholder" />
    </div>
  </section>
</template>

<style scoped>
.hero {
  max-width: 1440px;
  margin: 0 auto;
  padding: 96px 56px 120px;
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 80px;
  align-items: center;
}

.hero-eyebrow {
  font-family: var(--font-body);
  font-weight: 400;
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-bottom: 36px;
}

.hero-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 60px;
  line-height: 1.4;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 36px;
}

.hero-sub {
  font-size: 14px;
  line-height: 2;
  color: var(--color-ink-default);
  margin: 0 0 48px;
  max-width: 420px;
  letter-spacing: 0.04em;
}

.hero-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.btn {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  padding: 16px 32px;
  border: 1px solid;
  background: transparent;
  text-decoration: none;
  display: inline-block;
  transition: all 200ms;
}
.btn-primary {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border-color: var(--color-ink-strong);
}
.btn-primary:hover {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.btn-link {
  border: none;
  padding: 16px 4px;
  color: var(--color-accent);
  letter-spacing: 0.24em;
}
.btn-link:hover {
  color: var(--color-accent-deep);
}

.hero-visual {
  aspect-ratio: 4 / 5;
  overflow: hidden;
  background: var(--color-paper-deep);
}
.hero-visual img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: sepia(0.04) saturate(0.95);
}
.hero-visual-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(
    135deg,
    var(--color-paper-deep),
    var(--color-accent-soft) 70%,
    var(--color-accent)
  );
  opacity: 0.4;
}

@media (max-width: 1023px) {
  .hero {
    padding: 64px 32px 80px;
    gap: 48px;
  }
  .hero-title {
    font-size: 44px;
  }
}

@media (max-width: 767px) {
  .hero {
    grid-template-columns: 1fr;
    padding: 48px 24px 64px;
    gap: 40px;
  }
  .hero-title {
    font-size: 36px;
  }
  .hero-sub {
    font-size: 13px;
  }
}
</style>
