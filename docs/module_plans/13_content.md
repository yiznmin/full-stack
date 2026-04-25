# Module 13 - 內容管理（content）

> 統一管理：靜態頁面（pages）、系統設定（system_settings）、客製案例（custom_cases + case_categories）、客製定價基準（custom_photo_prices + custom_photo_surcharges）。共 23 個 endpoint（4 public + 19 admin）。

## 1. 檔案清單

新建：
- `backend/content/__init__.py`
- `backend/content/models.py` — Page、CustomCase、CaseCategory
- `backend/content/router.py`
- `backend/content/service.py`
- `backend/content/schemas/__init__.py`
- `backend/content/schemas/request.py`
- `backend/content/schemas/response.py`
- `backend/migrations/versions/f6a7b8c9d0e1_create_content_tables.py`
- `backend/tests/content/__init__.py`
- `backend/tests/content/test_content.py`

修改：
- `backend/main.py` 註冊 router
- `backend/migrations/env.py`、`backend/scripts/reset_test_db.py`、`backend/scripts/drop_test_db.py`、`backend/tests/conftest.py` 加 import

## 2. DB 模型（新增）

### pages
```
id UUID PK
slug VARCHAR NOT NULL UNIQUE
title VARCHAR NOT NULL
content TEXT NOT NULL
updated_at TIMESTAMP NOT NULL DEFAULT now() onupdate now()
```
種子 5 筆：size_guide / shipping / custom_process / pricing_reference / refund_policy

### case_categories
```
id UUID PK
name VARCHAR NOT NULL UNIQUE
created_at TIMESTAMP NOT NULL DEFAULT now()
```

### custom_cases
```
id UUID PK
image_url VARCHAR NOT NULL
title VARCHAR NOT NULL
description TEXT
category_id UUID nullable FK → case_categories.id ON DELETE SET NULL
canvas_w_cm INTEGER nullable
canvas_h_cm INTEGER nullable
difficulty Enum(DifficultyEnum) nullable
is_published BOOLEAN NOT NULL DEFAULT false
created_at TIMESTAMP NOT NULL DEFAULT now()
```

複用既有：
- `color.models.SystemSetting`
- `custom.models.CustomPhotoPrice`
- `custom.models.CustomPhotoSurcharge`

## 3. Endpoint（23）

### Pages
- `GET /pages/{slug}` — public
- `GET /admin/pages` — admin（list all）
- `PUT /admin/pages/{slug}` — admin（upsert：不存在自動建立）

### System Settings
- `GET /system-settings/public` — public（白名單欄位：免運門檻、商品說明、銀行帳號等）
- `GET /admin/system-settings` — admin
- `PATCH /admin/system-settings` — admin（單一 key/value upsert）

### Custom Cases
- `GET /custom-cases?category_id=&page=1&page_size=12` — public（只看 is_published=true）
- `GET /custom-cases/{id}` — public（只看 is_published=true，否則 404）
- `POST /admin/custom-cases` — admin
- `PUT /admin/custom-cases/{id}` — admin
- `DELETE /admin/custom-cases/{id}` — admin
- `PATCH /admin/custom-cases/{id}/toggle-publish` — admin

### Case Categories
- `GET /admin/case-categories` — admin
- `POST /admin/case-categories` — admin
- `PUT /admin/case-categories/{id}` — admin
- `DELETE /admin/case-categories/{id}` — admin（ON DELETE SET NULL → cases.category_id 為 null）

### Custom Photo Prices
- `GET /admin/custom-photo-prices` — admin
- `PUT /admin/custom-photo-prices/{id}` — admin（只能改 price）

### Custom Photo Surcharges
- `GET /admin/custom-photo-surcharges` — admin
- `POST /admin/custom-photo-surcharges` — admin
- `PUT /admin/custom-photo-surcharges/{id}` — admin
- `PATCH /admin/custom-photo-surcharges/{id}/toggle-active` — admin
- `DELETE /admin/custom-photo-surcharges/{id}` — admin

## 4. 業務規則

- **GET /system-settings/public**：白名單回傳。允許的 keys：`bank_account_number`、`bank_name`、`bank_account_name`、`product_info_tools`、`product_info_material`、`product_info_tips`、`product_info_notes`、`quote_reply_days`。其他 key（如 ECPAY_*、payment_absolute_deadline_hours）不洩漏。
- **PUT /admin/pages/{slug}**：upsert（不存在自動建立）。
- **PATCH /admin/system-settings**：單一 key/value upsert。
- **DELETE /admin/case-categories/{id}**：ON DELETE SET NULL（schema 規定）。
- **GET /custom-cases**：只回 `is_published=true`，依 created_at desc + 分頁。
- **PATCH .../toggle-publish**：取反 boolean，回完整物件。
- **PATCH .../toggle-active**：同上。

## 5. EVENT_MATRIX
不觸發任何 Event。純 CRUD。

## 6. 測試覆蓋

| Case | 預期 | 函數名 |
|---|---|---|
| GET /pages/{slug} 存在 | 200 | test_get_page_existing |
| GET /pages/{slug} 不存在 | 404 | test_get_page_not_found |
| GET /admin/pages | 200 + list | test_admin_list_pages |
| PUT /admin/pages/{slug} 新 | 200 + 自動建立 | test_admin_upsert_new_page |
| PUT /admin/pages/{slug} 既有 | 200 + content 更新 | test_admin_update_existing_page |
| GET /system-settings/public 白名單 | 200 + 不含敏感 key | test_public_settings_whitelist |
| GET /admin/system-settings | 200 + 全部 | test_admin_list_settings |
| PATCH /admin/system-settings 新 key | 200 | test_admin_upsert_new_setting |
| PATCH /admin/system-settings 既有 key | 200 + 改值 | test_admin_update_existing_setting |
| GET /custom-cases public 只看 published | 對應 | test_public_cases_published_only |
| GET /custom-cases?category_id 過濾 | 對應 | test_public_cases_filter_category |
| GET /custom-cases/{id} unpublished 拒絕 | 404 | test_public_case_unpublished_404 |
| POST /admin/custom-cases | 201 | test_admin_create_case |
| PUT /admin/custom-cases/{id} | 200 | test_admin_update_case |
| DELETE /admin/custom-cases/{id} | 204 | test_admin_delete_case |
| PATCH toggle-publish | 200 | test_admin_toggle_publish_case |
| GET/POST/PUT/DELETE case-categories | 對應 | test_admin_case_categories_crud |
| DELETE category 後 case.category_id 變 null | 對應 | test_delete_category_sets_null |
| GET /admin/custom-photo-prices | 200 | test_admin_list_photo_prices |
| PUT /admin/custom-photo-prices/{id} | 200 | test_admin_update_photo_price |
| GET/POST/PUT/DELETE custom-photo-surcharges | 對應 | test_admin_surcharges_crud |
| PATCH toggle-active surcharge | 200 | test_admin_toggle_active_surcharge |

## 7. ⚠️ 決議

### A — `pages` 表為新建
api.md 提到 GET /pages/{slug} 但 schema.md 中 pages 表雖列在「資訊頁」區塊。新建 model + migration。

### B — `system_settings` 在 color/models.py
我會 import 它而不重新定義。

### C — Slug 規則
slug 限 `^[a-z0-9_]+$`（lowercase + digits + underscore），長度 1-50。
