# Module 11 - 通知系統（notifications）

> 集中管理員所有系統事件通知。本模組補上 admin 列表/篩選/狀態切換 4 個 endpoint，並把現有 `admin_notifications.is_completed` (Boolean) 升級為 `status` 三態 Enum。

---

## 1. 檔案清單

```
backend/notifications/
├── __init__.py            # 已存在
├── models.py              # 升級 status enum + ref/req 索引
├── router.py              # 新增（4 endpoints）
├── service.py             # 新增 list / update_status / bulk_complete + payment_resubmitted 取代邏輯 + stock_shortage 去重
└── schemas/
    ├── __init__.py
    ├── request.py
    └── response.py

backend/tests/notifications/
├── __init__.py
└── test_notifications.py

backend/migrations/versions/
└── e5f6a7b8c9d0_notifications_status_enum.py    # is_completed → status
```

修改既有：
- `backend/orders/service.py` → `payment_resubmitted` 建立時，標同訂單 `payment_submitted` 為 completed（規格 §73）
- `backend/color/service.py` 或 stock 觸發點 → `stock_shortage` 通知去重（同 physical_color 已有 unhandled/in_progress 則 UPDATE 不新增）
- `backend/custom/service.py` `_mark_quote_pending_notifications_done` → 改用 `status='completed'`
- `backend/notifications/service.py` `create_notification` → 新增可選 `status` 參數（預設 unhandled）
- 既有所有寫 `is_completed=True` 的地方改 `status=NotificationStatusEnum.completed`
- `backend/main.py` 註冊 router

---

## 2. DB 模型

### admin_notifications（升級）

| 欄位 | 型別 | 限制 |
|---|---|---|
| id | UUID | PK |
| type | VARCHAR | NOT NULL |
| requires_action | BOOLEAN | NOT NULL DEFAULT false |
| **status**（新）| Enum('unhandled','in_progress','completed') | NOT NULL DEFAULT 'unhandled' |
| reference_type | VARCHAR | nullable |
| reference_id | UUID | nullable |
| message | TEXT | NOT NULL |
| created_at | TIMESTAMP | NOT NULL DEFAULT now() |
| updated_at | TIMESTAMP | NOT NULL DEFAULT now() onupdate now() |

Index：
- `(status, created_at DESC)` — 列表查詢最常排序
- `(reference_type, reference_id)` — 自動標完成查詢用
- `(type, status, reference_id)` — stock_shortage 去重 + payment_resubmitted 取代查詢

### NotificationStatusEnum

```python
class NotificationStatusEnum(StrEnum):
    unhandled = "unhandled"
    in_progress = "in_progress"
    completed = "completed"
```

---

## 3. Migration 策略

`is_completed` Boolean → `status` Enum：

```python
# upgrade
op.execute("CREATE TYPE notificationstatusenum AS ENUM ('unhandled','in_progress','completed')")
op.add_column('admin_notifications',
    sa.Column('status',
        sa.Enum('unhandled','in_progress','completed', name='notificationstatusenum'),
        nullable=False, server_default='unhandled'))
op.execute(
    "UPDATE admin_notifications SET status = 'completed' WHERE is_completed = true"
)
op.drop_column('admin_notifications', 'is_completed')
op.create_index(...)  # 三個 index
```

downgrade 反向。

---

## 4. Endpoint 業務流程

### 4.1 `GET /admin/notifications`（admin）

- Query：`status?`, `requires_action?`, `page=1`, `page_size=20`
- ORDER BY `created_at DESC`
- Response：`{ items: [...], total, page, page_size }`
- 每筆：`id, type, message, requires_action, status, reference_type, reference_id, created_at, updated_at`

### 4.2 `PATCH /admin/notifications/{id}/status`（admin）

- Request：`{ status: "in_progress|completed" }`
- 不允許從 `completed → unhandled`（單向）
- 不允許從任何狀態回到 `unhandled`
- UPDATE status + onupdate updated_at
- Response 200：完整通知物件

### 4.3 `PATCH /admin/notifications/bulk-complete`（admin）

- Request：`{ ids: [uuid] }`
- 對每筆 SELECT FOR UPDATE，UPDATE status='completed'
- 跳過已 completed 與不存在的
- Response 200：`{ completed_count, processed_ids: [...], skipped_ids: [...] }`

### 4.4 `GET /admin/notifications/sse`（admin）

**本模組不實作**，列為 Phase 2，沿用 Module 10 慣例。
> 規劃書中保留條目但 endpoint 暫不開放。

---

## 5. Cross-module 調整

### 5.1 `notifications/service.create_notification`

新增可選 `status` 參數（預設 `unhandled`）。`reference_id` 已是 UUID，無需變動。

### 5.2 stock_shortage 去重（規格 §73）

新增 `notifications/service.create_or_update_stock_shortage(db, physical_color_id, message)`：

```python
existing = SELECT FROM admin_notifications
   WHERE type='stock_shortage'
   AND reference_type='physical_color'
   AND reference_id=physical_color_id
   AND status IN ('unhandled', 'in_progress')

if existing:
    UPDATE existing.updated_at = now(), existing.message = new_message
else:
    INSERT new notification
```

### 5.3 payment_resubmitted 取代（規格 §36）

在建立 `payment_resubmitted` 時，同 transaction：
```python
UPDATE admin_notifications
SET status='completed',
    message = original_message || '（已被新付款表單取代）'
WHERE type='payment_submitted'
  AND reference_id = order_id
  AND status != 'completed'
```

放入 `notifications/service.create_payment_resubmitted(db, order_id, message)` helper，由 orders 模組呼叫。
（**註：** 目前 `payment_resubmitted` 並未在 orders 模組中觸發；舊的 `submit_payment` 統一發 `payment_submitted`。本模組僅補 helper，orders 後續若要加重新提交區分時可呼叫。）

### 5.4 既有「標 quote_pending 為 completed」改用 status

`custom/service._mark_quote_pending_notifications_done`：
```python
.values(is_completed=True, requires_action=False)  # 舊
→ .values(status=NotificationStatusEnum.completed, requires_action=False)
```

---

## 6. EVENT_MATRIX 對照

本模組不新增 Event；所有既有 Event 寫入 admin_notifications 的呼叫不變，只是欄位名變了。

| 舊呼叫 | 新狀態 |
|---|---|
| 預設建立 | status=unhandled |
| 進入處理 | status=in_progress |
| 完成 | status=completed |
| `_mark_quote_pending_notifications_done` | status=completed |

---

## 7. 測試覆蓋（test_notifications.py）

| Case | 預期 | 測試函數 |
|---|---|---|
| GET list 無 filter | 200 + 全部 | test_list_all_notifications |
| GET list filter status=unhandled | 200 + 只有 unhandled | test_list_filter_status |
| GET list filter requires_action=true | 200 + 只有 requires_action | test_list_filter_requires_action |
| GET list 分頁 | 200 + page/page_size 正確 | test_list_pagination |
| PATCH status unhandled→in_progress | 200 + DB 對應 | test_update_status_to_in_progress |
| PATCH status in_progress→completed | 200 | test_update_status_to_completed |
| PATCH status completed→unhandled 拒絕 | 400 + code=INVALID_STATUS_TRANSITION | test_reject_status_revert |
| PATCH 不存在 id | 404 | test_update_unknown_404 |
| PATCH bulk-complete 多筆 | 200 + count | test_bulk_complete |
| Bulk-complete 跳過已 completed | 200 + skipped | test_bulk_complete_skips_completed |
| stock_shortage 去重：同 color 已有 unhandled → UPDATE 不新增 | 數量不增 | test_stock_shortage_dedup |
| stock_shortage 同 color 已 completed → 新增 | 新筆 | test_stock_shortage_creates_after_completed |
| payment_resubmitted 自動標 payment_submitted 為 completed | 對應 | test_payment_resubmitted_completes_old |
| 非 admin 呼叫 list | 401/403 | test_non_admin_list_rejected |
| 既有 custom mark-negotiating 後 status 為 completed | DB 對應 | test_quote_pending_marked_completed_via_status |

---

## 8. 待確認事項

### ⚠️ A — SSE endpoint 不實作
與 Module 10 一致，`/admin/notifications/sse` 暫不開發，留 Phase 2。

### ⚠️ B — `payment_resubmitted` 觸發點
目前 orders.submit_payment 統一寫 `payment_submitted`。本模組只補通知層 helper（`create_payment_resubmitted`），不修改 orders 行為。**確認：本模組不改 orders submit_payment 規則**。

### ⚠️ C — 「狀態反向」錯誤碼
`PATCH /admin/notifications/{id}/status` 不允許 `completed → unhandled` 或 `in_progress → unhandled`，回 400 + `code=INVALID_STATUS_TRANSITION`。
