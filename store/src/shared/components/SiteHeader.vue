<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Search, User, ShoppingBag, Menu } from 'lucide-vue-next'
import SiteLogo from './SiteLogo.vue'
import IconButton from './IconButton.vue'
import MegaMenu from './MegaMenu.vue'
import MobileMenu from './MobileMenu.vue'
import {
  useThemesQuery,
  useSeriesQuery,
  useTagsQuery,
  useFeaturedSeriesQuery,
} from '@/features/browse/queries'

const themesQuery = useThemesQuery()
const seriesQuery = useSeriesQuery()
const tagsQuery = useTagsQuery()
const featuredSeriesQuery = useFeaturedSeriesQuery()
const mobileOpen = ref(false)

const FEATURED_SERIES_LIMIT = 5

const DIFFICULTIES = [
  { code: 'beginner', label: '入門' },
  { code: 'elementary', label: '初級' },
  { code: 'intermediate', label: '中級' },
  { code: 'advanced', label: '進階' },
]

const SERIES_LIMIT = 6
const TAGS_LIMIT = 8
</script>

<template>
  <header class="site-header">
    <div class="site-header-inner">
      <!-- Mobile (< 1024) — 漢堡 + logo + cart -->
      <button
        class="mobile-trigger"
        aria-label="開啟導覽選單"
        @click="mobileOpen = true"
      >
        <Menu />
      </button>

      <!-- Desktop nav -->
      <nav class="site-nav desktop">
        <MegaMenu label="商品" to="/products">
          <div class="mega-products">
            <!-- 依系列 -->
            <div class="mega-col">
              <h4 class="mega-heading">依系列</h4>
              <ul
                v-if="(seriesQuery.data.value?.items.length ?? 0) > 0"
                class="mega-list"
              >
                <li
                  v-for="s in seriesQuery.data.value?.items.slice(0, SERIES_LIMIT)"
                  :key="s.id"
                >
                  <RouterLink :to="`/products?series_id=${s.id}`">{{ s.name }}</RouterLink>
                </li>
              </ul>
              <p v-else class="mega-col-empty">建設中</p>
            </div>

            <!-- 依標籤 -->
            <div class="mega-col">
              <h4 class="mega-heading">依標籤</h4>
              <ul
                v-if="(tagsQuery.data.value?.items.length ?? 0) > 0"
                class="mega-list"
              >
                <li
                  v-for="tag in tagsQuery.data.value?.items.slice(0, TAGS_LIMIT)"
                  :key="tag.id"
                >
                  <RouterLink :to="`/products?tag_id=${tag.id}`">{{ tag.name }}</RouterLink>
                </li>
              </ul>
              <p v-else class="mega-col-empty">建設中</p>
            </div>

            <!-- 依難易度（寫死 4 個） -->
            <div class="mega-col">
              <h4 class="mega-heading">依難易度</h4>
              <ul class="mega-list">
                <li v-for="d in DIFFICULTIES" :key="d.code">
                  <RouterLink :to="`/products?difficulty=${d.code}`">{{ d.label }}</RouterLink>
                </li>
              </ul>
            </div>
          </div>
          <div class="mega-footer">
            <RouterLink to="/products" class="mega-cta">前往全部商品 →</RouterLink>
          </div>
        </MegaMenu>

        <MegaMenu label="主題" to="/themes">
          <!-- 精選系列（admin 勾選 is_featured 的系列）-->
          <div
            v-if="(featuredSeriesQuery.data.value?.items.length ?? 0) > 0"
            class="mega-featured"
          >
            <h4 class="mega-heading">精選系列</h4>
            <div class="featured-chips">
              <RouterLink
                v-for="s in featuredSeriesQuery.data.value?.items.slice(0, FEATURED_SERIES_LIMIT)"
                :key="s.id"
                :to="`/series/${s.id}`"
                class="featured-chip"
              >
                {{ s.name }}
              </RouterLink>
            </div>
          </div>

          <!-- 所有主題 -->
          <div v-if="themesQuery.isPending.value" class="mega-empty">
            主題載入中⋯
          </div>
          <div v-else-if="themesQuery.isError.value" class="mega-empty">
            主題載入失敗
          </div>
          <div v-else-if="(themesQuery.data.value?.items.length ?? 0) === 0" class="mega-empty">
            主題建設中，敬請期待
          </div>
          <div v-else>
            <h4
              v-if="(featuredSeriesQuery.data.value?.items.length ?? 0) > 0"
              class="mega-heading mega-heading-spaced"
            >所有主題</h4>
            <div class="mega-grid mega-themes">
              <RouterLink
                v-for="theme in themesQuery.data.value?.items"
                :key="theme.id"
                :to="`/themes/${theme.id}`"
                class="mega-theme"
              >
                <span class="theme-name">{{ theme.name }}</span>
                <span class="theme-meta">{{ theme.series_count }} 系列 · {{ theme.product_count }} 件商品</span>
              </RouterLink>
            </div>
          </div>
        </MegaMenu>

        <RouterLink to="/custom" class="nav-link">客製</RouterLink>
        <RouterLink to="/size-guide" class="nav-link">尺寸指南</RouterLink>
      </nav>

      <SiteLogo size="md" />

      <div class="site-actions">
        <IconButton to="/search" aria-label="搜尋"><Search /></IconButton>
        <IconButton to="/profile" aria-label="會員"><User /></IconButton>
        <IconButton to="/cart" aria-label="購物車"><ShoppingBag /></IconButton>
      </div>
    </div>

    <MobileMenu :open="mobileOpen" @close="mobileOpen = false" />
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(247, 241, 226, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-line-subtle);
}

