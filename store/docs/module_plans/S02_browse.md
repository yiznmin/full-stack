# S02 — 商品瀏覽

> 後端對應：`backend/product/`（GET /products, /products/search, /products/:id, /products/:id/related, /themes, /series, /tags）
> 規格來源：[docs/api.md](../../../docs/api.md)、[docs/store_design_brief.md](../../../docs/store_design_brief.md) #1–#4
> 設計依據：[design_system.md](../design_system.md)
> SOP：[frontend_sop.md](../frontend_sop.md)

---

## 1. 範圍

### 本模組做

1. **HomePage `/`**（brief #1）
   - Hero（大標 + 副文 + CTA）
   - 最新上架（4 商品卡）— GET /products?sort=latest&page_size=4
   - 主題瀏覽（4 主題卡橫向）— GET /themes (取前 4)
   - 精選系列（chips 橫向）— GET /series?featured=true
   - 三個分類入口（依難易度 / 依主題 / 依標籤 — 用戶角度修正：拿掉細緻度）
   - 客製化 banner

2. **ProductListPage `/products`**（brief #2）
   - 左欄篩選器（主題 / 系列 / 難易度 / 細緻度 / 尺寸 / 標籤）
   - 商品卡網格（4 col 桌面 / 2 col 平板 / 1 col 手機）
   - 排序（最新 / 熱門 / 價格升降）
   - 分頁（24 筆/頁）
   - URL query 同步（`?theme_id=&difficulty=&sort=&page=`）

3. **SearchPage `/search`**（brief #3）
   - 與 ProductListPage 共用元件（同 grid + 同分頁）
   - title 改「搜尋結果：{q}」
   - GET /products/search?q=

4. **ProductDetailPage `/products/:id`**（brief #4）
   - 圖片輪播（封面 + product_images，選定變體後加 filled_template）
   - 規格三層級選擇器（尺寸 → 難易度 → 細緻度），無對應變體灰階禁用
   - 價格、庫存（現貨 / 預購標示）
   - 加購車按鈕（暫顯 toast「即將上線」— S05 補加購邏輯）
   - 同系列商品橫列 — GET /products/:id/related
   - 商品說明摺疊區（畫具內容 / 畫布材質 / 使用建議 / 注意事項，4 區）— **內容由 admin product description Markdown 提供，無內容時不顯示該段**
   - 「想要不同規格？」展開區塊 link 到 `/custom`（屬 S07 細節）

5. **修補 S01 SiteHeader bug**：
   - 依難易度 mega-menu 4 個連結：`basic` enum 錯誤 → 改 `elementary`（backend 實 enum）

### 不做

- 加購車實際邏輯（屬 S05）— 按鈕只顯 toast「即將上線」
- 商品評論 / 收藏（brief 明令禁）
- 客製規格表單送出（屬 S07）— 詳情頁只放 link
- 變體圖片庫（每變體獨立 filled_template_url 已在 PublicVariantResponse，但詳情頁圖片輪播 v1 只放固定的 product_images，不依變體切圖）— 屬 S02 enhancement，先放佔位

---

## 2. 路由

| Path | Component | Layout | Guard | 備註 |
|---|---|---|---|---|
| `/` | HomePage | DefaultLayout | — | 取代現有 placeholder |
| `/products` | ProductListPage | DefaultLayout | — | URL query 同步 |
| `/products/:id` | ProductDetailPage | DefaultLayout | — | — |
| `/search` | SearchPage | DefaultLayout | — | `?q=` required，無 q → 重導 `/products` |

---

## 3. 後端 API 對應

