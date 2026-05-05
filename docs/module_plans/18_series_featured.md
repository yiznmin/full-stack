# Module 18 — Series is_featured 欄位

> 目的：新增 `is_featured` Boolean 欄位到 `product_series` 表，供精選系列功能使用：
> - store 端「精選系列」nav 入口
> - admin 後台勾選/取消精選 toggle
>
> 規格參考：[docs/store_design_brief.md](../store_design_brief.md) — 「精選系列」探索

---

## 一、檔案清單

```
backend/
├── product/models.py                                 # ProductSeries 加 is_featured
├── product/schemas/request.py                        # CreateRequest + UpdateRequest 加 is_featured
├── product/schemas/response.py                       # SeriesResponse + PublicSeriesBrief 加 is_featured
├── product/service.py                                # create / update / list / public_list 處理
├── product/router.py                                 # public GET /series 加 ?featured=
├── migrations/versions/k1f2g3h4i5j6_add_series_is_featured.py   # 新 alembic migration
└── tests/product/test_series_featured.py             # 新測試檔
```

---

## 二、DB Model

`product_series` 表加：

| 欄位 | 型別 | 限制 | 預設 |
|---|---|---|---|
| is_featured | BOOLEAN | NOT NULL | false |

Alembic migration `k1f2g3h4i5j6_add_series_is_featured`：
- upgrade: `op.add_column('product_series', sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=False))`
- downgrade: `op.drop_column('product_series', 'is_featured')`

---

## 三、API 改動

### Request schemas
- `SeriesCreateRequest` 加 `is_featured: bool = False`
- `SeriesUpdateRequest` 加 `is_featured: bool = False`

### Response schemas
- `SeriesResponse` 加 `is_featured: bool`
- `PublicSeriesBrief` 加 `is_featured: bool`

### Public endpoint
`GET /series` 加 query：

| Query | 行為 |
|---|---|
| 未傳 | 回所有系列（is_featured 在每筆 response 標示）|
| `?featured=true` | 只回 is_featured=true |
| `?featured=false` | 只回 is_featured=false |
| `?theme_id=...&featured=true` | 雙重過濾 |

### Admin endpoints
現有 `PUT /admin/series/:id` body 加 is_featured 欄位（沒傳 → 預設 false）。
現有 `POST /admin/series` body 加 is_featured 欄位（沒傳 → 預設 false）。

---

## 四、業務流程

### admin create / update series
1. body 含 is_featured（預設 false）
2. service 寫入 ProductSeries.is_featured
3. response 回 is_featured

### public list series
1. parse query: theme_id, featured
2. 組 select 加 where 子句
3. 排序：精選的排前面 + created_at desc fallback（**待確認**：是否要按 is_featured 排前？）→ 暫定不變動排序，只加 filter
4. response 每筆標 is_featured

---

## 五、EVENT_MATRIX 對照

本模組**無 Event 觸發**（純資料欄位 toggle，不觸發 email / 通知 / 副作用）。

---

## 六、測試覆蓋

| Case | 預期 | 測試函數 |
|---|---|---|
| Create series 不傳 is_featured | response is_featured=false（預設） | test_create_series_default_not_featured |
| Create series with is_featured=true | response is_featured=true | test_create_series_with_featured |
| Update toggle false → true | response is_featured=true | test_update_series_toggle_featured_on |
| Update toggle true → false | response is_featured=false | test_update_series_toggle_featured_off |
| Public GET /series 無 featured query | 全部回，每筆含 is_featured | test_public_list_series_default |
| Public GET /series?featured=true | 只回 featured 的 | test_public_list_series_featured_true |
| Public GET /series?featured=false | 只回非 featured 的 | test_public_list_series_featured_false |
| Public GET /series?theme_id=X&featured=true | 雙重 filter 正確 | test_public_list_series_combined_filter |
| Admin GET /admin/series | response 每筆含 is_featured | test_admin_list_series_with_featured |

---

## 七、規格文件同步

- `docs/api.md` GET /series 加 query / response 加 is_featured；POST/PUT /admin/series body 加 is_featured
- `docs/schema.md` product_series 表加 is_featured 欄位

---

## 八、待確認

無。

---

## 九、部署順序

1. 寫 migration → local 跑 `alembic upgrade head` 驗證 OK
2. push 到 remote
3. user 在 Railway 上手動 trigger `alembic upgrade head`（[start_web.sh:11 TODO](../../backend/scripts/start_web.sh#L11)）
4. 等 backend 部署完成才動 admin / store
