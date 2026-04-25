# Module 10 - 客製訂單系統（custom）

> 客製申請 → 管理員報價 → 客戶確認 → 建立訂單（接 Module 09 訂單流）。包含照片/規格申請、訊息往來、報價 token、報價延長/拒絕/要求修改、自動逾期。

---

## 1. 檔案清單

```
backend/custom/
├── __init__.py
├── models.py
├── router.py
├── service.py
├── tasks.py                     # Celery: 報價逾期掃描（E12）
└── schemas/
    ├── __init__.py
    ├── request.py
    └── response.py

backend/tests/custom/
├── __init__.py
└── test_custom.py

backend/migrations/versions/
└── d4e5f6a7b8c9_create_custom_tables.py    # 建立所有 custom_ 表 + 補 FK

docs/module_plans/10_custom.md            # 本檔
```

修改既有：
- `backend/orders/models.py` → `OrderItem.custom_request_id` 改為 `ForeignKey("custom_requests.id")`
- `backend/production/models.py` → `ProductionJob.custom_request_id` 改為 `ForeignKey("custom_requests.id")`
- `backend/orders/service.py` → 新增 `_create_order_from_custom_request()`（E14/E15）；`admin_update_order_status → paid` 偵測客製訂單觸發 `custom_order_paid` 通知
- `backend/production/service.py` → `create_jobs()` 在 `custom_request_id` 非 null 時自動 `custom_requests.status: quote_pending → negotiating` + 標 `quote_pending` 通知為 completed（E26）
- `backend/main.py` → 註冊 custom router

---

## 2. DB 模型

### custom_requests

```python
class CustomRequestTypeEnum(StrEnum):
    custom_photo
    custom_spec

class CustomRequestStatusEnum(StrEnum):
    quote_pending
    negotiating
    quote_sent
    draft_revision
    quote_confirmed
    quote_rejected
    quote_expired
```

| 欄位 | 型別 | 限制 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | NOT NULL, FK → users.id |
| request_type | Enum(CustomRequestTypeEnum) | NOT NULL |
| status | Enum(CustomRequestStatusEnum) | NOT NULL, default `quote_pending` |
| photo_url | VARCHAR | nullable |
| ref_product_id | UUID | nullable, FK → products.id |
| canvas_w_cm | INTEGER | nullable |
| canvas_h_cm | INTEGER | nullable |
| difficulty | Enum(DifficultyEnum) | nullable |
| detail | Enum(DetailEnum) | nullable |
| customer_notes | TEXT | nullable |
| quoted_price | NUMERIC(10,2) | nullable |
| quote_token | VARCHAR | nullable, UNIQUE（hash 後存）|
| quote_expires_at | TIMESTAMP | nullable |
| is_extended | BOOLEAN | NOT NULL, default false |
| revision_count | INTEGER | NOT NULL, default 0 |
| parent_request_id | UUID | nullable, FK → custom_requests.id |
| order_id | UUID | nullable, FK → orders.id |
| admin_notes | TEXT | nullable |
| created_at | TIMESTAMP | NOT NULL, default now() |
| quoted_at | TIMESTAMP | nullable |

CHECK 限制：
- `request_type='custom_spec'` → `ref_product_id NOT NULL`
- `request_type='custom_photo'` → `photo_url NOT NULL`

### custom_request_messages

| id | UUID PK |
| request_id | UUID NOT NULL FK → custom_requests.id |
| sender_type | Enum('admin','customer') NOT NULL |
| message | TEXT NOT NULL |
| created_at | TIMESTAMP DEFAULT now() |

### custom_photo_prices（管理員報價基準表）

| id, canvas_w INT, canvas_h INT, difficulty Enum, price NUMERIC(10,2) |
| UNIQUE(canvas_w, canvas_h, difficulty) |

### custom_photo_surcharges（管理員可選加費項目）

| id, category VARCHAR, label VARCHAR, amount NUMERIC(10,2), is_active BOOLEAN, created_at |

### canvas_sizes

| id, canvas_w_cm INT, canvas_h_cm INT, display_name VARCHAR, sort_order INT, is_active BOOLEAN, created_at |
| UNIQUE(canvas_w_cm, canvas_h_cm) |

---

## 3. Migration

