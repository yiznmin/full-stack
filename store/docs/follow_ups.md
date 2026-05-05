# Store 後續優化備忘

> 開發過程中暫緩、需要進一步討論或更深層製作的項目。
> 每筆記錄四件事：**觸發來源 / 現況 / 想做什麼 / 風險與牽連**。
> 開始做某項時建議先從這裡撈出來，討論完拍板再進實作。

---

## #001 — 商品詳情頁「資訊欄位」深度優化

**觸發來源**: S02 M3 ProductDetailPage 商品說明區（[features/products/components/ProductDescription.vue](../src/features/products/components/ProductDescription.vue)）

**現況**:
- `description`（商家自填）顯示為「關於這幅畫」單段純文字（`white-space: pre-wrap` plain text，無 markdown 渲染）
- 下方 4 個固定區塊摺疊：畫具內容 / 畫布材質 / 使用建議 / 注意事項
- 4 區內容目前**全部寫死在 store 前端 `SECTIONS` 陣列**（store/src 內 hard-code 的品牌共通文案）
- 每個商品都顯示同樣 4 區、無法因商品差異化

**想做什麼**（待討論方向）:
1. **內容歸屬**：4 區內容該由 store 寫死、admin 後台可編輯、還是 product 級可 override？
   - 全 admin 編輯 → 後台需要 4 個 textarea 欄位（`system_settings` 或新表 `product_description_sections`）
   - product 級 override → 商品 schema 加 4 個 nullable 欄位、admin form 加分頁
   - 折衷：admin 編全站預設、product 級可選擇性覆寫
2. **內容深度**：純文字 → markdown 渲染 / 圖文混排 / step-by-step 帶圖 / 規格表格
   - 例如「畫具內容」帶 4 張小圖（畫布 / 顏料 / 畫筆 / 色號表），每項一行短描述
   - 「使用建議」可做成編號 step（01-05）+ 小 illustration
3. **Markdown 支援**：admin 寫 description 用 markdown，前端用 marked / shiki 之類 lib 渲染
4. **動態欄位**：管理員可自訂 N 個段落（不限於 4 區），每段 title + body + 是否預展開
5. **SEO 考量**：說明區內容對 SEO 重要，要展開狀態可被 crawler 看到（v-show 是 OK，v-if 不行）

**風險與牽連**:
- Backend：可能加新表 / 新欄位 → migration → admin schema 同步
- Admin：SeriesAdminPage 等級的新 page / form 改動
- Store：ProductDescription 元件重做、可能引入 markdown lib（bundle size）
- 文案：4 區固定文案需要品牌/文案決策（目前 store 寫死的暫用版未經 user 校稿）

**討論前先看的東西**:
- 競品 store 商品詳情怎麼做（Aesop / niko and... / muji 商品頁說明結構）
- brief 提的 4 區是規格還是建議

**優先級**: 中 — S02 M3 不影響上線，但商品上線初期就會被使用者看到、體驗差會扣分。建議在 S02 全模組上線後、S04+ 之前處理。

---

## #002 — Series sample_cover_image_url（精選系列卡片視覺）

**觸發來源**: S02 M1 HomePage FeaturedSeriesSection

**現況**:
- 精選系列卡片視覺區用 4 種漸層循環（`VISUAL_GRADIENTS`）+ 系列名 overlay
- 系列本身在 backend schema 沒 cover_image_url 欄位

**想做什麼**:
- backend GET /series response 加 `sample_cover_image_url`（取該系列下第一個 on_sale 商品 cover_image_url；無 → null）
- 前端有 url 時顯示真圖 + sepia 濾鏡，無 url 時保留現有漸層 fallback
- 系列詳情頁 hero 也用同欄位

**風險與牽連**:
- Backend：service.public_list_series + service.public_get_series 補 SQL JOIN（無 schema migration）
- 前端 SeriesListItem type 加 nullable 欄位、FeaturedSeriesSection 內加 img 渲染分支

**優先級**: 低 — 視覺 fallback 已可接受，等 user 後台真的建商品 + 關聯系列後再啟動。

---

## #003 — 商品 level `is_featured` 欄位（精選商品機制）

**觸發來源**: SeriesDetailPage hero 右側展示區，user 想顯示「該系列中的精選商品」，發現目前只有 `series.is_featured` + `tags`、**products 表沒有 is_featured 欄位**。

**現況**:
- 系列詳情頁右側「精選展示」**暫用 `series.products.slice(0, 1-3)`**（依 series_order ASC 取前幾個）作為代理
- 跟「最新上架」section 一樣是排序衍生、不是真正「店家標記精選」

**想做什麼**（與 series featured 同型 epic）:
1. **Backend**：`products` 表加 `is_featured BOOLEAN NOT NULL DEFAULT false` 欄位（alembic migration）
2. **Backend**：`GET /products` 加 `?featured=true|false` query；`ProductCreateRequest` / `ProductUpdateRequest` 加 `is_featured`
3. **Admin**：`ProductsListPage` 列表加 ⭐ toggle、`ProductFormPage` 加「設為精選商品」checkbox
4. **Store**：
   - HomePage 加「精選商品」section（取代 / 補充「最新上架」）
   - ProductCard 加「⭐ 精選」chip
   - SeriesDetailPage 右側展示區改用 `GET /products?series_id=X&featured=true` 拿真實精選

**風險與牽連**:
- Backend：alembic migration（同 #002 series）+ schema / service / router / tests / docs
- Admin：ProductsListPage、ProductFormPage、api.ts、queries.ts
- Store：api.ts ProductsListParams 加 featured、HomePage 新 section
- 部署順序：backend → admin → store（同 series featured epic 流程）
- ⚠️ 要記得補 `start_web.sh` 的 `alembic upgrade head` 否則又會踩到「stamp head 沒 ALTER」的坑

**優先級**: 中 — SeriesDetailPage 暫用排序代理可接受，待 user 上商品後若覺得「該系列哪個商品要先曝光」需要店家自己決定，再啟動此 epic。

---

## 模板（新項目從這裡複製）

### #00X — <一句話標題>

**觸發來源**:

**現況**:

**想做什麼**:

**風險與牽連**:

**優先級**:
