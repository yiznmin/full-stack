<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { X, Search, User, ShoppingBag } from 'lucide-vue-next'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const route = useRoute()

// Close drawer when route changes
watch(
  () => route.fullPath,
  () => {
    if (props.open) emit('close')
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer-overlay">
      <div v-if="open" class="overlay" @click="emit('close')" />
    </Transition>
    <Transition name="drawer-panel">
      <aside v-if="open" class="panel" role="dialog" aria-label="導覽選單">
        <div class="panel-header">
          <span class="panel-title">易木 YIIMUI</span>
          <button class="close-btn" aria-label="關閉選單" @click="emit('close')">
            <X />
          </button>
        </div>

        <nav class="panel-nav">
          <RouterLink to="/products" class="panel-link">商品</RouterLink>
          <RouterLink to="/themes" class="panel-link">主題</RouterLink>
          <RouterLink to="/custom" class="panel-link">客製</RouterLink>
          <div class="panel-sublinks">
            <RouterLink to="/custom/apply" class="panel-sublink">申請表單</RouterLink>
            <RouterLink to="/custom/cases" class="panel-sublink">案例分享</RouterLink>
            <RouterLink to="/custom/about" class="panel-sublink">關於客製化服務</RouterLink>
          </div>
          <RouterLink to="/help" class="panel-link">購物說明</RouterLink>
        </nav>

        <div class="panel-divider" />

        <nav class="panel-actions">
          <RouterLink to="/search" class="action-link">
            <Search />
            <span>搜尋</span>
          </RouterLink>
          <RouterLink to="/profile" class="action-link">
            <User />
            <span>會員</span>
          </RouterLink>
          <RouterLink to="/cart" class="action-link">
            <ShoppingBag />
            <span>購物車</span>
          </RouterLink>
        </nav>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(46, 40, 35, 0.4);
  z-index: 90;
}

.panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(360px, 90vw);
  background: var(--color-paper-canvas);
  border-left: 1px solid var(--color-line-subtle);
  z-index: 91;
  display: flex;
  flex-direction: column;
  padding: 20px 0;
}

.panel-header {
  padding: 8px 24px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-line-subtle);
}

.panel-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.12em;
  color: var(--color-ink-strong);
}

.close-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.close-btn:hover { background: var(--color-paper-deep); }
.close-btn :deep(svg) { width: 18px; height: 18px; stroke-width: 1.5; fill: none; stroke: currentColor; }

.panel-nav {
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}

.panel-link {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  text-decoration: none;
  padding: 14px 24px;
  transition: background 150ms, color 150ms;
}
.panel-link:hover {
  background: var(--color-paper-deep);
  color: var(--color-accent);
}

.panel-sublinks {
  display: flex; flex-direction: column;
  padding: 0 24px 8px 40px;
  border-left: 1px solid var(--color-line-subtle);
  margin-left: 24px;
}
.panel-sublink {
  font-family: var(--font-cn-serif);
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  text-decoration: none;
  padding: 8px 0;
  transition: color 150ms;
}
.panel-sublink:hover { color: var(--color-accent-deep); }

.panel-divider {
  height: 1px;
  background: var(--color-line-subtle);
  margin: 8px 24px;
}

.panel-actions {
  display: flex;
  flex-direction: column;
  padding: 8px 0;
}

.action-link {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  text-decoration: none;
  color: var(--color-ink-default);
  font-size: 13px;
  letter-spacing: 0.06em;
  transition: background 150ms;
}
.action-link:hover { background: var(--color-paper-deep); }
.action-link :deep(svg) {
  width: 18px;
  height: 18px;
  stroke-width: 1.5;
  fill: none;
  stroke: currentColor;
  color: var(--color-ink-muted);
}

/* Animations */
.drawer-overlay-enter-active,
.drawer-overlay-leave-active {
  transition: opacity 200ms ease;
}
.drawer-overlay-enter-from,
.drawer-overlay-leave-to {
  opacity: 0;
}

.drawer-panel-enter-active,
.drawer-panel-leave-active {
  transition: transform 240ms ease;
}
.drawer-panel-enter-from,
.drawer-panel-leave-to {
  transform: translateX(100%);
}
</style>
