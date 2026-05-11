// useSeo — 動態更新單頁 SEO meta tags
// 用法：在 <script setup> 內呼叫 useSeo({ title, description, ogImage, jsonLd })
// 會自動：
//   - <title>
//   - <meta name="description">
//   - og:title / og:description / og:url / og:image
//   - twitter:title / twitter:description / twitter:image
//   - <script type="application/ld+json"> （optional，per-page Product schema 等）
//
// canonical 由 router.afterEach 統一處理（每次切頁都對齊 current path）。
import { watchEffect, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

interface SeoOptions {
  title?: string
  description?: string
  ogImage?: string
  /** 完整 JSON-LD 物件（或 array），會以 <script type="application/ld+json"> 注入 head，離開頁面時自動移除 */
  jsonLd?: Record<string, unknown> | Array<Record<string, unknown>>
}

const SITE_NAME = '易木 YIIMUI'
const SITE_URL = 'https://yiimui.com'
const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`

function setMeta(selector: string, attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

export function useSeo(opts: () => SeoOptions) {
  const route = useRoute()
  const jsonLdEls: HTMLScriptElement[] = []

  watchEffect(() => {
    const o = opts()
    const fullTitle = o.title ? `${o.title}｜${SITE_NAME}` : `${SITE_NAME} · 客製化數字油畫`
    const desc = o.description || '台灣客製化數字油畫平台 — 上傳照片轉成編號油畫模板。'
    const ogImg = o.ogImage || DEFAULT_OG_IMAGE
    const url = `${SITE_URL}${route.fullPath}`

    document.title = fullTitle
    setMeta('meta[name="description"]', 'name', 'description', desc)
    setMeta('meta[property="og:title"]', 'property', 'og:title', fullTitle)
    setMeta('meta[property="og:description"]', 'property', 'og:description', desc)
    setMeta('meta[property="og:url"]', 'property', 'og:url', url)
    setMeta('meta[property="og:image"]', 'property', 'og:image', ogImg)
    setMeta('meta[name="twitter:title"]', 'name', 'twitter:title', fullTitle)
    setMeta('meta[name="twitter:description"]', 'name', 'twitter:description', desc)
    setMeta('meta[name="twitter:image"]', 'name', 'twitter:image', ogImg)

    // 清掉舊的 page-level JSON-LD，重新注入新的
    jsonLdEls.forEach((el) => el.remove())
    jsonLdEls.length = 0
    if (o.jsonLd) {
      const items = Array.isArray(o.jsonLd) ? o.jsonLd : [o.jsonLd]
      for (const item of items) {
        const s = document.createElement('script')
        s.type = 'application/ld+json'
        s.setAttribute('data-page-seo', '1')
        s.textContent = JSON.stringify(item)
        document.head.appendChild(s)
        jsonLdEls.push(s)
      }
    }
  })

  onUnmounted(() => {
    jsonLdEls.forEach((el) => el.remove())
  })
}
