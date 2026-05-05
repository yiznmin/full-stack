# PaintLearn API 規格

## 通用規則

- **Base URL**：`/api/v1`
- **認證**：JWT 存於 httpOnly cookie
- **權限層級**：`public` / `auth`（customer 或 admin 均可）/ `admin`（role=admin）
- 所有狀態變更使用資料庫交易 + `SELECT FOR UPDATE`

### 回應格式

**成功 — 單筆資源**：直接回傳物件
```json
{ "id": "uuid", "name": "string", ... }
```

**成功 — 建立資源**：HTTP 201，回傳建立後的物件
```json
{ "id": "uuid", ... }
```

**成功 — 列表（分頁）**：
```json
{ "items": [...], "total": 100, "page": 1, "page_size": 20 }
```

**成功 — 無回傳內容**：HTTP 204，無 body

**錯誤**：所有錯誤統一格式
```json
{ "detail": "錯誤描述（中文）" }
```

| 狀態碼 | 使用情境 |
|--------|---------|
| 400 | 語意錯誤（非法狀態轉換、業務規則衝突）|
| 401 | 未登入、JWT 無效或過期、帳號已停用 |
| 403 | 權限不足 |
| 404 | 資源不存在 |
| 409 | 唯一性衝突（email 重複、促銷碼衝突）|
| 422 | Request body 格式 / 型別錯誤（Pydantic 自動，格式為欄位級錯誤）|
| 503 | 外部服務失敗（ECpay / Firebase），可重試 |

---

## 模組一：認證

### POST /auth/register
**權限**：public

```json
Request: { "name": "string(min4)", "email": "string", "password": "string(min10,英數混合)" }
Response 201: { "message": "驗證信已寄出" }
```

### POST /auth/login
**權限**：public  
成功後設定 httpOnly cookie（7天）

```json
Request:  { "email": "string", "password": "string" }
Response 200: { "id": "uuid", "name": "string", "role": "customer" }
Response 401: 帳號或密碼錯誤（不區分哪個錯）
Response 403: 帳號未驗證 email / 帳號已停用
```

### POST /auth/logout
**權限**：auth｜清除 cookie

### GET /auth/me
**權限**：auth

```json
Response 200: { "id": "uuid", "name": "string", "email": "string", "pending_email": "string|null", "role": "string", "gender": "string|null", "birthday": "date|null" }
```

### POST /auth/verify-email
**權限**：public

```json
Request:  { "token": "string" }
Response 200: { "token_type": "signup|email_change" }
```
> signup → 帳號啟用 + 發放 new_user 歡迎券  
> email_change → pending_email 寫入 email

### POST /auth/resend-verification
**權限**：public

```json
Request: { "email": "string" }
Response 200: { "message": "驗證信已重新寄出" }
```

### POST /auth/forgot-password
**權限**：public｜發送重設信，回應固定成功（不洩漏帳號是否存在）

```json
Request:  { "email": "string" }
Response 200: { "message": "若帳號存在，重設連結已寄出" }
```

### POST /auth/reset-password
**權限**：public

```json
Request:  { "token": "string", "new_password": "string(min10,英數混合)" }
Response 200: { "message": "密碼已更新" }
Response 400: token 無效或已過期
```

### POST /admin/auth/login
**權限**：public｜成功後設定 httpOnly cookie（8小時）

```json
Request:  { "email": "string", "password": "string" }
Response 200: { "id": "uuid", "name": "string", "role": "admin" }
Response 403: 非 admin 帳號
```

### POST /admin/auth/logout
**權限**：admin｜清除 cookie

### POST /admin/auth/forgot-password
**權限**：public｜重設後導回 /admin/login，不記錄 redirect

---

## 模組二：用戶資料

### PATCH /users/me
**權限**：auth

```json
Request:  { "name": "string", "gender": "female|male|other|null", "birthday": "date|null" }
Response 200: 更新後的用戶資料
```

### POST /users/me/change-password
**權限**：auth

```json
Request:  { "old_password": "string", "new_password": "string" }
Response 400: 舊密碼錯誤
```

### POST /users/me/request-email-change
**權限**：auth｜將新 email 存入 pending_email，寄驗證信

```json
Request:  { "new_email": "string" }
Response 409: email 已被使用
```

---

## 模組三：收件資料

### GET /users/me/shipping-profiles
**權限**：auth

### POST /users/me/shipping-profiles
**權限**：auth

```json
Request: {
  "shipping_type": "home|seven_eleven|family_mart",
  "recipient_name": "string",
  "phone": "string",
  "email": "string|null",
  "city": "string|null",
  "district": "string|null",
  "address_detail": "string|null",
  "store_id": "string|null",
  "store_name": "string|null",
  "is_default": false
}
```
> home 必填：city、district、address_detail  
> 超商必填：store_id、store_name

### PUT /users/me/shipping-profiles/{id}
**權限**：auth

### DELETE /users/me/shipping-profiles/{id}
**權限**：auth

### PATCH /users/me/shipping-profiles/{id}/set-default
**權限**：auth｜同時取消同用戶其他 is_default=true

---

## 模組四：用戶管理（Admin）

### GET /admin/users
**權限**：admin

Query: `?search=（name/email）&role=admin|customer&is_active=true|false&page=1&page_size=20`

### GET /admin/users/{id}
**權限**：admin

### PATCH /admin/users/{id}
**權限**：admin

```json
Request: { "name": "string", "role": "admin|customer", "is_active": true, "password": "string|null" }
```
> 禁止停用自己（operator_id = target_id 時回 403）；禁止停用其他 admin（target.role = admin 時回 403）

### POST /admin/users/issue-coupons
**權限**：admin｜批次手動發放折扣券

```json
Request:  { "user_ids": ["uuid"], "coupon_config_id": "uuid" }
Response 200: { "issued_count": 5 }
```