來源 [backend/product/router.py:53-105](../../../backend/product/router.py#L53-L105)：

| Endpoint | Query | Response | 用於 |
|---|---|---|---|
| `GET /products` | difficulty (beginner/elementary/intermediate/advanced)<br>detail (rough/standard/detailed/premium)<br>canvas_size (WxH e.g. 30x40)<br>tag_id, series_id, theme_id (UUID)<br>sort (latest/popular/price_asc/price_desc)<br>page (≥1), page_size (1–100, default 24) | PublicProductListResponse `{items, total, page, page_size}` 每筆 PublicProductBrief `{id, title, cover_image_url, difficulty_range, price_min, price_max, is_preorder}` | HomePage 最新上架 / ProductListPage |
| `GET /products/search` | q (min 1 char), page, page_size | 同上 | SearchPage |
| `GET /products/:id` | — | PublicProductDetailResponse `{id, title, description, cover_image_url, images, series, tags, variants}` | ProductDetailPage |
| `GET /products/:id/related` | — | RelatedProductsResponse `{series, items}` | ProductDetailPage 同系列推薦 |
| `GET /themes` | — | (S01 已用) | HomePage 主題瀏覽 |
| `GET /series?featured=true` | — | (S01 已用) | HomePage 精選系列 |
| `GET /tags` | — | (S01 已用) | ProductListPage 篩選器 |

⚠️ **Backend enum 校正**：
- difficulty: `beginner`、`elementary`、`intermediate`、`advanced`（S01 mega-menu 寫成 `basic` ❌ → 改 `elementary`）
- detail: `rough`、`standard`、`detailed`、`premium`（S01 mega-menu 寫成 `fine` 但已拿掉那欄，不影響）

---

## 4. 元件樹

```
src/features/home/
├── components/
│   ├── HomeHero.vue                     # hero 大標 + CTA + 攝影
│   ├── LatestProductsSection.vue        # 最新上架 4 卡片
│   ├── ThemesCarousel.vue               # 主題卡片橫向（共用 ThemeCard）
│   ├── FeaturedSeriesSection.vue        # 精選系列 chips
│   ├── CategoryEntries.vue              # 3 入口（難易度 / 主題 / 標籤）
│   └── CustomBanner.vue                 # 客製化 banner
└── pages/HomePage.vue                   # 組合所有 sections（取代現有 placeholder）

src/features/products/
├── api.ts                               # listProducts, searchProducts, getProduct, getRelated
├── queries.ts                           # useProductsQuery, useProductDetailQuery 等
├── components/
│   ├── ProductCard.vue                  # 共用商品卡（design_system §8）
│   ├── ProductGrid.vue                  # 4 col grid + responsive
│   ├── ProductFilter.vue                # 左欄篩選（5 段 collapsible）
│   ├── ProductSort.vue                  # 排序 dropdown
│   ├── Pagination.vue                   # 分頁元件
│   ├── ProductGallery.vue               # 詳情頁圖片輪播
│   ├── VariantSelector.vue              # 三層級規格選擇器
│   ├── ProductDescription.vue           # 4 區摺疊（畫具內容 / 畫布材質 / 使用建議 / 注意事項）
│   └── EmptyState.vue                   # 空狀態（無商品 / 無搜尋結果）
└── pages/
    ├── ProductListPage.vue              # 取代 placeholder
    ├── ProductDetailPage.vue            # 取代 placeholder
    └── SearchPage.vue                   # 取代 placeholder

src/features/themes/components/
└── ThemeCard.vue                        # 主題卡（HomePage 與後續 S03 共用）

src/shared/components/
├── Toast.vue                            # 全站 toast（加購車 placeholder 用）
└── Loader.vue                           # 載入指示器
```

---

## 5. 設計決策（引 design_system.md）

### 商品卡（ProductCard）
完全依 [design_system.md §8 Product Card](../design_system.md#product-card)：
- paper-surface 底 + 1px line-subtle 邊
- 圖佔上半部 4:5 + 1px hairline 底邊
- product-body 內距 22px
- 順序：No. 編號（mono）→ 商品標題（h3 Noto Serif TC weight 300 size 20）→ meta（uppercase）→ 1px hairline → 價格 row（label「售價」上 / 價格下）
- hover：邊框換 line + box-shadow 4px blur 6% alpha + 圖片 scale 1.03 + brightness 1.05

### Hero 攝影策略
- 4:5 aspect-ratio
- sepia 0.04 saturate 0.95（[design_system §6](../design_system.md#攝影策略)）
- 圖片來源：v1 用 placeholder（picsum-like 或 backend cover_image_url 取最新一筆）；後續 admin 後台可加「Hero 推薦商品」設定（屬 future enhancement）

### 篩選器 UI
- 左欄寬 240px，桌面 sticky
- 5 段 collapsible：主題、系列、難易度、細緻度、尺寸、標籤
- 每段顯示「全部」+ 該分類的選項（chip 或 list）
- 選中時 chip 背景換 accent-tint
- mobile（< 1024）篩選改為頂部抽屜（漢堡按鈕觸發）

### 規格選擇器（VariantSelector）
- 三層級依序：尺寸 → 難易度 → 細緻度（從 product.variants 推導可用組合）
- 每層用 chips 排列
- 上層改變後下層 reset + 重新計算可用值
- 無對應變體 → chip 灰階 disabled（不消失）
- 全選後顯示：售價、預覽圖（filled_template_url）、庫存（現貨 / 預購）

### 動效
- HomePage 進場：sections stagger fade-in 180ms each
- 商品卡 hover：sepia 0.07 saturate 0.92 + brightness 1.05（200ms transform 600ms）
- 圖片輪播：crossfade 240ms

### 響應式
- ≥ 1280: 商品 grid 4 col、page padding 56-64px
- 1024-1279: 商品 grid 3 col
- 768-1023: 商品 grid 2 col、左欄篩選變頂部抽屜
- < 768: 商品 grid 1 col、page padding 24px、篩選抽屜全屏

---

## 6. 狀態 / Pinia / TanStack Query

S02 不引新 Pinia store（auth store 已在 S01 建立）。

### TanStack Query keys

| Key | Endpoint | Stale time |
|---|---|---|
| `['public', 'products', { difficulty, detail, canvas_size, tag_id, series_id, theme_id, sort, page, page_size }]` | GET /products | 60s |
| `['public', 'products', 'search', { q, page, page_size }]` | GET /products/search | 60s |
| `['public', 'product', id]` | GET /products/:id | 5min |
| `['public', 'product', id, 'related']` | GET /products/:id/related | 5min |

URL query <-> Vue Router 同步：用 `useRoute()` + `useRouter()` watch + push。

---

## 7. 手動測試覆蓋

| Group | Case | 預期 | 對應 brief / api |
|---|---|---|---|
| HomePage | hero 載入、字體無 FOIT | ✓ Noto Serif TC 大標 | brief #1 |
| | 最新上架顯示 4 商品（DB 有商品時）/ 顯示「商品準備中」（DB 0 商品） | ✓ 真打 GET /products | api.md GET /products |
| | 主題瀏覽顯示 4 主題（DB 0 主題 → 隱藏該 section）| ✓ 真打 GET /themes | api.md GET /themes |
| | 精選系列 chips 顯示（DB 0 → 隱藏 section）| ✓ 真打 GET /series?featured=true | api.md GET /series |
| | 三入口卡片可點擊跳對應 /products?xxx | ✓ URL 含對應 query | brief #1 |
| | 客製 banner CTA 跳 /custom | ✓ | brief #1 |
| ProductListPage | 不帶 query 顯示 24 筆商品 / 空 → empty state | ✓ | brief #2 |
| | 點擊難易度 chip → URL 加 `?difficulty=elementary` + grid refresh | ✓ | brief #2 + backend enum |
| | 點擊主題 chip → URL 加 `?theme_id=xxx` + grid refresh | ✓ | brief #2 |
| | 排序 dropdown 切換 → URL 加 `?sort=price_asc` | ✓ | api.md GET /products |
| | 分頁切換 → URL `?page=2` + scroll top | ✓ | brief #2 |
| | mobile 篩選漢堡按鈕觸發抽屜 | ✓ | design_system §12 |
| ProductDetailPage | 圖片輪播切換 cover + images | ✓ | brief #4 |
| | 規格選擇器：選尺寸 → 難易度自動 filter 可用組合 | ✓ | brief #4 |
| | 全選後顯示價格 + 預覽圖 | ✓ | brief #4 |
| | 加購車按鈕點擊 → toast「即將上線」（S05 才做真邏輯）| ✓ | brief #4 + S05 範圍切割 |
| | 同系列商品橫列 ≤ 8 個 | ✓ | api.md GET /products/:id/related |
| | 商品說明 4 區摺疊 / 無 description → 整段隱藏 | ✓ | brief #4 |
| SearchPage | `/search` 沒 q → 重導 `/products` | ✓ | 規範 |
| | `/search?q=cat` 顯示「搜尋結果：cat」+ 商品 grid | ✓ | brief #3 + api.md GET /products/search |
| | 0 結果 → empty state「找不到符合的商品，試試別的關鍵字」 | ✓ | UX |
| 共用 | 載入中 spinner 顯示 | ✓ Loader2 | design_system |
| | 商品卡 hover 動效 | ✓ scale 1.03 + brightness 1.05 | design_system §7 |
| | < 768 商品卡單欄 | ✓ | design_system §12 |
| | mega-menu「依難易度 → 入門 / 初級 / 中級 / 進階」連結都打對 enum | ✓ basic → **elementary** | S01 修補 |

---

## 8. EVENT_MATRIX 對照

S02 全部為 GET 操作（讀取），**無 Event 觸發**。

加購車 button 點擊在本模組是 toast，不寫 cart（S05 才寫）。

---

## 9. 待確認

無。Backend API 規格已確認、設計決策已鎖。

---

## 10. 完成標準

每個 page 完成後：

1. `pnpm type-check` 0 錯
2. `pnpm build` 0 error / 0 warn
3. 手動驗收（§7）對應 case 全 ✓
4. Console 0 JS error / 0 warn
5. Network 真打 backend 真 endpoint（不 mock 假資料）
6. Lighthouse Accessibility ≥ 90
7. 設計風格對齊 [design_system.md](../design_system.md)（人工肉眼比對截圖）

---

## 11. Milestone 拆分

| # | 範圍 | 通過條件 |
|---|---|---|
| **M1 HomePage** | hero / 最新上架 / 主題 / 精選 / 入口 / 客製 banner + 修 SiteHeader bug | user 訪問 `/` chrome 看完整視覺 + 各 section 真實 API call 有資料時顯示資料、無資料時 empty state |
| **M2 ProductListPage + SearchPage** | 共用 grid + filter + sort + pagination | user 試 `/products?difficulty=elementary` 等過濾 |
| **M3 ProductDetailPage** | 圖片輪播 + 變體選擇 + 加購占位 + 同系列推薦 + 描述摺疊 | user 進真實商品詳情頁試規格切換 |
