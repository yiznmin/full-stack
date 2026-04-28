# 規格比對報告 — F03 商品管理

> 配對 `F03_products.md` 規劃書與所有規格來源逐項比對。

---

## 1. api.md 端點比對

來源：`docs/api.md` lines 282-374（19 個端點）

| Endpoint | api.md 規定 | 規劃書 §3 對應 | 結果 |
|---|---|---|---|
| `GET /admin/products?search=&status=&page=&page_size=` | query 參數 | ProductsListPage 列表 query | ✓ |
| `POST /admin/products` | `{title, description, cover_image_url, series_id, series_order, status, tag_ids}` | ProductFormPage create + zod schema 對齊 | ✓ |
| `PUT /admin/products/{id}` | 同上 | ProductFormPage edit | ✓ |
| `DELETE /admin/products/{id}` | 需先下架 + 無進行中訂單；否則 409 | 列表刪除 + case 17 驗 409 | ✓ |
| `POST /admin/products/{id}/images` | `{image_url, sort_order}` | ProductImagesTab + signed URL 流程 | ✓ |
| `DELETE /admin/products/{id}/images/{image_id}` | — | grid 圖右上 X 觸發 | ✓ |
| `PATCH /admin/products/{id}/images/reorder` | `{order: [image_id...]}` | drag-and-drop 後 PATCH | ✓ |
| `POST /admin/products/{id}/variants` | `{production_job_id, price}` ON CONFLICT UPDATE | VariantAddDialog | ✓ |
| `PATCH /admin/products/{id}/variants/{vid}` | `{price?, is_active?}` | 變體列表改價 + toggle | ✓ |
| `DELETE /admin/products/{id}/variants/{vid}` | — | 列表刪除 | ✓ |
| `GET /admin/series` | — | 系列下拉 + tab 列表 | ✓ |
| `POST /admin/series` | `{name, description}` | inline 建立 + tab 建 | ✓ |
| `PUT /admin/series/{id}` | rename | tab rename | ✓ |
| `DELETE /admin/series/{id}` | 系列下有商品則 409 | tab delete + case 20 | ✓ |
| `GET /admin/tags` | — | tags 多選 + tab 列表 | ✓ |
| `POST /admin/tags` | `{name}` | inline + tab | ✓ |
| `PUT /admin/tags/{id}` | rename | tab | ✓ |
| `DELETE /admin/tags/{id}` | CASCADE | tab | ✓ |

19/19 ✓。

---

## 2. requirements/admin_product.md 業務規則比對

| 規則 | 來源（行）| 規劃書對應 | 結果 |
|---|---|---|---|
| 商品 status 三態：draft / on_sale / off_sale | L86-91 | zod enum + Status badge 三色 | ✓ |
| 變體預設帶入 price_formula_base，admin 可改 price | L74 | VariantAddDialog 顯示 formula 為 helper | ✓ |
| 每個變體獨立計算可供件數 | L95 | F03 不做（屬 F07 顏色模組）| ✓（範圍外）|
| 系列內排序 series_order | L44 | productSchema 含 series_order | ✓ |
| 上架時若有未完成訂單需顯示警告 | L137 | F03 規劃書未明列此 confirm dialog → ⚠️ 補入 |
| 同 production_job 可出現在多商品（跨不同 product）| L242 | VariantAddDialog 不擋；後端 ON CONFLICT 處理 | ✓ |
| 商品 status=draft / off_sale 才能刪除 | api.md L305 + req L137 | case 17 驗 409 toast | ✓ |
| 變體 is_active 控制單一規格上下架（vs 商品層級 status）| 推論 | VariantsTab 的 toggle 對應 | ✓ |

⚠️ **差異**：上架 / 下架時的「進行中訂單」警告 dialog 沒列在規劃書元件樹。**處理**：在 ProductFormPage 的 status select 切換時 / 列表 status toggle 時加 confirm dialog 流程；元件樹補一個 `OrderImpactWarningDialog.vue`。

---

## 3. requirements/admin_routes.md 比對

| 規定路由 | 規劃書 §2 | 結果 |
|---|---|---|
| `/admin/products` 商品列表 | ✓ | ✓ |
| `/admin/products/new` 新增 | ✓ | ✓ |
| `/admin/products/:id` 編輯 | ✓ | ✓ |

系列 / 標籤管理走 `?tab=`，admin_routes 沒明列子頁——**規劃 sub-tab 模式**符合「商品管理」總範圍。

---

## 4. design_system.md 一致性比對

| 規則 | 來源 | 規劃書對應 | 結果 |
|---|---|---|---|
| 列表頁三段（搜尋、表格、分頁）| §11 | ProductsListPage | ✓ |
| 詳情頁左 2/3 / 右 1/3 | §11 | ProductFormPage | ✓ |
| 表單縱向單欄、CTA 右下 | §11 | sticky 主操作按鈕 | ✓ |
| 不用模組色 | §3.3 | F03 status 用 state 色（success / info / muted）| ✓ |
| Status badge 規範（10% alpha bg） | §8 | 三 status 對應三 state 色 | ✓ |
| Modal Esc 關閉、focus trap | §9 | Dialog 元件需實作（之前沒做）| ✓（待寫）|
| 列表 row 40px、卡片 24-28px 內距 | §4 | AppDataTable 沿用 | ✓ |
| Lucide icon stroke 1.5、16px | §9 | 全模組統一 | ✓ |

---

## 5. 手動測試覆蓋

24 條 case 已映射到對應的 endpoint / 業務規則 / a11y / RWD。

---

## 6. 差異與待確認

### ⚠️ 必須補入規劃書
1. **上架 / 下架時的進行中訂單警告 dialog** —— 規劃書 §4 元件樹補 `OrderImpactWarningDialog.vue`，§8 case 增加 case 25「商品 on_sale 切 off_sale 有未完成訂單」→ 顯示警告，admin 可確認強制下架。

### 待確認（內部預設，不阻擋）
1. **drag-reorder library**：`vue-draggable-plus` — 預設使用，1 個第三方依賴可接受
2. **Series / Tags 管理是 sub-tab 還是獨立頁** — 預設 sub-tab `?tab=`
3. **cover_image 必填** — api.md 沒標 nullable，預設必填

### 待後端配合（不阻擋 F03）
- variant 列表需要 production_job 摘要資料（jobs 端點不在 F03 範圍）— 預設後端 `GET /admin/products/{id}/variants` 應回 join 後的 snapshot；規劃書假設 response 含 `production_job_snapshot` 欄位。如後端目前只回 `production_job_id`，前端再用 `GET /admin/production/jobs/{id}` 補資料（拖慢但能跑）。

---

## 7. 結論

⚠️ 必須先補入「進行中訂單警告 dialog」到規劃書 §4 元件樹 + §8 測試 case，補完即可開始寫 code。

修正後規劃書狀態：可以開始實作。