---

## 模組五：商品（公開）

### GET /products
**權限**：public

Query: `?difficulty=beginner|elementary|intermediate|advanced&detail=rough|standard|detailed|premium&canvas_size=30x40&tag_id=uuid&series_id=uuid&theme_id=uuid&sort=latest|popular|price_asc|price_desc&page=1&page_size=24`

> `theme_id` 過濾撈該主題下所有 series 的商品（透過 series_id IN 子查詢）。

```json
Response 200: {
  "items": [{
    "id": "uuid", "title": "string", "cover_image_url": "string",
    "difficulty_range": ["beginner","advanced"],
    "price_min": 397, "price_max": 860,
    "is_preorder": false
  }],
  "total": 100, "page": 1, "page_size": 24
}
```

### GET /products/search
**權限**：public

Query: `?q=關鍵字&page=1&page_size=24`  
> ILIKE 搜尋 products.title、products.description、tags.name

### GET /products/{id}
**權限**：public

```json
Response 200: {
  "id": "uuid", "title": "string", "description": "string",
  "cover_image_url": "string",
  "images": [{ "image_url": "string", "sort_order": 0 }],
  "series": { "id": "uuid", "name": "string", "products": [...] },
  "tags": [{ "id": "uuid", "name": "string" }],
  "variants": [{
    "id": "uuid", "canvas_w_cm": 30, "canvas_h_cm": 40,
    "difficulty": "beginner", "detail": "standard",
    "color_count": 18, "price": 397,
    "is_active": true, "is_preorder": false,
    "filled_template_url": "string"
  }]
}
```

### GET /products/{id}/related
**權限**：public｜取得同系列其他商品

```json
Response 200: {
  "series": { "id": "uuid", "name": "string" },
  "items": [{ "id": "uuid", "title": "string", "cover_image_url": "string", "price_min": 397, "is_preorder": false }]
}
```
> 若商品不屬於任何系列，回傳 `{ "series": null, "items": [] }`

### GET /tags
**權限**：public

### GET /themes
**權限**：public｜所有主題（依 sort_order 排）

```json
Response 200: {
  "items": [{
    "id": "uuid", "name": "萌寵", "description": "string|null",
    "cover_image_url": "string|null", "sort_order": 10,
    "series_count": 3, "product_count": 12
  }]
}
```

> `product_count` 只計 `status='on_sale'` 的商品。

### GET /themes/{id}
**權限**：public｜單主題詳情 + 該主題下所有系列

```json
Response 200: {
  "id": "uuid", "name": "string", "description": "string|null",
  "cover_image_url": "string|null", "sort_order": 10,
  "series": [{ "id": "uuid", "name": "string", "description": "string|null", "product_count": 5 }]
}
Response 404: 主題不存在
```

### GET /series
**權限**：public｜所有系列（含 theme_name + product_count + is_featured）

Query:
- `?theme_id=uuid` 過濾主題（可選）
- `?featured=true|false` 過濾精選系列（可選；不傳 = 全部）

```json
Response 200: {
  "items": [{
    "id": "uuid", "name": "string", "description": "string|null",
    "theme_id": "uuid|null", "theme_name": "string|null",
    "is_featured": false,
    "product_count": 5
  }]
}
```

### GET /series/{id}
**權限**：public｜單系列詳情 + 該系列下所有 on_sale 商品（依 series_order ASC）

```json
Response 200: {
  "id": "uuid", "name": "string", "description": "string|null",
  "theme_id": "uuid|null", "theme_name": "string|null",
  "is_featured": false,
  "products": [{
    "id": "uuid", "title": "string", "cover_image_url": "string",
    "difficulty_range": ["beginner","advanced"],
    "price_min": 397, "price_max": 860, "is_preorder": false
  }]
}
Response 404: 系列不存在
```

> `series_order` NULL 排在最後（NULLS LAST）。

---

## 模組六：商品管理（Admin）

### GET /admin/products
**權限**：admin

Query: `?search=&status=draft|on_sale|off_sale&page=1&page_size=20`

### POST /admin/products
**權限**：admin

```json
Request: {
  "title": "string", "description": "string", "cover_image_url": "string",
  "series_id": "uuid|null", "series_order": 0,
  "status": "draft|on_sale|off_sale",
  "tag_ids": ["uuid"]
}
```

### PUT /admin/products/{id}
**權限**：admin

### DELETE /admin/products/{id}
**權限**：admin｜需先下架且無進行中訂單

### POST /admin/products/{id}/images
**權限**：admin

```json
Request:  { "image_url": "string", "sort_order": 0 }
```

### DELETE /admin/products/{id}/images/{image_id}
**權限**：admin

### PATCH /admin/products/{id}/images/reorder
**權限**：admin

```json
Request:  { "order": ["image_id_1", "image_id_2"] }
```

### POST /admin/products/{id}/variants
**權限**：admin｜從 approved production_job 建立變體

```json
Request:  { "production_job_id": "uuid", "price": 397 }
Response 200: 自動帶入 price_formula_base（公式計算）
Response 409: UNIQUE(product_id, production_job_id) 衝突時覆蓋（ON CONFLICT UPDATE）
```

### PATCH /admin/products/{id}/variants/{variant_id}
**權限**：admin

```json
Request:  { "price": 420, "is_active": true }
```

### DELETE /admin/products/{id}/variants/{variant_id}
**權限**：admin

### GET /admin/themes
**權限**：admin

Query: `?search=&page=1&page_size=50`

```json
Response 200: {
  "items": [{
    "id": "uuid", "name": "萌寵", "description": "string|null",
    "cover_image_url": "string|null", "sort_order": 10,
    "series_count": 3, "created_at": "iso", "updated_at": "iso"
  }],
  "total": 5, "page": 1, "page_size": 50
}
```

### GET /admin/themes/{id}
**權限**：admin｜回單一主題詳情含 series_count

