# Module 19 — Product is_featured 欄位

> 目的：商品 level 精選機制 — store 端「精選商品」入口、SeriesDetailPage 右側 Pick 區塊使用真實 admin 標記。

---

## 一、檔案清單

```
backend/
├── product/models.py                                      # Product 加 is_featured
├── product/schemas/request.py                             # ProductCreateRequest + ProductUpdateRequest 加 is_featured
├── product/schemas/response.py                            # ProductBriefResponse / ProductDetailResponse / PublicProductBrief / PublicProductDetailResponse 加 is_featured
├── product/service.py                                     # public_list_products 加 featured 過濾；_public_product_brief / public_get_product 回 is_featured
├── product/router.py                                      # public GET /products 加 ?featured=
├── migrations/versions/l2g3h4i5j6k7_add_product_is_featured.py
└── tests/product/test_product_featured.py
```

---

## 二、DB Model

`products` 表加：

| 欄位 | 型別 | 限制 | 預設 |
|---|---|---|---|
| is_featured | BOOLEAN | NOT NULL | false |

Alembic migration `l2g3h4i5j6k7_add_product_is_featured`：
- upgrade: `op.add_column('products', sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=False))`
- downgrade: `op.drop_column('products', 'is_featured')`

---

## 三、API 改動

### Request schemas
- `ProductCreateRequest` 加 `is_featured: bool = False`
- `ProductUpdateRequest` 加 `is_featured: bool = False`

### Response schemas
- `ProductBriefResponse`（admin list）加 `is_featured: bool`
- `ProductDetailResponse`（admin detail）加 `is_featured: bool`
- `PublicProductBrief`（store list）加 `is_featured: bool`
- `PublicProductDetailResponse`（store detail）加 `is_featured: bool`

### Public endpoint
`GET /products` 加 query：

| Query | 行為 |
|---|---|
| 未傳 | 全部回，每筆 response 標 is_featured |
| `?featured=true` | 只回 is_featured=true |
| `?featured=false` | 只回 is_featured=false |
| 與其他 filter（series_id / theme_id / tag_id / difficulty / detail / canvas_size）並用 | 雙重過濾 |

### Admin endpoints
- `POST /admin/products` body 加 is_featured（沒傳 → 預設 false）
- `PUT /admin/products/:id` body 加 is_featured

---

## 四、業務流程

### admin create / update product
1. body 含 is_featured（預設 false）
2. service 寫入 Product.is_featured（透過 `Product(**data)` spread）
3. response 回 is_featured

### public list products with featured filter
1. parse query: featured (and existing filters)
2. 組 select 加 `Product.is_featured == featured` where 子句
3. response 每筆標 is_featured

### public get product detail
1. ORM Product 已含 is_featured 屬性
2. response dict 加 `is_featured: product.is_featured`

---

## 五、EVENT_MATRIX 對照

本模組**無 Event 觸發**（純資料欄位 toggle，不觸發 email / 通知 / 副作用）。

---

## 六、測試覆蓋

| Case | 預期 | 測試函數 |
|---|---|---|
| Create product 不傳 is_featured | response is_featured=false | test_create_product_default_not_featured |
| Create product with is_featured=true | response is_featured=true | test_create_product_with_featured_true |
| Update toggle false → true | response is_featured=true | test_update_product_toggle_featured |
| Public GET /products 無 featured query | 全部回，每筆含 is_featured | test_public_list_products_default_includes_is_featured |
| Public GET /products?featured=true | 只回 featured 的 | test_public_list_products_featured_true_filter |

---

## 七、規格文件同步

- `docs/api.md` GET /products query / response 加 is_featured；POST/PUT /admin/products body 加 is_featured；GET /products/:id response 加 is_featured
- `docs/schema.md` products 表加 is_featured 欄位

---

## 八、部署順序

1. **先 alembic upgrade head** 在 production DB（透過 Railway public proxy URL）→ ALTER TABLE 加 is_featured 欄位
2. **後** push backend code → Railway redeploy → init_db.py stamp head 已是 head（no-op）
3. Admin Vercel auto deploy
4. Store Vercel auto deploy

⚠️ Module 18（Series featured）有踩過「init_db.py stamp head 沒實際 ALTER」的坑，本模組已在 push 前先跑 alembic upgrade 實際 ALTER。
