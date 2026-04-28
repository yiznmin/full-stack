# F03 — 商品管理

> 後端對應：`backend/product/`
> 規格來源：`docs/api.md`（模組六，line 282-374）、`docs/requirements/admin_product.md`、`docs/requirements/admin_routes.md`
> 設計依據：`admin/docs/design_system.md`

---

## 1. 範圍

### 本模組做
- `/admin/products`：商品列表（搜尋、狀態篩選、分頁）
- `/admin/products/new`：新增商品表單
- `/admin/products/:id`：編輯商品（含 variants tab、images tab）
- 系列（series）CRUD：dialog inline 建立、清單管理頁 `/admin/products?tab=series`
- 標籤（tags）CRUD：同上 `/admin/products?tab=tags`

### 本模組不做
- 商品上架到 store 的前端展示（屬 store/ 專案）
- production_job 的建立（屬 F06 製作系統）
- 商品評論 / 評分（規格未列）
- 庫存連動實體色顏料（屬 F07）

---

## 2. 路由清單

| Path | Component | Layout | Guard |
|---|---|---|---|
| `/admin/products` | `ProductsListPage` | `AdminLayout` | requiresAuth |
| `/admin/products/new` | `ProductFormPage`（mode=create）| `AdminLayout` | requiresAuth |
| `/admin/products/:id` | `ProductFormPage`（mode=edit）| `AdminLayout` | requiresAuth |

`tab=series` / `tab=tags` 切系列 / 標籤管理用 query string 控制 tab，不另開路由。

---

## 3. 後端 API 對應

### 商品本體
| Endpoint | 用於頁面 | Request | Response |
|---|---|---|---|
| `GET /admin/products?search=&status=&page=&page_size=` | 列表頁 | — | `{items, total, page, page_size}` |
| `POST /admin/products` | 新增頁 submit | `{title, description, cover_image_url, series_id, series_order, status, tag_ids}` | created product |
| `PUT /admin/products/{id}` | 編輯頁 submit | 同上 | updated product |
| `DELETE /admin/products/{id}` | 列表 / 詳情刪除 | — | 204 / 409（有訂單）|

### Variants（編輯頁子分頁）
| Endpoint | Request | 說明 |
|---|---|---|
| `POST /admin/products/{id}/variants` | `{production_job_id, price}` | 從 production_job 建變體 |
| `PATCH .../variants/{vid}` | `{price?, is_active?}` | 改價 / 上下架單一變體 |
| `DELETE .../variants/{vid}` | — | 刪除變體 |

### Images（編輯頁子分頁）
| Endpoint | Request | 說明 |
|---|---|---|
| `POST /admin/products/{id}/images` | `{image_url, sort_order}` | 加圖（image_url 從 F01 upload signed URL 流程拿）|
| `DELETE .../images/{img_id}` | — | 移圖 |
| `PATCH .../images/reorder` | `{order: [img_id...]}` | drag-and-drop 排序 |

### Series / Tags（共用清單管理）
| Endpoint | 用途 |
|---|---|
| `GET /admin/series` `GET /admin/tags` | 下拉 / 多選 / 列表 |
| `POST /admin/series` `POST /admin/tags` | 從 product form inline 建 + tab 頁建 |
| `PUT /admin/{series\|tags}/{id}` | rename |
| `DELETE /admin/{series\|tags}/{id}` | 刪（series 有商品擋 409、tags CASCADE）|

### 上傳（F01 signed URL 流程，沿用）
- `POST /upload/product-image` 產 signed URL → 前端 PUT 直傳 → 拿 `public_url` 寫入商品

---

## 4. 元件樹

```
features/products/
├── pages/
│   ├── ProductsListPage.vue        # /admin/products
│   ├── ProductFormPage.vue         # /admin/products/new + :id
│   ├── SeriesAdminPage.vue         # tab page (series 管理)
│   └── TagsAdminPage.vue           # tab page (tags 管理)
│
├── components/
│   ├── ProductTable.vue            # 商品列表 row
│   ├── ProductFilterBar.vue        # search + status + 新增按鈕
│   ├── ProductBasicForm.vue        # title / description / status / series / tags
│   ├── ProductCoverUpload.vue      # 主視覺圖（單張，必填）
│   ├── ProductImagesTab.vue        # 多圖 + 排序（drag）
│   ├── ProductVariantsTab.vue      # 變體列表 + 加變體 dialog
│   ├── VariantAddDialog.vue        # 從 production_job 選 + 設價
│   ├── SeriesPicker.vue            # 下拉 + 「新增系列」inline
│   ├── TagsMultiSelect.vue         # 多選 + 「新增標籤」inline
│   ├── ProductsTabs.vue            # /products + ?tab= 三個 tab 切換
│   └── OrderImpactWarningDialog.vue # 切 off_sale 時若有未完成訂單跳警告
│
├── api.ts                          # openapi-fetch / fetch wrappers
├── queries.ts                      # useProductsQuery, useProductMutation, ...
├── schemas.ts                      # zod
└── store.ts                        # 不需要 global store，全用 query cache
```

### Shared 共用元件本模組會拉出
- `shared/components/AppDataTable.vue`：可重用列表（columns、actions、loading、empty）
- `shared/components/AppPagination.vue`：分頁
- `shared/components/AppSearchInput.vue`：debounced 搜尋輸入
- `shared/ui/Dialog.vue`：modal primitive（之前沒做，這次補）
- `shared/ui/Select.vue`：下拉
- `shared/ui/Textarea.vue`：多行輸入

這四個 shared 在 F03 寫，F04+ 沿用。

---

## 5. 狀態 / Query 設計

### TanStack Query keys

```ts
['products', 'list', { search, status, page, page_size }]   → useProductsQuery
['products', 'detail', id]                                   → useProductQuery
['products', 'variants', id]                                 → useVariantsQuery
['products', 'images', id]                                   → useImagesQuery
['series', 'list']                                           → useSeriesQuery
['tags', 'list']                                             → useTagsQuery
```

### Mutations
- `useCreateProduct` / `useUpdateProduct` / `useDeleteProduct`
- `useAddVariant` / `useUpdateVariant` / `useDeleteVariant`
- `useAddImage` / `useDeleteImage` / `useReorderImages`
- `useCreateSeries` / `useUpdateSeries` / `useDeleteSeries`
- `useCreateTag` / `useUpdateTag` / `useDeleteTag`

每個 mutation 在 onSuccess 內 invalidate 對應 list/detail key。

---

## 6. 表單 schema（zod）

```ts
productSchema = z.object({
  title: z.string().min(1, '請輸入商品名稱').max(100),
  description: z.string().max(2000).default(''),
  cover_image_url: z.string().url('封面圖必填'),
  series_id: z.string().uuid().nullable(),
  series_order: z.number().int().min(0).default(0),
  status: z.enum(['draft', 'on_sale', 'off_sale']),
  tag_ids: z.array(z.string().uuid()).default([]),
})

variantSchema = z.object({
  production_job_id: z.string().uuid('請選一個 production job'),
  price: z.number().int().min(1).max(99999),
})

variantPatchSchema = z.object({
  price: z.number().int().min(1).max(99999).optional(),
  is_active: z.boolean().optional(),
})

seriesSchema = z.object({
  name: z.string().min(1).max(50),
  description: z.string().max(500).nullable().default(null),
})

tagSchema = z.object({
  name: z.string().min(1).max(20),
})
```

---

## 7. 設計決策

> 全部沿用 `admin/docs/design_system.md`，本模組例外列在下方。

### 列表頁（ProductsListPage）
- PageHeader 標題「商品管理」，右側主 CTA 「+ 新增商品」（primary button）
- ProductFilterBar：搜尋框（debounced 300ms）+ status select + tag filter + 新增按鈕
- AppDataTable 欄位：封面縮圖（48×48）/ 標題 / 系列 / 狀態 badge / 變體數 / 更新時間 / 操作（編輯/刪除）
- 每 row 點任意處進詳情頁（除了操作按鈕）；操作按鈕需 `event.stopPropagation`
- Empty state（無商品）：用 lucide `Package` icon + 「尚無商品」+ CTA 按鈕

### 編輯頁（ProductFormPage）
- 雙欄佈局：左 2/3 表單區、右 1/3 meta + 儲存按鈕（沿用 design_system §11 詳情頁慣例）
- 上方 tab 列：「基本資訊 / 圖片 / 變體」
- 表單欄位 stack 上下，跨群組 24px 間距、同群組 12px
- 主操作按鈕固定右下 sticky（避免長表單滾動找不到 save）

### 變體 Tab
- 表格：production_job snapshot info / 售價 / formula 計算價 / is_active toggle / 刪除
- 加變體用 modal dialog：選 production_job（從下拉）+ 輸入 price
- 顯示 `formula_base` 為 helper text，幫 admin 判斷是否合理