- 建表：`custom_requests`、`custom_request_messages`、`custom_photo_prices`、`custom_photo_surcharges`、`canvas_sizes`
- 補 FK：`order_items.custom_request_id` → `custom_requests.id`、`production_jobs.custom_request_id` → `custom_requests.id`
- Index：`custom_requests(user_id, status)`、`custom_requests(quote_token)`（UNIQUE）、`custom_requests(quote_expires_at)` (for Celery scan)
- 種子：插入 17 種標準 `canvas_sizes`（20×20、30×30、30×40 ⋯）

---

## 4. Endpoint 業務流程

### 4.1 客戶端（require_auth）

#### `POST /custom-requests` (E07)
- 驗證：`request_type=custom_spec` → `ref_product_id` 必填且 product 存在
- 驗證：`request_type=custom_photo` → `photo_url` 必填
- INSERT custom_request（status=quote_pending, revision_count=0）
- INSERT custom_request_message（sender_type=admin, message=系統歡迎訊息，從 `system_settings.quote_reply_days` 內崁天數）
- INSERT admin_notification（type=quote_pending, requires_action=true, reference_type=custom_request, reference_id）
- Email 客戶（"客製申請已收到，預計 X 工作天回覆"）
- Response 201: `{ id }`

#### `GET /custom-requests`
- Filter: `status?`, `page=1`, `page_size=10`
- ORDER BY created_at DESC
- Response: `{ items: [{id, request_type, status, created_at, quoted_price, quote_expires_at}], total, page, page_size }`

#### `GET /custom-requests/{id}`
- 驗證 owner
- Response: full request + `messages: [...]`（時間順序）

#### `POST /custom-requests/{id}/messages` (E10)
- 驗證 owner
- INSERT message（sender_type=customer）
- create_notification（type=new_message, requires_action=false）
- Email 管理員（三層判斷在 SSE 完成後再做；本 module 統一發郵件）
- Response 201

#### `PATCH /custom-requests/{id}/photo` (E18)
- 前置：status=quote_pending（其他 → 409）
- 驗證 owner
- 覆蓋 photo_url（Firebase 刪舊檔屬於外部 stub，記 TODO；本模組僅更新欄位）
- Response: 204

### 4.2 報價 token 端點（auth + token）

#### `GET /custom/quote/{token}`
- 用 hash(token) 查 custom_requests.quote_token
- 驗證 owner（current_user.id == request.user_id）
- 驗證 status=quote_sent，quote_expires_at > now() → 否則 410
- Response: `{ custom_request_id, spec_summary: {canvas_w_cm, canvas_h_cm, difficulty, detail}, quoted_price, quote_expires_at, is_extended, revision_count }`

#### `POST /custom/quote/{token}/confirm` (E14/E15)
- 前置：status=quote_sent，未過期
- Request: `{ shipping_profile_id }`
- 驗證 shipping_profile 屬於 user
- 反查 production_job：`SELECT FROM production_jobs WHERE custom_request_id = request.id AND approved=true`（取最新 approved）
- 計算 shipping_fee（home=120, conv=70；客製訂單**不適用免運門檻**）
- 計算 total = quoted_price + shipping_fee
- INSERT order（status=pending_payment, payment_deadline=now+24h, no discount, no auto_checkout）
- INSERT order_item（custom_request_id, production_job_id, product_variant_id=null, fulfilled_qty=0, preorder_qty=1, unit_price=quoted_price, product_title_snapshot="客製作品", variant_spec_snapshot from request）
- UPDATE custom_request（status=quote_confirmed, order_id）
- create_notification（type=quote_confirmed, requires_action=false）
- Email 客戶（訂單編號 + 付款帳號 + 24h 期限）
- Response 201: `{ order_id, order_number, total, payment_deadline }`

#### `POST /custom/quote/{token}/reject` (E16)
- 前置：status=quote_sent
- Request: `{ reason: str | null }`
- UPDATE status=quote_rejected
- INSERT message（customer，內容 = reason or "客戶拒絕報價"）
- create_notification（type=quote_rejected）
- Response 204

#### `POST /custom/quote/{token}/extend` (E13)
- 前置：status=quote_sent，is_extended=false
- 已用過 → 400
- UPDATE quote_expires_at += 24h, is_extended=true
- Email 管理員（"客戶已延長報價"）
- Response: `{ quote_expires_at, is_extended }`

#### `POST /custom/quote/{token}/request-revision` (E11-B)
- 前置：status=quote_sent，revision_count < 3
- Request: `{ reason: str }`
- UPDATE status=draft_revision, revision_count += 1
- INSERT message（customer，reason）
- create_notification（type=draft_revision_requested, requires_action=true）
- Email 管理員
- Response 200