### POST /admin/themes
**權限**：admin

```json
Request: {
  "name": "string(min1,max50)",
  "description": "string|null",
  "cover_image_url": "string|null",
  "sort_order": 0
}
Response 409: name UNIQUE 衝突
```

### PUT /admin/themes/{id}
**權限**：admin｜同 POST 欄位

### DELETE /admin/themes/{id}
**權限**：admin｜該主題下所有系列 theme_id 自動 SET NULL（系列保留）

### GET /admin/series
**權限**：admin

Query: `?theme_id=uuid` filter（可選；不帶則列所有）

Response 每筆系列含 `theme_id`、`theme_name`、`is_featured`。

### POST /admin/series
**權限**：admin

```json
Request:  { "name": "string", "description": "string|null", "theme_id": "uuid|null", "is_featured": false }
Response 404: theme_id 不存在
```

### PUT /admin/series/{id}
**權限**：admin｜同 POST 欄位

### DELETE /admin/series/{id}
**權限**：admin｜系列下仍有商品時回 409

### GET /admin/tags
**權限**：admin

### POST /admin/tags
**權限**：admin

```json
Request:  { "name": "string" }
```

### PUT /admin/tags/{id}
**權限**：admin

### DELETE /admin/tags/{id}
**權限**：admin｜CASCADE 移除所有 product_tags 關聯

---

## 模組七：製作系統（Admin）

### GET /admin/images
**權限**：admin

Query: `?page=1&page_size=20`

### POST /admin/images
**權限**：admin｜上傳原始圖片

```json
Request:  { "original_url": "string", "filename": "string", "width": 1920, "height": 1080 }
```

### POST /admin/production/jobs
**權限**：admin｜建立製作任務（單筆或批次）

```json
Request: {
  "image_id": "uuid|null",
  "custom_request_id": "uuid|null",
  "jobs": [{
    "detail": "rough|standard|detailed|premium",
    "difficulty": "beginner|elementary|intermediate|advanced",
    "mode": "standard|sam_refine|sam_weighted",
    "canvas_w_cm": 30, "canvas_h_cm": 40,
    "min_brush_diam_cm": 1.0,
    "num_colors": null,
    "blur_ksize": null, "blur_sigma_color": null, "blur_sigma_space": null,
    "prune_iterations": null, "pruning_threshold": null,
    "min_ratio_multiplier": null, "bg_extra_blur": null,
    "extra_colors": null, "weight_ratio": null,
    "sam_points": null, "polygons": null, "mask_url": null
  }]
}
```
> 多筆 jobs → 共用同一 batch_id，依序進入 Celery 佇列（不並發）

```json
Response 201: { "batch_id": "uuid|null", "job_ids": ["uuid"] }
```

### GET /admin/production/jobs
**權限**：admin

Query: `?status=pending|processing|completed|failed&approved=true|false&batch_id=uuid&image_id=uuid&custom_request_id=uuid&page=1&page_size=20`

### GET /admin/production/jobs/{id}
**權限**：admin

```json
Response 200: {
  "id": "uuid", "batch_id": "uuid|null", "custom_request_id": "uuid|null",
  "status": "pending|processing|completed|failed", "approved": false,
  "detail": "rough|standard|detailed|premium", "difficulty": "beginner|elementary|intermediate|advanced",
  "mode": "string", "canvas_w_cm": 30, "canvas_h_cm": 40,
  "svg_url": null, "filled_template_url": null, "snapped_rgb_url": null,
  "palette_json": [...], "num_colors_used": 18,
  "palette_mappings": [{ "template_id": 1, "algorithm_rgb": [0, 0, 0], "physical_color": {"id":"uuid","code":"201","name":"SKIN TONE"}, "required_ml": null, "mapped_by": "system|manual" }],
  "notes": "string|null", "created_at": "timestamp", "approved_at": "timestamp|null"
}
```

### DELETE /admin/production/jobs/{id}
**權限**：admin｜硬刪除任務 + 連帶刪 `palette_color_mappings` + Firebase 物件（svg / filled / snapped_rgb / mask）。

```
Response 204: (no content)
Response 400: {"detail":"任務正在處理中，無法刪除..."}        # status=processing
Response 400: {"detail":"任務被以下資料引用，無法刪除：商品 variant（1 筆）"}  # 被 product_variants / print_batches / order_items 引用
Response 404: {"detail":"製作任務不存在"}
```

業務規則：
- `status=processing` 拒絕（worker 寫入中）
- 被 `product_variants` / `print_batches` / `order_items` 任一引用拒絕（防斷鏈）
- `palette_color_mappings` 連帶刪（FK NOT NULL，schema 無 ondelete CASCADE）
- Firebase 4 個 blob best-effort 刪：失敗只 log 不回滾（DB 已 commit）

### GET /admin/production/jobs/{id}/signed-url
**權限**：admin｜取得私有檔案簽名 URL（15分鐘 TTL）

Query: `?file=svg|snapped_rgb|filled`

`filled` 為 admin UI 顯示用 signed URL（DB 內 filled_template_url 為 `gs://` 私有路徑，需簽名才能讀）。

```json
Response 200: { "url": "https://..." }
```

### POST /admin/production/jobs/{id}/post-process/merge-color
**權限**：admin｜格子合併（區域層級）

```json
Request:  { "polygon_id": "r5", "target_template_id": 1 }
```
> `polygon_id` = template.svg 中 `<polygon id="rN">` 的識別碼（admin 點該格時前端取得）
> 後端：解 SVG 取 polygon 頂點 → mask → 把該格像素改成 target_template_id 對應的 RGB →
> 重跑 SVG + filled_template → approved 退回 false。若該格是該色最後一格，palette 自動縮減。

### POST /admin/production/jobs/{id}/post-process/eliminate-border
**權限**：admin｜消除邊界線（區域層級）