### 圖片 Tab
- 主封面：頂端單張大圖（必填）+ 上傳 / 替換按鈕
- 額外圖：grid 多張，drag-to-reorder（用 `vue-draggable-plus`）+ 每張右上 X 刪除
- 上傳走 F01 signed URL 流程：點「+ 加圖」→ 選檔 → POST /upload/product-image → PUT 直傳 → POST /admin/products/{id}/images

### Status badge
- `draft` 草稿：`--state-info`（藍墨）
- `on_sale` 上架中：`--state-success`（苔綠）
- `off_sale` 已下架：`--ink-muted`（灰）

### Series picker / Tags multi-select
- inline 「+ 新增系列 / 標籤」：點按鈕 → 同位置變 input → 輸入按 Enter 立即 POST + 加到列表
- Series 是單選下拉、Tags 是 chip-style multi-select

---

## 8. 手動驗收清單

| # | Case | 預期 |
|---|---|---|
| 1 | 進 `/admin/products` | 列表載入；空 DB 顯示 empty state |
| 2 | 點「+ 新增商品」 | 跳 `/admin/products/new`，空表單 |
| 3 | 填完表單 + 上傳封面 + submit | 201；跳到 `/admin/products/:id` 編輯頁，顯示剛建立的資料 |
| 4 | 必填留空 submit | 對應欄位下方紅字錯誤，不送出 API |
| 5 | 列表 search 框輸入「婚」 | debounce 後 query 帶 `?search=婚`，列表更新 |
| 6 | status filter 切 `on_sale` | query 帶 `?status=on_sale` |
| 7 | 翻頁 | query 帶 `?page=2` |
| 8 | 點 row 進詳情 | 進編輯頁，欄位都填好 |
| 9 | 編輯 title submit | 200；列表回去後標題已更新 |
| 10 | 「變體」tab + 加變體 | dialog 打開、選 production_job、設 price、submit；變體列表新增一行 |
| 11 | 改變體價格 | PATCH 200；列表更新 |
| 12 | 變體 is_active toggle | PATCH 200；toggle 立即視覺更新（optimistic）|
| 13 | 刪除變體 | DELETE 204；列表移除 |
| 14 | 「圖片」tab + 加圖 | upload signed URL → PUT → POST images；新圖在 grid 出現 |
| 15 | drag 圖排序 | PATCH images/reorder 200；順序保持 |
| 16 | 列表刪除（status=draft）| 204；列表移除 |
| 17 | 列表刪除（status=on_sale）| 409 toast「請先下架」 |
| 18 | 系列 tab 建立 | inline 新增 + appears in list |
| 19 | 系列 tab 刪除（系列下無商品） | 204 |
| 20 | 系列 tab 刪除（有商品） | 409 toast |
| 21 | 標籤 tab CRUD | 對應行為 |
| 22 | 401 中途登出 | 全頁 redirect login |
| 23 | < 1024 寬列表 | sidebar 收抽屜、表格橫向卷或縮欄位 |
| 24 | Console 0 錯誤 | — |
| 25 | 把 on_sale 商品切 off_sale 且有未完成訂單 | 跳 OrderImpactWarningDialog「此商品有 X 筆進行中訂單，下架後不影響現有訂單，確定繼續？」；確認後 PUT 才送出 |

---

## 9. 待確認問題

1. **新增商品時 cover_image 必填還是可空？** api.md schema 寫 `cover_image_url: "string"` 沒 nullable 標示，**預設必填**。
2. **drag-reorder library 選哪個？** `vue-draggable-plus` 是 Vue 3 友好、TS 支援；或自己用 native HTML5 drag。**預設用 vue-draggable-plus**（少量第三方依賴接受）。
3. **Series / Tags 管理用 sub-tab 還是獨立頁？** 規劃用 sub-tab，URL 帶 `?tab=`，視覺整合。OK 嗎？

---

## 10. 完成標準

- [ ] 規格比對報告產出無 ⚠️
- [ ] 24 條手動驗收全跑過
- [ ] `pnpm type-check` 0 error
- [ ] Console 無 error / warn
- [ ] Lighthouse a11y `/admin/products` ≥ 90
- [ ] 設計風格與 design_system 一致（5 個 random screenshot 比對）
- [ ] 回頭驗收報告無 ⚠️
- [ ] /reviewer pass
- [ ] git commit：`feat(admin/products): 完成 F03 - 商品管理`