### 4.3 管理員端（require_admin）

#### `GET /admin/custom-requests`
- Filter: status, request_type, page, page_size
- JOIN users（user_name, user_email）
- Response: `{ items: [...], total, page, page_size }`

#### `GET /admin/custom-requests/{id}`
- Full detail + messages + user info

#### `POST /admin/custom-requests/{id}/quote` (E11)
- 前置：status ∈ {quote_pending, negotiating, draft_revision}
- Request: `{ quoted_price, detail?, surcharge_ids?, quote_note? }`
- 產生 quote_token = secrets.token_urlsafe(32)；DB 存 hash(token)
- UPDATE custom_request（quoted_price, quoted_at=now, quote_token=hash, quote_expires_at=now+24h, status=quote_sent, detail（如有）, revision_count 保留）
- INSERT message（admin，"報價金額：NT$X，備註：⋯"）
- Email 客戶（filled_template_url 從 production_job 取，連結 `/custom/quote/{plain_token}`）
- Response: `{ quote_expires_at }`

#### `POST /admin/custom-requests/{id}/messages` (E09)
- INSERT message（sender_type=admin）
- Email 客戶
- Response 201

#### `PATCH /admin/custom-requests/{id}/mark-negotiating` (E08)
- UPDATE status=negotiating（從 quote_pending）
- 標 admin_notification(type=quote_pending, reference_id) → completed
- Response 200

#### `GET /admin/custom-requests/{id}/photo-signed-url` (Stub)
- 回傳：`{ url: photo_url, expires_at: now+15min }`（**stub** —實際 Firebase 整合在後續模組補；TODO log warning）

### 4.4 跨模組整合

#### `production/service.create_jobs()` 修補（E26）
- 若 `custom_request_id` 不為 null：
  - SELECT FOR UPDATE custom_request
  - 若 status=quote_pending → status=negotiating
  - 標對應 admin_notification(type=quote_pending, reference_id=custom_request.id) 為 `is_read=true` 或 `requires_action=false`（取決於 model）

#### `orders/service.admin_update_order_status` 修補（E21 客製訂單追加）
- 轉 `paid` 後，若 `order_item.custom_request_id is not null`：
  - create_notification(type=custom_order_paid, requires_action=true)

### 4.5 Celery Task（E12）

`custom/tasks.py`:
```python
@celery.task
def expire_quotes():
    """Every 5 min: status=quote_sent AND quote_expires_at < now() → quote_expired"""
    # SELECT FOR UPDATE 鎖定每筆
    # UPDATE status=quote_expired
    # Email 客戶
```

---

## 5. EVENT_MATRIX 對照

| Event | 實作位置 | 副作用 |
|---|---|---|
| E07 | POST /custom-requests | INSERT custom_request + message + notification, email 客戶 |
| E08 | PATCH mark-negotiating（手動）/ E26 自動 | UPDATE status, 標 notification completed |
| E09 | POST /admin/custom-requests/{id}/messages | INSERT message, email 客戶 |
| E10 | POST /custom-requests/{id}/messages | INSERT message, notification, email 管理員 |
| E11 | POST /admin/custom-requests/{id}/quote | UPDATE quoted_price+token+deadline+status=quote_sent, message, email 客戶 |
| E11-B | POST /custom/quote/{token}/request-revision | UPDATE status=draft_revision, revision_count+1, message, notification |
| E12 | Celery `expire_quotes` | UPDATE status=quote_expired, email 客戶 |
| E13 | POST /custom/quote/{token}/extend | UPDATE expires+24h, is_extended=true, email 管理員 |
| E14/E15 | POST /custom/quote/{token}/confirm | UPDATE status=quote_confirmed, INSERT order+order_item, email 客戶, notification |
| E16 | POST /custom/quote/{token}/reject | UPDATE status=quote_rejected, message, notification |
| E18 | PATCH /custom-requests/{id}/photo | UPDATE photo_url（前置 status=quote_pending 強制）|
| E21（客製分支）| orders.admin_update_order_status → paid | 額外 INSERT notification(type=custom_order_paid) |
| E26 | production.create_jobs | 自動 UPDATE custom_request.status, 標 quote_pending notification completed |

---

## 6. 測試覆蓋（test_custom.py）

