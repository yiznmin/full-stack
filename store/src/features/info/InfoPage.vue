<script setup lang="ts">
import { computed, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useTitle } from '@vueuse/core'
import { Loader2, AlertCircle } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import { fetchPage, type InfoSlug } from './api'
import { renderMarkdown } from './renderMarkdown'

const props = defineProps<{
  slug: InfoSlug
  no: string
  chapter: string
  fallbackTitle: string
  caption?: string
}>()

const pageQuery = useQuery({
  queryKey: computed(() => ['info-page', props.slug] as const),
  queryFn: () => fetchPage(props.slug),
  staleTime: 10 * 60 * 1000, // 靜態頁，10 分鐘 stale
})

const title = computed(() => pageQuery.data.value?.title ?? props.fallbackTitle)

// SEO — 設定 document.title；meta description 取 markdown 第一段純文字（< 160 字）
useTitle(computed(() => `${title.value}｜易木 YIIMUI`))

watch(
  () => pageQuery.data.value?.content,
  (md) => {
    if (typeof document === 'undefined') return
    const desc = md
      ? md
          .replace(/^#+\s.*$/gm, '')
          .replace(/[*`>\-|]/g, '')
          .replace(/\s+/g, ' ')
          .trim()
          .slice(0, 155)
      : `易木 YIIMUI ${title.value}說明頁面。`
    let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    if (!tag) {
      tag = document.createElement('meta')
      tag.name = 'description'
      document.head.appendChild(tag)
    }
    tag.content = desc
  },
  { immediate: true },
)
const html = computed(() =>
  pageQuery.data.value ? renderMarkdown(pageQuery.data.value.content) : '',
)
const updatedAt = computed(() => {
  const ts = pageQuery.data.value?.updated_at
  if (!ts) return null
  try {
    return new Date(ts).toLocaleDateString('zh-TW', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return null
  }
})
</script>

<template>
  <main class="page">
    <SectionMasthead
      :no="no"
      :chapter="chapter"
      :title="title"
      :caption="caption"
    />

    <div v-if="pageQuery.isLoading.value" class="state">
      <Loader2 class="spin" />
      <span>載入中…</span>
    </div>

    <div v-else-if="pageQuery.isError.value" class="state error">
      <AlertCircle :size="16" />
      <span>無法載入內容，請稍後再試。</span>
    </div>

    <article v-else class="prose" v-html="html" />

    <p v-if="updatedAt" class="meta">最後更新：{{ updatedAt }}</p>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 64px 56px 96px;
}

.state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  color: var(--color-ink-muted);
  font-size: 13px;
}
.state.error { color: var(--color-state-danger); }
.spin {
  width: 16px; height: 16px; stroke-width: 1.5;
  animation: spin 900ms linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.meta {
  margin-top: 48px;
  padding-top: 16px;
  border-top: 1px solid var(--color-line-subtle);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
  text-transform: uppercase;
}

/* Markdown 渲染樣式 — 使用 :deep 因為 v-html 內容不被 scoped 影響 */
.prose :deep(h1) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 48px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.prose :deep(h1:first-child) { margin-top: 0; }

.prose :deep(h2) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 19px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 36px 0 12px;
}
.prose :deep(h2:first-child) { margin-top: 0; }

.prose :deep(h3) {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 24px 0 10px;
}

.prose :deep(p) {
  font-size: 14px;
  line-height: 2;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 0 0 14px;
}

.prose :deep(strong) {
  font-weight: 500;
  color: var(--color-ink-strong);
}

.prose :deep(em) {
  font-style: italic;
  color: var(--color-accent);
}

.prose :deep(a) {
  color: var(--color-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--color-accent);
  padding-bottom: 1px;
  transition: color 150ms;
}
.prose :deep(a:hover) { color: var(--color-accent-deep); }

.prose :deep(ul),
.prose :deep(ol) {
  padding-left: 24px;
  margin: 0 0 16px;
}
.prose :deep(li) {
  font-size: 14px;
  line-height: 1.9;
  letter-spacing: 0.04em;
  color: var(--color-ink-default);
  margin: 4px 0;
}
.prose :deep(ul) { list-style: none; }
.prose :deep(ul > li) { position: relative; }
.prose :deep(ul > li::before) {
  content: '';
  position: absolute;
  left: -16px;
  top: 0.85em;
  width: 6px;
  height: 1px;
  background: var(--color-accent);
}

.prose :deep(blockquote) {
  margin: 24px 0;
  padding: 16px 20px;
  background: var(--color-paper-deep);
  border-left: 2px solid var(--color-accent);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}
.prose :deep(blockquote p) {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0;
}

.prose :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 2px 6px;
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
  color: var(--color-ink-strong);
}

.prose :deep(.md-table-wrap) {
  margin: 20px 0;
  overflow-x: auto;
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
}
.prose :deep(.md-table) {
  width: 100%;
  min-width: 480px;
  border-collapse: collapse;
  font-size: 13px;
}
.prose :deep(.md-table th) {
  background: var(--color-paper-deep);
  text-align: left;
  padding: 12px 14px;
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  border-bottom: 1px solid var(--color-line);
}
.prose :deep(.md-table td) {
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-line-subtle);
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}
.prose :deep(.md-table tr:last-child td) { border-bottom: none; }

@media (max-width: 767px) {
  .page { padding: 40px 24px 64px; }
  .prose :deep(h1) { font-size: 21px; }
  .prose :deep(h2) { font-size: 17px; }
  .prose :deep(h3) { font-size: 14px; }
}
</style>
