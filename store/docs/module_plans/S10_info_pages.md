# S10 — 資訊頁（5 個靜態頁）

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #25–29、規格見 [docs/requirements/store/store_info.md](../../../docs/requirements/store/store_info.md)。
> 後端 API 由 `backend/content` 模組提供（[router.py:45](../../../backend/content/router.py)）。
>
> **追溯規劃書**：本模組已先實作（commit `58e19ed` / `1ce415e` / 此 commit），事後對照 SOP 補寫規劃書 + 規格比對。後續修正項見最末「事後修正」段落。

---

## 1. 範圍

5 個 placeholder 頁改成從 `GET /pages/{slug}` 取 markdown 內容、用共用元件渲染。

| Brief # | 頁面 | URL | slug |
|---|---|---|---|
| #25 | 尺寸指南 | `/size-guide` | `size_guide` |
| #26 | 出貨流程 | `/shipping-info` | `shipping` |
| #27 | 訂製流程 | `/custom-process` | `custom_process` |
| #28 | 報價參考 | `/pricing` | `pricing_reference` |
| #29 | 退款退貨政策 | `/refund-policy` | `refund_policy` |

---

## 2. 檔案清單

```
store/src/features/info/
├── api.ts                  # fetchPage(slug) — fetch /api/v1/pages/{slug}
├── renderMarkdown.ts       # 純前端 markdown parser（無依賴）
└── InfoPage.vue            # 共用元件（SectionMasthead + 渲染 + meta）

store/src/features/pages/
├── SizeGuidePage.vue       # → <InfoPage slug="size_guide" no="01" />
├── ShippingInfoPage.vue
├── CustomProcessPage.vue
├── PricingPage.vue
└── RefundPolicyPage.vue

backend/scripts/
└── seed_pages_remote.py    # 一次性 seed remote DB 5 個 page（冪等）
```

---

## 3. API

| Endpoint | Method | 說明 |
|---|---|---|
| `/api/v1/pages/{slug}` | GET | 公開取單一 page，404 = 該 slug 未 seed |

**Response**：`{ slug, title, content, updated_at }`，content 是 markdown。

來源：[backend/content/router.py:45-50](../../../backend/content/router.py#L45-L50)、[backend/content/schemas/response.py](../../../backend/content/schemas/response.py)

---

## 4. 元件樹

```
<InfoPage slug no chapter fallbackTitle caption?>
├─ <SectionMasthead no chapter title caption />
├─ Loading state（Loader2 + 「載入中…」）
├─ Error state（AlertCircle + 「無法載入內容，請稍後再試。」）
├─ <article v-html="renderMarkdown(content)">  ← markdown 渲染區
└─ <p class="meta">最後更新：{{ updatedAt }}</p>
```

5 個 page 各自只是 1-行 wrapper：傳 slug + masthead 編號（01–05）+ chapter 標籤。

---

## 5. 設計決策

引用 [design_system.md](../design_system.md)：

| 元素 | Token / Rule | 為什麼 |
|---|---|---|
| 頁面 max-width | 880px | 編輯誌長文閱讀寬度（與 admin 後台不同）|
| 頁面 padding 桌面 | 64px | §4 頁面外距桌面 ≥ 1024：56–64px |
| 頁面 padding mobile | 24px | §4 頁面外距 mobile：24px |
| Section header | `<SectionMasthead>` | §8 規格：eyebrow + 大標 + line 三層結構 |
| h1 字體 | `--font-cn-serif` weight 300 letter-spacing 0.06em size 24 | §2 text-h1 規格 |
| h2 字體 | `--font-cn-serif` weight 300 size 19 | §2 + §1 紀律「中文標題不超 weight 500」 |
| h3 字體 | `--font-cn-serif` weight 300 size 15 | 同上 |
| body | `--color-ink-default` 14 / line-height 2 letter-spacing 0.04em | §2 text-body 接近（store 比 admin 鬆）|
| 強調色 | `--color-accent` (em / link) / `--color-fresh`（無）| §3 整站只一個 accent |
| Table | `--color-line-subtle` 1px 邊 + `--radius-xs` 2px | §5 圓角 ≤ 4px、§3.1 line-subtle 兩階分線 |
| Blockquote | `--color-accent` 2px left border + `--color-paper-deep` 底 | §3.1 paper-deep 是 band 高亮層 |
| 載入更新時間 | `--font-mono` 11px letter-spacing 0.16em uppercase | §2 text-num-mono |

**禁區遵循**：
- ✅ 無紙紋 noise
- ✅ 只用一個 accent（walnut）
- ✅ 圓角 ≤ 4px（直角紙感）
- ✅ 中文標題 weight 300（修正後）
- ✅ 1px hairline 分線

---

## 6. 後端依賴

DB 必須有對應 5 個 slug。生產 DB 透過 [seed_pages_remote.py](../../../backend/scripts/seed_pages_remote.py) 冪等寫入；本地透過 [seed_content.py](../../../backend/scripts/seed_content.py)。

來源：[backend/scripts/seed_content.py:46-146](../../../backend/scripts/seed_content.py#L46-L146)

---

## 7. 手動驗收（pending — 待補做）

- [ ] 5 個 URL 都能 200 載入內容
- [ ] markdown 渲染正確（標題、列表、表格、blockquote、粗斜體、連結）
- [ ] 移動端 24px padding、表格 horizontal scroll 不壓縮
- [ ] Console 0 error / 0 warn
- [ ] Network 都是 200，無未預期 401
- [ ] document.title 正確設定（SEO）
- [ ] Lighthouse Accessibility ≥ 90

---

## 8. 事後修正項（已發現、待修）

對照 design_system 後發現的偏差：

| 偏差 | 規格 | 實作 | 修正動作 |
|---|---|---|---|
| h2 weight 400 | weight 300 | `font-weight: 400` | 改 300 |
| h3 weight 500 | weight 300 | `font-weight: 500` | 改 300 |
| token `--color-paper-subtle` 不存在 | 應用 paper-deep 或 paper-surface | fallback 寫法 | 直接用 paper-deep |
| 元件命名 InfoPage | 規格寫 `<MarkdownPage>` | InfoPage.vue | 保留 InfoPage（更語意化、限定為資訊頁；MarkdownPage 為通用元件名稱，但目前只有資訊頁一處用） |
| SEO meta 缺 | document.title + meta description | 無 | 加 useTitle hook（@vueuse/core 已裝）|
| commit 格式 | `feat(store/<module>): 完成 SXX - <模組名稱>` | `feat(store/info): 5 個...` | 後續 commit 用正確格式 |