### 客戶端
| Case | 預期 | 測試函數 |
|---|---|---|
| POST custom_photo 成功 | 201 | test_create_custom_photo_request |
| POST custom_spec 缺 ref_product_id | 422/400 | test_create_custom_spec_missing_ref_product |
| POST custom_photo 缺 photo_url | 422/400 | test_create_custom_photo_missing_photo |
| POST 自動建立歡迎訊息 | message exists | test_create_request_seeds_welcome_message |
| GET 列出自己 | 200 | test_list_own_custom_requests |
| GET 不屬於自己 | 404 | test_get_others_custom_request_404 |
| POST messages 客戶 | 201 + DB 記錄 | test_post_customer_message |
| PATCH photo 在 quote_pending | 204 | test_patch_photo_in_quote_pending |
| PATCH photo 在 negotiating 拒絕 | 409 | test_patch_photo_after_negotiating_rejected |

### 管理員端
| Case | 預期 | 測試函數 |
|---|---|---|
| Admin GET list+filter | 200 | test_admin_list_custom_requests |
| Admin POST messages | 201 | test_admin_post_message |
| Admin PATCH mark-negotiating | 200 + notification 標完成 | test_admin_mark_negotiating |
| Admin POST quote 成功 | 200 + token issued | test_admin_send_quote |
| Admin POST quote 在 quote_confirmed 後拒絕 | 400 | test_admin_quote_already_confirmed_rejected |
| Admin GET photo-signed-url | 200 + url 含 expires_at | test_admin_get_photo_signed_url |

### 報價 token 流程
| Case | 預期 | 測試函數 |
|---|---|---|
| GET /custom/quote/{token} 有效 | 200 | test_get_quote_summary |
| GET 過期 token | 410 | test_get_expired_quote |
| GET 無效 token | 404 | test_get_invalid_quote |
| POST confirm 成功（建立 order）| 201 + order_id | test_confirm_quote_creates_order |
| POST confirm 同時更新 custom_request.order_id 與 status | DB 對應 | test_confirm_quote_updates_status |
| POST confirm 包含 custom_request_id 在 order_item | 對應 | test_confirm_quote_links_order_item |
| POST extend 第一次成功 | 200 | test_extend_quote_first_time |
| POST extend 第二次拒絕 | 400 | test_extend_quote_twice_rejected |
| POST reject | 204 + status=quote_rejected | test_reject_quote |
| POST request-revision 成功 | 200 + revision_count+1 | test_request_revision |
| POST request-revision 第 4 次拒絕 | 400 | test_request_revision_max_exceeded |

### 跨模組
| Case | 預期 | 測試函數 |
|---|---|---|
| production.create_jobs 帶 custom_request_id 自動 negotiating | status changes | test_create_jobs_auto_marks_negotiating |
| orders.paid 客製訂單觸發 custom_order_paid notification | notification exists | test_paid_custom_order_creates_notification |

### Celery Task
| Case | 預期 | 測試函數 |
|---|---|---|
| expire_quotes 過期 quote_sent → quote_expired | direct call test | test_expire_quotes_marks_expired |
| expire_quotes 不影響 quote_confirmed | not changed | test_expire_quotes_skips_confirmed |

---

## 7. 待確認事項

### ⚠️ A — `revision_count = 3` 達上限的 UI/錯誤訊息歸誰處理
規格書未指明達 3 次後的提示文字。本模組只回 400 + `{detail: "已達修改次數上限"}`，前端自行決定 UI。

### ⚠️ B — Firebase 簽名 URL stub
`GET /admin/custom-requests/{id}/photo-signed-url` 在本模組為 stub，回傳原始 photo_url 並標記 expires_at = now+15min。正式上線前需以 Firebase Admin SDK 替換（已在 backend 預留 `paint-by-number-d9fa3-firebase-adminsdk*.json`）。

### ⚠️ C — SSE 端點 (`/custom-requests/{id}/sse`、`/admin/custom-requests/sse`)
本模組**不實作**SSE，視為 Phase 2。所有訊息通知統一以 email 通道為主，admin notification 為輔。

### ⚠️ D — `parent_request_id` 重新申請流程
EVENT_MATRIX E18 提到「重新申請時指向原申請」。本模組保留欄位但不提供端點觸發此流程；若客戶被拒絕後想重新申請，客戶就再 POST /custom-requests 一次（前端可帶上 parent_request_id 在 customer_notes）。
