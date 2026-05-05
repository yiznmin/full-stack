# S03 — 主題與系列瀏覽

> 後端對應：`backend/product/router.py:115-148`（GET /themes、/themes/:id、/series、/series/:id）
> 規格來源：[docs/api.md](../../../docs/api.md)、[docs/store_design_brief.md](../../../docs/store_design_brief.md) #4a/4b/4c
> 設計依據：[design_system.md](../design_system.md)

---

## 1. 範圍

### 本模組做

1. **ThemeListPage `/themes`**（brief #4a）
   - hero 標題 + 簡短說明
   - 主題卡片網格（4 col，每張：cover_image_url、name、description、series_count、product_count）

2. **ThemeDetailPage `/themes/:id`**（brief #4b）
   - hero：主題封面 + 名稱 + 描述
   - 該主題下所有系列卡片（grid）
   - 「該主題全部商品」CTA → `/products?theme_id=:id`
   - 404 處理（主題不存在）

3. **SeriesDetailPage `/series/:id`**（brief #4c）
   - hero：系列名稱 + 描述 + 主題麵包屑
   - 該系列下所有 on_sale 商品（依 series_order ASC）
   - 共用 ProductCard（沿 S02 的 component）
   - 404 處理（系列不存在）

### 不做

- 主題 cover_image_url 上傳功能（屬 admin）
- 系列頁不做 hero 圖（系列無 cover_image_url 欄位）— 用主題色漸層 + 系列名 fallback。已記錄在 [follow_ups.md #002](../follow_ups.md) 待 backend 加 `sample_cover_image_url`

---

## 2. 路由

| Path | Component | Layout | 備註 |
|---|---|---|---|
| `/themes` | ThemeListPage | DefaultLayout | 取代 S01 placeholder |
| `/themes/:id` | ThemeDetailPage | DefaultLayout | 取代 S01 placeholder |
| `/series/:id` | SeriesDetailPage | DefaultLayout | 取代 S01 placeholder |

---

## 3. 後端 API 對應

| Endpoint | Response | 用於 |
|---|---|---|
| `GET /themes` | `{ items: [{id, name, description, cover_image_url, sort_order, series_count, product_count}] }`（S01 useThemesQuery 已用）| ThemeListPage |
| `GET /themes/:id` | `{id, name, description, cover_image_url, sort_order, series: [{id, name, description, product_count}]}` | ThemeDetailPage |
| `GET /series/:id` | `{id, name, description, theme_id, theme_name, is_featured, products: [{id, title, cover_image_url, difficulty_range, price_min, price_max, is_preorder}]}` | SeriesDetailPage |

---

## 4. 元件樹

```
src/features/browse/
├── api.ts (擴充)               # +getTheme, +getSeries
├── queries.ts (擴充)           # +useThemeDetailQuery, +useSeriesDetailQuery

src/features/themes/
├── components/
│   ├── ThemeCard.vue           # S01 已建（主題列表 + Home 共用）
│   ├── ThemeHero.vue           # 主題詳情頁 hero
│   └── SeriesCard.vue          # 主題詳情頁的系列卡片
└── pages/
    ├── ThemeListPage.vue       # 取代 placeholder
    ├── ThemeDetailPage.vue     # 取代 placeholder
    └── SeriesDetailPage.vue    # 取代 placeholder
```

---

## 5. 設計決策

- 主題卡（ThemeCard）沿 S01 既有設計（aspect 1.3:1 + sepia 0.06 saturate 0.85 + overlay）
- 主題詳情頁 hero 結構：左圖右文，4:5 大圖 + 標題大字 + description + product_count meta
- 系列卡（主題詳情頁用）—  簡化版：左半部漸層 + 系列名 + 右半部描述 + product_count + →
- 系列詳情頁 hero：無圖，純標題 + 描述 + 主題麵包屑（borrow 主題色漸層當背景，未來補 sample_cover_image_url 換成真圖）
- 響應式同 S02

---

## 6. EVENT_MATRIX

S03 全 GET，無 Event。

---

## 7. 手動驗收

| Case | 預期 |
|---|---|
| `/themes` | 4 主題卡顯示 + 點進其中一個 |
| `/themes/:id` 真實 ID | hero 顯示主題名 + 該主題下系列 grid + 全部商品 CTA |
| `/themes/aaaa-bbbb-cccc-...`（不存在 UUID）| 404 「找不到這個主題」+ 回主題列表 CTA |
| `/series/:id` 真實 ID | 系列 hero + 該系列商品 grid（DB 0 商品 → empty state） |
| `/series/aaaa-...`（不存在 UUID）| 404 |
| 點主題卡的「全部商品 CTA」 | 跳到 `/products?theme_id=...` filter 對應主題 |
| 點主題詳情下的系列卡 | 跳 `/series/:id` |
| 點系列詳情下的商品 | 跳 `/products/:id` |

---

## 8. 完成標準

1. type-check 0 錯
2. build 0 error / 0 warn
3. 手動驗收所有 case ✓
4. Console 0 JS error / 0 warn
5. 0 商品時 empty state 正確（不寫死假資料）

---

## 9. 與 S01 既有路由 placeholder 的關係

S01 路由 `/themes`、`/themes/:id`、`/series/:id` 已建 placeholder 元件（features/themes/pages/ThemeListPage.vue 等），S03 是把這 3 個檔內容從 placeholder 換成完整實作。