```json
Request:  { "absorbed_polygon_id": "r5", "surviving_polygon_id": "r2" }
```
> 兩個 polygon_id 由 admin 點兩格 + 對話框選擇保留哪邊得來。後端把 absorbed 那格像素改成
> surviving 那格在 snapped_rgb 中的實際 RGB → 重跑 SVG + filled。鄰接判定屬前端 UI 約束。

### POST /admin/production/jobs/{id}/sam-mask
**權限**：admin｜送出 SAM 遮罩參數，後端跑 SAM 模型產生 mask

```json
Request: {
  "sam_points": [{"x": 100, "y": 200, "label": 1}, {"x": 50, "y": 80, "label": 0}],
  "polygons": [[[x,y], [x,y], ...]],
  "mode": "sam_refine|sam_weighted"
}
Response 200: { "mask_url": "string|null", "mask_coverage": "0.42 (0~1 比例) | null（純 sam_points 等 worker 推論）" }
```
> label: 1=前景點, 0=背景點；完成後更新 production_job 的 mask_url / mask_coverage，approved 退回 false

### POST /admin/production/jobs/{id}/approve
**權限**：admin｜確認儲存（approved=true）

```json
Request:  { "notes": "string|null" }
Response 200: JobDetailResponse（approved=true, approved_at 已設定）
```

> 只有 status=completed 才可核准；重複呼叫 idempotent（200）

### POST /admin/production/jobs/{id}/unapprove
**權限**：admin｜撤銷核准（approved=false）

```json
Response 200: JobDetailResponse（approved=false, approved_at=null）
```

> 重複呼叫 idempotent（200）

### GET /admin/production/jobs/{id}/export-pdf
**權限**：admin｜即時產生 PDF（SVG → Inkscape 轉換），直接回傳二進位下載

### POST /admin/production/batches/{batch_id}/start
**權限**：admin｜把 batch 內 sam_* 模式的 pending job 一次性送進 Celery 佇列

```json
Response 200: {
  "enqueued": 3,
  "skipped": [
    { "job_id": "uuid", "reason": "missing mask_url" },
    { "job_id": "uuid", "reason": "already processing" }
  ]
}
Response 404: batch_id 不存在
```

