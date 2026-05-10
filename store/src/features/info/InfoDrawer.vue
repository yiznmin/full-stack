<script setup lang="ts">
// 右側資訊抽屜 — 用在「決策當下」場景：
//   - 產品頁尺寸選擇器旁 → 尺寸指南
//   - 客製申請頁 → 報價參考
//   - 購物車運費旁 → 出貨流程
//   - 訂單頁退款旁 → 退款政策
// 直接 reuse fetchPage + renderMarkdown，沒有額外後端負擔。
import { computed, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Loader2, AlertCircle, X } from 'lucide-vue-next'
import { fetchPage, type InfoSlug } from './api'
import { renderMarkdown } from './renderMarkdown'

const props = defineProps<{
  open: boolean
  slug: InfoSlug
  title: string
  fullPagePath: string
}>()

const emit = defineEmits<{ close: [] }>()

const pageQuery = useQuery({
  queryKey: computed(() => ['info-page', props.slug] as const),
  queryFn: () => fetchPage(props.slug),
  staleTime: 10 * 60 * 1000,
  enabled: computed(() => props.open),
})

const html = computed(() =>
  pageQuery.data.value ? renderMarkdown(pageQuery.data.value.content) : '',
)

// ESC 關閉 + 鎖背景捲動
watch(
  () => props.open,
  (isOpen) => {
    if (typeof window === 'undefined') return
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', onKeydown)
    } else {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKeydown)
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer-overlay">
      <div v-if="open" class="overlay" @click="emit('close')" />
    </Transition>
    <Transition name="drawer-panel">
      <aside v-if="open" class="panel" role="dialog" :aria-label="title">
        <header class="head">
          <div class="head-text">
            <span class="eyebrow">Reference</span>
            <h2 class="head-title">{{ title }}</h2>
          </div>
          <button type="button" class="close-btn" aria-label="關閉" @click="emit('close')">
            <X :size="18" />
          </button>
        </header>

        <div class="body">
          <div v-if="pageQuery.isLoading.value" class="state">
            <Loader2 class="spin" />
            <span>載入中…</span>
          </div>
          <div v-else-if="pageQuery.isError.value" class="state error">
            <AlertCircle :size="14" />
            <span>無法載入內容</span>
          </div>
          <article v-else class="prose" v-html="html" />
        </div>

        <footer class="foot">
          <RouterLink :to="fullPagePath" class="full-link" @click="emit('close')">
            看完整內容 →
          </RouterLink>
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(46, 40, 35, 0.4);
  z-index: 90;
}

.panel {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: min(420px, 92vw);
  background: var(--color-paper-canvas);
  border-left: 1px solid var(--color-line-subtle);
  z-index: 91;
  display: flex;
  flex-direction: column;
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 28px 20px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.head-text { display: flex; flex-direction: column; gap: 6px; }
.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-fresh);
  font-weight: 500;
}
.head-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 20px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}

.close-btn {
  width: 36px; height: 36px;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-muted);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 150ms, color 150ms;
}
.close-btn:hover {
  background: var(--color-paper-deep);
  color: var(--color-ink-strong);
}
.close-btn :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

.body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px 40px;
}

.state {
  display: flex; align-items: center; gap: 8px;
  padding: 32px 0;
  color: var(--color-ink-muted);
  font-size: 13px;
}
.state.error { color: var(--color-state-danger); }
.spin {
  width: 14px; height: 14px; stroke-width: 1.5;
  animation: spin 900ms linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.foot {
  border-top: 1px solid var(--color-line-subtle);
  padding: 16px 28px;
  background: var(--color-paper-surface);
}
.full-link {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 3px;
  transition: color 150ms, border-color 150ms;
}
.full-link:hover {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

/* Markdown — 沿用 InfoPage 的樣式但稍微壓縮（drawer 寬度較窄） */
.prose :deep(h1) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.prose :deep(h1:first-child) { margin-top: 0; }
.prose :deep(h2) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 24px 0 10px;
}
.prose :deep(h2:first-child) { margin-top: 0; }
.prose :deep(h3) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 18px 0 8px;
}
.prose :deep(p) {
  font-size: 13px;
  line-height: 1.85;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 0 0 12px;
}
.prose :deep(strong) { font-weight: 500; color: var(--color-ink-strong); }
.prose :deep(em) { font-style: italic; color: var(--color-accent); }
.prose :deep(a) {
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
}
.prose :deep(ul), .prose :deep(ol) {
  padding-left: 20px;
  margin: 0 0 12px;
}
.prose :deep(li) {
  font-size: 13px;
  line-height: 1.85;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
}
.prose :deep(ul) { list-style: none; }
.prose :deep(ul > li) { position: relative; }
.prose :deep(ul > li::before) {
  content: '';
  position: absolute;
  left: -14px;
  top: 0.85em;
  width: 5px;
  height: 1px;
  background: var(--color-accent);
}
.prose :deep(blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  background: var(--color-paper-deep);
  border-left: 2px solid var(--color-accent);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}
.prose :deep(blockquote p) {
  font-size: 12px;
  color: var(--color-ink-muted);
  margin: 0;
}
.prose :deep(.md-table-wrap) {
  margin: 14px 0;
  overflow-x: auto;
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.prose :deep(.md-table) {
  width: 100%;
  min-width: 320px;
  border-collapse: collapse;
  font-size: 12px;
}
.prose :deep(.md-table th) {
  background: var(--color-paper-deep);
  text-align: left;
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  border-bottom: 1px solid var(--color-line);
}
.prose :deep(.md-table td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-line-subtle);
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.prose :deep(.md-table tr:last-child td) { border-bottom: none; }
.prose :deep(code) {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 5px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
  color: var(--color-ink-strong);
}

/* Animations */
.drawer-overlay-enter-active,
.drawer-overlay-leave-active { transition: opacity 200ms ease; }
.drawer-overlay-enter-from,
.drawer-overlay-leave-to { opacity: 0; }

.drawer-panel-enter-active,
.drawer-panel-leave-active { transition: transform 240ms ease; }
.drawer-panel-enter-from,
.drawer-panel-leave-to { transform: translateX(100%); }
</style>
