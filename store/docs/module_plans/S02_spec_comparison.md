# 規格比對報告 — S02 商品瀏覽

> 配對 [S02_browse.md](S02_browse.md) 規劃書與所有規格來源逐項比對。任何 ⚠️ 必須先解決才能進入下一階段（實作）。

---

## 1. api.md 端點比對

| Endpoint | api.md 規定 | backend 實際 | 規劃書對應 | 結果 |
|---|---|---|---|---|
| `GET /products` | query: difficulty, detail, canvas_size, tag_id, series_id, theme_id, sort, page, page_size | [router.py:53-71](../../../backend/product/router.py#L53-L71)；difficulty enum `beginner/elementary/intermediate/advanced`；detail enum `rough/standard/detailed/premium`；sort enum `latest/popular/price_asc/price_desc` | §3 完整列出；§7 case 涵蓋 difficulty/sort/分頁 | ✓ |
| `GET /products/search` | query: q, page, page_size；q min 1 char | [router.py:74-81](../../../backend/product/router.py#L74-L81) | §3 列出；§7 case 涵蓋 search empty + with q | ✓ |
| `GET /products/:id` | response: id, title, description, cover_image_url, images, series, tags, variants | [router.py:84-93](../../../backend/product/router.py#L84-L93) `PublicProductDetailResponse` | §3 + §4 ProductGallery / VariantSelector / ProductDescription | ✓ |
| `GET /products/:id/related` | response: series, items | [router.py:96-105](../../../backend/product/router.py#L96-L105) `RelatedProductsResponse` | §3 + §4 同系列商品橫列 | ✓ |

**Schema 校對**：
- `PublicProductBrief` 有 `id, title, cover_image_url, difficulty_range, price_min, price_max, is_preorder` — 規劃書 §4 ProductCard 用這些欄位
- `PublicVariantResponse` 有 `id, canvas_w_cm, canvas_h_cm, difficulty, detail, color_count, price, is_active, is_preorder, filled_template_url` — 規劃書 §5 規格選擇器用這些欄位

---

## 2. requirements/store_routes.md 路由比對

| 路由 | 規劃書對應 | 結果 |
|---|---|---|
| `/` 首頁 | §2 第 1 列 HomePage | ✓ |
| `/products` 商品列表 | §2 第 2 列 ProductListPage | ✓ |
| `/products/:id` 商品詳情 | §2 第 3 列 ProductDetailPage | ✓ |
| `/search` 搜尋結果 | §2 第 4 列 SearchPage | ✓ |

---

## 3. store_design_brief.md 比對

| 規格 | 來源（行）| 規劃書對應 | 結果 |
|---|---|---|---|
| 首頁：hero、最新上架橫向、主題瀏覽、精選系列、3 個分類入口、客製 banner | brief:42 #1 | §1 HomePage 6 個 sections | ✓ |
| 商品列表：左側篩選（主題 / 系列 / 難易度 / 細緻度 / 尺寸 / 標籤）+ 排序 + 24 筆/頁 | brief:43 #2 | §1 ProductListPage + §5 篩選器 UI 5 段 collapsible | ✓ |
| 搜尋結果：同列表頁，篩選保留 | brief:44 #3 | §1 SearchPage 共用 ProductListPage 元件 | ✓ |
| 商品詳情：圖片輪播 + 規格三層級選擇器 + 加購車 + 同系列商品 + 商品說明 4 區摺疊 + 「想要不同規格？」客製規格表單 | brief:45 #4 | §1 ProductDetailPage + §5 VariantSelector | ✓（加購車邏輯與客製規格送出屬範圍外，邊界已標明）|
| 商品卡：封面圖、商品名稱（思源宋體 → 規劃書改 Noto Serif TC）、難易度標籤、價格區間 NT$397~860、預購標示 | brief:312 | §5 ProductCard | ✓（思源宋體在 Google Fonts 等價於 Noto Serif TC，design_system §2 已決策） |
| 商品詳情圖片輪播：封面 + product_images + 選定變體 filled_template | brief:319 | §1 ProductDetailPage + §4 ProductGallery；v1 不依變體切圖（已標註 enhancement）| ⚠️ → 範圍切割 |
| 規格選擇器三層級：依序尺寸 → 難易度 → 細緻度，無對應變體灰階禁用 | brief:323 | §5 VariantSelector | ✓ |
| 訂單狀態流 / 折扣 / 預購機制 | brief:228+ | 屬 S05/S06 | 範圍外 |

**⚠️ 範圍切割（不是衝突）**：
- 圖片輪播 v1 不依變體切圖 → 在規劃書 §1「不做」明確標明 v1 enhancement
- 加購車邏輯屬 S05 → 規劃書 §1 標明、按鈕只 toast

---

## 4. design_system.md 一致性

| 規則 | 來源 | 規劃書對應 | 結果 |
|---|---|---|---|
| 商品卡風格（paper-surface + line-subtle 邊 + 4:5 圖 + 22px 內距 + 價格 row）| §8 Product Card | §5 設計決策第 1 點完整對應 | ✓ |
| 攝影濾鏡 sepia 0.07 saturate 0.92 | §6 | §5 + Hero 用 sepia 0.04（hero 偏淡，已在規劃書註明） | ✓ |
| 商品卡 hover scale 1.03 + brightness 1.05 | §7 | §5 設計決策動效段 | ✓ |
| 留白：page padding 56-64px、section padding 96px | §4 | §5 響應式段；HomePage section gap 96px | ✓ |
| 響應式：≥1024 desktop nav、≥1280 商品 4 col、<768 1 col | §12 | §5 響應式 4 個 breakpoint 對齊 | ✓ |
| 中文標題 Noto Serif TC weight 300 size 20 | §2 + §8 | §5 ProductCard 標題 | ✓ |
| 圖示用 Lucide stroke 1.5 | §9 | §4 共用元件圖示 | ✓ |
| 動效進場 fade 180ms | §7 | §5 stagger fade-in | ✓ |
| 不寫死假資料 | memory `feedback_no_fake_data.md` | §1 全部接真 API、無資料 → empty state | ✓ |

---

## 5. EVENT_MATRIX 對照

S02 全部 GET 操作（讀取），無 Event 觸發 — 規劃書 §8 已確認。

加購車 button 在 S02 只 toast，不寫 cart（無 E08 cart 相關 Event）。

---

## 6. 手動測試覆蓋

規劃書 §7 列 27 條 case，分 4 group（HomePage / ProductListPage / ProductDetailPage / SearchPage / 共用 + S01 修補）。每條都對應到 chrome-devtools 驗證手段或 unit-level 行為。

---

## 7. 差異與 ⚠️

| 等級 | 內容 | 處理 |
|---|---|---|
| **無 ⚠️ 規格衝突** | — | — |
| 範圍切割 | 加購車邏輯（S05）/ 客製規格送出（S07）/ 變體圖片切換（v1 enhancement）| 已在規劃書 §1「不做」標明 |
| S01 修補 | mega-menu difficulty enum `basic` → `elementary` | 在 M1 階段一併修 |

**結論**：S02 規劃書與 4 份規格來源 0 衝突，可進入實作。

---

## 8. 下一階段檢查清單

- [x] api.md 4 條 endpoint 全部對照 backend 原始碼 + enum 校正
- [x] store_routes.md 4 條路由全在規劃書
- [x] store_design_brief.md #1-#4 規格全對應到元件樹
- [x] design_system.md 風格全套用
- [x] 27 條手動驗收 case 對應驗證手段
- [x] 範圍切割理由清楚（S05/S07/enhancement）
- [ ] 進 M1 HomePage 實作