> 為什麼有這個 endpoint：mode=sam_refine / sam_weighted 的 job 在 `POST /admin/production/jobs` 建立時**不會**自動 enqueue，因為 admin 必須先用 [POST /sam-mask](#post-adminproductionjobsidsam-mask) 編完遮罩才能送進 worker。
> 此 endpoint 是 admin 編完整批 mask 後的「送出全批處理」動作。
>
> 行為：
> - 只 enqueue `mode != standard` 且 `status = pending` 且 `mask_url != null` 的 job
> - 缺 mask_url 的 → skipped 列表中標 `"missing mask_url"`，**不**整批拒絕
> - 已 processing / completed / failed → skipped，避免重複觸發
> - mode=standard 的 job 已在建立時 enqueue → skipped（防禦性處理；前端應已擋掉混批）
> - 操作 idempotent；admin 可在補完缺漏 mask 後重點送出

---

## 模組八：顏色管理（Admin）

### GET /admin/colors
**權限**：admin

Query: `?color_family=&is_active=true|false&search=`

```json
Response 200: {
  "items": [{ "id": "uuid", "code": "201", "name": "SKIN TONE", "color_family": "膚色系", "rgb": [247, 167, 132], "stock_ml": 500, "is_active": true }]
}
```

### POST /admin/colors
**權限**：admin

```json
Request: { "code": "201", "name": "SKIN TONE", "color_family": "膚色系", "brand": "string|null", "rgb": [247, 167, 132], "stock_ml": 0 }
```

### PUT /admin/colors/{id}
**權限**：admin

### PATCH /admin/colors/{id}/toggle-active
**權限**：admin｜停用後視同庫存為 0

### PATCH /admin/colors/{id}/rgb
**權限**：admin｜校正實體色 RGB（palette workspace 彈跳視窗）

```json
Request:  { "hex": "#FF8800" } 或 { "rgb": [255, 136, 0] }
Response 200: PhysicalColor 完整物件
Response 422: hex/rgb 同時提供、或都未提供、或格式不符
```
> hex 與 rgb 二擇一必填。校正不影響既有 palette_color_mappings 與 required_ml；僅影響未來新建 mapping 的 LAB 距離自動配色結果。
> 每次校正都會寫入 `physical_color_rgb_history` 一筆 audit snapshot。

### GET /admin/colors/{id}/rgb-history
**權限**：admin｜列出此實體色的 RGB 變動歷史（時間倒序）

```json
Response 200: {
  "items": [
    { "id": "uuid", "rgb": [255, 136, 0],
      "changed_by_user_id": "uuid|null",
      "changed_by_name": "string|null",
      "note": "initial|manual|revert from <id>",
      "created_at": "datetime" }
  ]
}
```

### POST /admin/colors/{id}/rgb-revert
**權限**：admin｜還原實體色 RGB 到指定的歷史版本

```json
Request:  { "history_id": "uuid" }
Response 200: PhysicalColor 完整物件
Response 404: history_id 不存在或不屬於此實體色
```
> 還原也會寫入新的 audit snapshot（`note="revert from <history_id>"`），保留完整 audit trail。

### PATCH /admin/colors/{id}/stock
**權限**：admin｜更新庫存並觸發預購等待掃描

```json
Request:  { "add_ml": 500 }
Response 200: { "new_stock_ml": 750, "fulfilled_orders": 3 }
```
> 回應後系統自動：掃描 preorder 訂單 → 庫存足夠者自動升單（fulfilled_qty 更新、stock_ml 扣減）→ 寄 email 通知客戶 → 建立 admin_notification

### GET /admin/colors/shortage-dashboard
**權限**：admin｜預購缺貨儀表板

```json
Response 200: {
  "items": [{
    "color_id": "uuid", "code": "201", "name": "SKIN TONE",
    "stock_ml": 100, "required_ml": 450, "shortage_ml": 350,
    "waiting_orders": 5
  }]
}
```

---

## 模組九：調色盤對應（Admin）

### GET /admin/production/jobs/{id}/palette-mappings
**權限**：admin

```json
Response 200: {
  "mappings": [{
    "template_id": 1,
    "algorithm_rgb": [247, 167, 132],
    "physical_color": { "id": "uuid", "code": "201", "name": "SKIN TONE", "rgb": [247, 167, 132], "stock_ml": 500 },
    "required_ml": null,
    "mapped_by": "system"
  }]
}
```

### PUT /admin/production/jobs/{id}/palette-mappings/{template_id}
**權限**：admin｜修改單一顏色對應

```json
Request:  { "physical_color_id": "uuid" }
```

### POST /admin/production/jobs/{id}/palette-mappings/copy-from/{source_job_id}
**權限**：admin｜從其他 job 複製對應（按 template_id 複製）

### POST /admin/production/jobs/{id}/palette-mappings/complete
**權限**：admin｜標記顏色對應完成，觸發 required_ml 計算

```json
Response 200: { "all_stocked": true, "shortage_colors": [] }
```

---

## 模組十：購物車

### GET /cart
**權限**：auth

```json
Response 200: {
  "items": [{
    "id": "uuid", "variant_id": "uuid",
    "product_title": "string",
    "variant_spec": { "canvas_w_cm": 30, "canvas_h_cm": 40, "difficulty": "beginner", "detail": "standard", "color_count": 18 },
    "unit_price": 397, "quantity": 2,
    "fulfilled_units": 2, "preorder_units": 0,
    "is_active": true
  }],
  "subtotal": 794
}
```
> is_active=false 的項目灰色顯示，結帳時拒絕

### POST /cart/items
**權限**：auth

```json
Request:  { "variant_id": "uuid", "quantity": 1 }
Response 409: 商品已下架
```

### PATCH /cart/items/{id}
**權限**：auth

```json
Request:  { "quantity": 3 }
```

### DELETE /cart/items/{id}
**權限**：auth

### POST /cart/checkout-preview
**權限**：auth｜結帳前預覽金額（不扣庫存）

折扣優先順序：① `promo_code` 有填 → 以 public_code 為準，不套 auto_checkout；② `user_coupon_id` 有填 → 套持有券，不套 auto_checkout；③ 兩者皆 null → 自動套用符合條件的 auto_checkout（取折扣最高者）。

```json
Request: {
  "shipping_type": "home|seven_eleven|family_mart",
  "user_coupon_id": "uuid|null",
  "promo_code": "string|null"
}
Response 200: {
  "subtotal": 794,
  "discount_amount": 100,
  "discount_source": "coupon|auto_checkout|null",
  "shipping_fee": 0,
  "total": 694,
  "free_shipping_reason": "amount|quantity|null",
  "has_preorder": true,
  "split_items": [{
    "variant_id": "uuid", "quantity": 3,
    "fulfilled_qty": 1, "preorder_qty": 2
  }]
}
```

---

## 模組十一：訂單（用戶）

### POST /orders
**權限**：auth｜結帳建立訂單

```json
Request: {
  "shipping_profile_id": "uuid",
  "shipping_preference": "together|separate",
  "user_coupon_id": "uuid|null",
  "promo_code": "string|null",
  "customer_notes": "string|null"
}
```
> SELECT FOR UPDATE 鎖定 physical_colors 計算並立即扣減 stock_ml  
> 若有下架變體回 409

```json
Response 201: {
  "order_id": "uuid",
  "order_number": "PL-20260418-000001",
  "total": 694,
  "payment_deadline": "2026-04-19T12:00:00Z",
  "payment_info": { "bank_name": "string", "bank_account_name": "string", "bank_account_number": "string" }
}
```

### GET /orders
**權限**：auth

Query: `?status=pending_payment|paid|processing|shipped|completed|cancelled|refund_processing|refunded|partially_refunded&page=1&page_size=10`

### GET /orders/{id}
**權限**：auth

```json
Response 200: {
  "id": "uuid", "order_number": "string", "status": "string",
  "subtotal": 794, "discount_amount": 100, "discount_source": "coupon", "auto_checkout_config_id": "uuid|null",
  "shipping_fee": 0, "total": 694,
  "shipping_type": "home",
  "shipping_snapshot": { "recipient_name": "...", "phone": "...", "notify_email": null, "city": "台北市", "district": "信義區", "address_detail": "忠孝東路一段1號", "store_id": null, "store_name": null },
  "payment_deadline": "2026-04-19T12:00:00Z",
  "paid_at": null,
  "items": [{
    "product_title_snapshot": "string",
    "variant_spec_snapshot": {...},
    "unit_price": 397, "quantity": 3,
    "fulfilled_qty": 1, "preorder_qty": 2,
    "production_progress": {
      "status": "pending|in_production|manufacturing|packaging|ready_to_ship|shipped",
      "notes": "string|null"
    }
  }],
  "shipments": [{ "shipment_type": "fulfilled", "status": "pending", "tracking_number": null }],
  "customer_notes": null,
  "can_cancel": true,
  "can_confirm_received": false
}
```

### POST /orders/{id}/payment-submission
**權限**：auth｜提交付款資訊

```json
Request: {
  "transfer_amount": 694,
  "transfer_date": "2026-04-18",
  "transfer_time": "14:30:00",
  "account_last5": "12345",
  "notes": "string|null"
}
```

### POST /orders/{id}/confirm-received
**權限**：auth｜確認收貨（僅 status=shipped 時可操作）

### POST /orders/{id}/confirm-refund
**權限**：auth｜客戶確認已收到退款（僅 status ∈ {refunded, partially_refunded} 且 refund_confirmed_at IS NULL 時可操作）

> UPDATE orders.refund_confirmed_at = now()；純記錄用，不影響訂單狀態機

```json
Response 204
```

### POST /orders/{id}/cancel
**權限**：auth｜取消訂單（僅 pending_payment 狀態可取消）

```json
Request:  { "cancel_reason": "string|null" }
```
> 回補 stock_ml，若有使用折扣券則回補 is_used=false

---

## 模組十二：訂單管理（Admin）

### GET /admin/orders
**權限**：admin

Query: `?status=&search=（訂單編號/客戶名/email）&date_from=&date_to=&order_type=regular|custom&page=1&page_size=20`

### GET /admin/orders/{id}
**權限**：admin｜完整訂單詳情（含 payment_submissions、production_progress、shipments）

### PATCH /admin/orders/{id}/status
**權限**：admin｜手動推進訂單狀態（SELECT FOR UPDATE）

```json
Request: { "status": "paid|processing|shipped|completed|refund_processing|cancelled", "admin_notes": "string|null" }
```
> `cancelled` 僅允許從 `pending_payment` 狀態轉換；`paid` 之後不可直接取消，必須走 `POST /admin/orders/{id}/refund` 流程  
> paid → 觸發付款確認 email，建立 production_progress 記錄  
> 若為客製訂單進入 paid → 發 custom_order_paid 通知

### POST /admin/orders/{id}/shipments
**權限**：admin｜建立出貨批次（呼叫 ECpay API）

```json
Request: { "shipment_type": "fulfilled|preorder" }
Response 201: { "shipment_id": "uuid", "tracking_number": "string", "ecpay_logistics_id": "string" }
Response 502: ECpay API 失敗，訂單狀態不變
```
> ECpay API 呼叫成功後立即自動：`shipments.status = 'shipped'`、`shipped_at = now()`，無需管理員手動標記。寄出貨通知 email，並將對應 production_progress 推進至 shipped。

### PATCH /admin/orders/{id}/production-progress/{progress_id}
**權限**：admin｜更新生產進度

```json
Request: { "status": "manufacturing|packaging|ready_to_ship", "notes": "string|null" }
```
> in_production 狀態由 production_job 完成時自動推進，不由此 endpoint 觸發

### POST /admin/orders/{id}/refund
**權限**：admin

```json
Request: {
  "refund_amount": 397,
  "returned_item_ids": ["uuid", "uuid"],
  "cancel_reason": "string"
}
```
> `returned_item_ids`：勾選要退回的 order_items（庫存回補只針對這些 items）  
> 若 returned_item_ids 包含全部 items → status=refunded（全額退款）；coupon 回補 is_used=false；public_code total_used -1  
> 若 returned_item_ids 為部分 items → status=partially_refunded；coupon **不回補**；stock 只回補勾選項  
> 回饋券撤銷依「剩餘金額是否仍 ≥ trigger_threshold」判斷（見 admin_orders.md §5.7）

### PATCH /admin/orders/{id}/payment-submissions/{sub_id}/flag
**權限**：admin｜標記付款資訊有誤，寄 email 通知客戶重新填寫

```json
Request:  { "is_flagged": true, "admin_note": "string" }
Response 200: { "payment_deadline": "2026-04-20T12:00:00Z" }
```
> flag 後系統自動將 `orders.payment_deadline` 重設為 now()+24h；客戶透過現有 `POST /orders/{id}/payment-submission` 重新提交

### PATCH /admin/orders/{id}/admin-notes
**權限**：admin｜任何狀態下均可修改

```json
Request: { "admin_notes": "string" }
```

---

## 模組十三：客製申請（用戶）

### POST /custom-requests
**權限**：auth

```json
Request: {
  "request_type": "custom_photo|custom_spec",
  "photo_url": "string|null",
  "ref_product_id": "uuid|null",
  "canvas_w_cm": 30, "canvas_h_cm": 40,
  "difficulty": "beginner|null",
  "detail": "rough|null",
  "customer_notes": "string|null"
}
Response 201: { "id": "uuid" }
```
> 建立後系統自動發送歡迎訊息（sender_type=admin）

### GET /custom-requests
**權限**：auth

Query: `?status=&page=1&page_size=10`

### GET /custom-requests/{id}
**權限**：auth

```json
Response 200: {
  "id": "uuid", "request_type": "string", "status": "string",
  "canvas_w_cm": 30, "canvas_h_cm": 40,
  "difficulty": "beginner|null", "detail": "rough|null",
  "quoted_price": null, "quote_expires_at": null, "is_extended": false,
  "order_id": null,
  "messages": [{ "sender_type": "admin|customer", "message": "string", "created_at": "datetime" }]
}
```

### POST /custom-requests/{id}/messages
**權限**：auth｜發送訊息

```json
Request: { "message": "string" }
```
> 若管理員有活躍 SSE 連線 → 即時推送；否則 → 寄 email

### PATCH /custom-requests/{id}/photo
**權限**：auth｜更換照片

```json
Request: { "photo_url": "string" }
```
> 舊照片立即從 Firebase 刪除

### GET /custom-requests/{id}/sse
**權限**：auth｜SSE 即時推送新訊息

---

## 模組十四：報價確認（用戶）

### GET /custom/quote/{token}
**權限**：auth（token 驗證）

```json
Response 200: {
  "custom_request_id": "uuid", "spec_summary": {...},
  "quoted_price": 1500, "quote_expires_at": "datetime", "is_extended": false
}
Response 404: token 無效｜Response 410: 已逾期
```

### POST /custom/quote/{token}/confirm
**權限**：auth｜確認報價，填寫收件資訊，建立訂單

```json
Request: { "shipping_profile_id": "uuid" }
Response 201: {
  "order_id": "uuid", "order_number": "string",
  "total": 1570,
  "payment_deadline": "datetime",
  "payment_info": { "bank_name": "string", "bank_account_name": "string", "bank_account_number": "string" }
}
```
> 客製訂單不套用折扣券與 auto_checkout

### POST /custom/quote/{token}/reject
**權限**：auth

```json
Request: { "reason": "string|null" }
Response 200: { "id": "uuid", "status": "quote_rejected", "rejected_at": "datetime" }
```

### POST /custom/quote/{token}/extend
**權限**：auth｜延長報價 1 天（每筆限一次）

```json
Response 200: { "quote_expires_at": "datetime", "is_extended": true }
Response 400 { "code": "QUOTE_ALREADY_EXTENDED" }: 已使用過延長機會
```

### POST /custom/quote/{token}/request-revision
**權限**：auth｜客戶要求修改報價（限 3 次）

```json
Request: { "reason": "string" }
Response 200: { "id": "uuid", "status": "draft_revision", "revision_count": 1 }
Response 400 { "code": "REVISION_LIMIT_EXCEEDED" }: 已達修改上限
```
> 觸發 E11-B：custom_requests.status: quote_sent → draft_revision；revision_count += 1；建立客戶訊息；通知管理員

---

## 模組十五：客製申請管理（Admin）

### GET /admin/custom-requests
**權限**：admin

Query: `?status=quote_pending|negotiating|quote_sent|quote_confirmed|quote_rejected|quote_expired&request_type=custom_photo|custom_spec&page=1&page_size=20`

### GET /admin/custom-requests/{id}
**權限**：admin

### PATCH /admin/custom-requests/{id}/mark-negotiating
**權限**：admin｜手動標記洽談中

### POST /admin/custom-requests/{id}/quote
**權限**：admin｜送出報價

```json
Request: {
  "quoted_price": 1500,
  "detail": "standard",
  "surcharge_ids": ["uuid"],
  "quote_note": "string|null"
}
Response 200: { "quote_expires_at": "datetime" }
```
> 寄報價確認 email（含 /custom/quote/:token 連結）

### POST /admin/custom-requests/{id}/messages
**權限**：admin

```json
Request: { "message": "string" }
```
> 若客戶有活躍 SSE 連線 → 即時推送；否則 → 寄 email

### GET /admin/custom-requests/{id}/photo-signed-url
**權限**：admin｜取得客製照片簽名 URL（15分鐘 TTL）

```json
Response 200: { "url": "https://...", "expires_at": "datetime" }
```
> Module 10 為 stub：直接回 photo_url + 假 expires_at；正式上線前以 Firebase Admin SDK 替換

### GET /admin/custom-requests/sse
**權限**：admin｜SSE 推送（訊息、新申請通知）

---

## 模組十六：折扣系統

### GET /users/me/coupons
**權限**：auth

```json
Response 200: {
  "available": [{ "id": "uuid", "coupon_type": "new_user", "discount_type": "percentage", "discount_value": 10, "min_purchase": 300, "expires_at": "datetime" }],
  "used": [...], "expired": [...]
}
```

### POST /promo-codes/validate
**權限**：auth

```json
Request:  { "code": "SALE2026", "subtotal": 794 }
Response 200: { "valid": true, "discount_type": "fixed", "discount_value": 100 }
Response 400: 代碼無效 / 未達門檻 / 已達使用上限
```

### GET /admin/coupon-configs
**權限**：admin

```json
Response 200: {
  "items": [{
    "id": "uuid", "coupon_type": "new_user|spend_reward|returning_loyal|manual|auto_checkout",
    "discount_type": "percentage|fixed", "discount_value": 10, "min_purchase": 300,
    "is_active": true, "params": {...}, "updated_at": "timestamp"
  }]
}
```

### GET /admin/coupon-configs/{id}/usage-stats
**權限**：admin｜查看單一券類型使用統計

```json
Response 200: {
  "total_issued": 150, "total_used": 87, "total_discount_amount": 8700,
  "usage_by_month": [{ "month": "2026-04", "issued": 30, "used": 20, "discount_amount": 2000 }]
}
```

### PATCH /admin/coupon-configs/{id}
**權限**：admin｜更新非 auto_checkout 類型設定

```json
Request: { "is_active": true, "discount_type": "percentage", "discount_value": 10, "min_purchase": 300, "params": {...} }
```

### POST /admin/coupon-configs/auto-checkout
**權限**：admin｜新增 auto_checkout 促銷

```json
Request: { "discount_type": "fixed", "discount_value": 50, "min_purchase": 500, "params": { "trigger_threshold": 500, "start_at": "2026-05-01", "end_at": "2026-05-31" } }
```

### DELETE /admin/coupon-configs/{id}
**權限**：admin｜僅限 coupon_type=auto_checkout

### GET /admin/promo-codes
**權限**：admin

### POST /admin/promo-codes
**權限**：admin

```json
Request: { "code": "SALE2026", "discount_type": "fixed", "discount_value": 100, "min_purchase": 500, "start_at": null, "end_at": null, "max_total_uses": 100, "max_per_user": 1 }
```

### PUT /admin/promo-codes/{id}
**權限**：admin

### DELETE /admin/promo-codes/{id}
**權限**：admin

### GET /admin/user-coupons
**權限**：admin

Query: `?user_id=uuid&coupon_type=&is_used=true|false`

---

## 模組十七：通知系統（Admin）

### GET /admin/notifications
**權限**：admin

Query: `?status=unhandled|in_progress|completed&requires_action=true|false&page=1&page_size=20`

```json
Response 200: {
  "items": [{
    "id": "uuid", "type": "string", "message": "string",
    "requires_action": true,
    "status": "unhandled|in_progress|completed",
    "reference_type": "order|custom_request|physical_color|null",
    "reference_id": "uuid|null",
    "created_at": "timestamp"
  }],
  "total": 50, "page": 1, "page_size": 20
}
```

### GET /admin/notifications/sse
**權限**：admin｜SSE 長連線，推送新通知給所有活躍管理員

> Railway heartbeat：每 30 秒推送 `: heartbeat\n\n`

### PATCH /admin/notifications/{id}/status
**權限**：admin

```json
Request: { "status": "in_progress|completed" }
```

### PATCH /admin/notifications/bulk-complete
**權限**：admin｜批次標記已完成

```json
Request: { "ids": ["uuid"] }
```

---

## 模組十八：內容管理

### GET /pages/{slug}
**權限**：public

### GET /admin/pages
**權限**：admin

### PUT /admin/pages/{slug}
**權限**：admin

```json
Request: { "title": "string", "content": "string（Markdown）" }
```

### GET /system-settings/public
**權限**：public｜僅回傳前台需要的設定（免運門檻、商品說明、銀行帳號等）

### GET /admin/system-settings
**權限**：admin

### PATCH /admin/system-settings
**權限**：admin

```json
Request: { "key": "free_shipping_amount", "value": "800" }
```

### GET /custom-cases
**權限**：public

Query: `?category_id=uuid&page=1&page_size=12`

### GET /custom-cases/{id}
**權限**：public

### POST /admin/custom-cases
**權限**：admin

```json
Request: { "image_url": "string", "title": "string", "description": "string|null", "category_id": "uuid|null", "canvas_w_cm": 30, "canvas_h_cm": 40, "difficulty": "beginner|null", "is_published": false }
```

### PUT /admin/custom-cases/{id}
**權限**：admin

### DELETE /admin/custom-cases/{id}
**權限**：admin

### PATCH /admin/custom-cases/{id}/toggle-publish
**權限**：admin

### GET /admin/case-categories
**權限**：admin

### POST /admin/case-categories
**權限**：admin

```json
Request: { "name": "string" }
```

### PUT /admin/case-categories/{id}
**權限**：admin

### DELETE /admin/case-categories/{id}
**權限**：admin｜ON DELETE SET NULL → 該分類案例改為「未分類」

### GET /admin/custom-photo-prices
**權限**：admin

### PUT /admin/custom-photo-prices/{id}
**權限**：admin

```json
Request: { "price": 800 }
```

### GET /admin/custom-photo-surcharges
**權限**：admin

### POST /admin/custom-photo-surcharges
**權限**：admin

```json
Request: { "category": "人物數量", "label": "2人", "amount": 200 }
```

### PUT /admin/custom-photo-surcharges/{id}
**權限**：admin

### PATCH /admin/custom-photo-surcharges/{id}/toggle-active
**權限**：admin

### DELETE /admin/custom-photo-surcharges/{id}
**權限**：admin

---

## 模組十九：上傳

> **上傳流程**（Signed URL 模式，前端直傳 Firebase）：
> 1. 前端 `POST /upload/<kind>` 帶 `{filename, content_type, size}` → 後端回 `{upload_url, public_url|firebase_path, expires_at}`
> 2. 前端在 `expires_at` 之前用 `PUT` 把檔案直接上傳到 `upload_url`（**不經過後端**）
> 3. 前端把 `public_url`（或 `firebase_path`）作為實體欄位值，呼叫對應 CRUD 端點存入 DB
>
> 後端不處理檔案二進位，靠前端 MIME/size 預檢 + Firebase Storage Rules 守。size 上限 20MB（schema 422 守門）。

### POST /upload/product-image
**權限**：admin

```json
Request:  { "filename": "cover.jpg", "content_type": "image/jpeg", "size": 524288 }
Response 200: {
  "upload_url": "https://storage.googleapis.com/...?X-Goog-Signature=...",
  "public_url": "https://storage.googleapis.com/<bucket>/product_images/<token>_cover.jpg",
  "expires_at": "2026-04-27T12:15:00+00:00"
}
```

### POST /upload/custom-photo
**權限**：auth｜私有上傳（回 firebase_path 而非 public_url，讀取需另外簽名）

```json
Request:  { "filename": "photo.jpg", "content_type": "image/jpeg", "size": 1048576 }
Response 200: {
  "upload_url": "https://...",
  "firebase_path": "custom_photos/<token>_photo.jpg",
  "expires_at": "2026-04-27T12:15:00+00:00"
}
```

### POST /upload/case-image
**權限**：admin｜契約同 product-image

### POST /upload/production-image
**權限**：admin｜契約同 product-image

### POST /upload/payment-screenshot
**權限**：auth（暫不實作，payment_submissions 暫不含截圖欄位）

### 共通 422 情境
- `size > 20_000_000`：超過 20MB 上限
- `size <= 0`：無效大小
- `content_type` 非 `image/jpeg|image/png`

---

## 模組二十：Webhook

### POST /webhooks/ecpay
**權限**：public（驗證 CheckMacValue）

> ECpay 物流狀態回調。後端驗證 CheckMacValue，失敗回 400。  
> 收到「已取貨 / 已投遞」事件 → shipment.status = delivered + delivered_at = now()  
> 若該訂單所有 shipments 均 delivered → order.status = completed，發完成 email + 觸發回饋券  
> 其他中間狀態（派送中等）→ 建立 ecpay_status 類型 admin_notification，不改訂單狀態

---

## 模組二十一：銷售報表（Admin）

### GET /admin/reports/sales
**權限**：admin

Query: `?date_from=2026-01-01&date_to=2026-04-30`

```json
Response 200: {
  "period": { "from": "2026-01-01", "to": "2026-04-30" },
  "total_orders": 54,
  "total_revenue": 32000,
  "note": "僅計算 status=completed 且未完全退款的訂單；部分退款以 total - refund_amount 計入"
}
```