.site-header-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 20px 56px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 32px;
}

.site-nav.desktop {
  display: flex;
  gap: 36px;
  align-items: center;
}

.nav-link {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-default);
  text-decoration: none;
  padding: 8px 0;
  transition: color 150ms;
}

.nav-link:hover {
  color: var(--color-accent);
}

.site-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}

.mobile-trigger {
  display: none;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.mobile-trigger:hover { background: var(--color-paper-deep); }
.mobile-trigger :deep(svg) {
  width: 22px; height: 22px; stroke-width: 1.5; fill: none; stroke: currentColor;
}

/* Mega-menu panel content */
.mega-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

.mega-themes {
  grid-template-columns: repeat(2, 1fr);
}

.mega-products {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
  min-width: 540px;
}

.mega-footer {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-line-subtle);
  text-align: right;
}

.mega-col-empty {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}

.mega-col { min-width: 120px; }

.mega-heading {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 400;
  margin-bottom: 12px;
}

.mega-list { list-style: none; padding: 0; margin: 0; }
.mega-list li { margin-bottom: 8px; }
.mega-list a {
  font-family: var(--font-cn-serif);
  font-size: 14px;
  color: var(--color-ink-default);
  text-decoration: none;
  letter-spacing: 0.04em;
  transition: color 150ms;
}
.mega-list a:hover { color: var(--color-accent); }

.mega-cta {
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  display: inline-block;
  padding-top: 4px;
}

.mega-theme {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  text-decoration: none;
  border-radius: var(--radius-xs);
  transition: background 150ms;
}
.mega-theme:hover { background: var(--color-paper-deep); }

.theme-name {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
}

.theme-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
}

.mega-empty {
  font-size: 13px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  padding: 8px 4px;
}

.mega-featured {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-line-subtle);
}

.mega-heading-spaced {
  margin-top: 0;
}

.featured-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.featured-chip {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  text-decoration: none;
  padding: 6px 14px;
  border: 1px solid var(--color-line);
  border-radius: 999px;
  transition: all 150ms;
}

.featured-chip:hover {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: var(--color-paper-canvas);
}

/* Responsive */
@media (max-width: 1023px) {
  .site-header-inner {
    padding: 16px 24px;
    grid-template-columns: auto 1fr auto;
    gap: 16px;
  }
  .site-nav.desktop { display: none; }
  .mobile-trigger { display: inline-flex; }
  .site-actions :deep(.icon-btn:not(:last-child)) { display: none; }
}

@media (max-width: 767px) {
  .site-header-inner {
    padding: 14px 20px;
  }
}
</style>
