# 管理者端：通知中心

管理員後台專屬頁面，集中顯示所有系統通知與待處理事項。

---

## 頁面結構

三個頁籤分類：

| 頁籤 | 說明 |
|------|------|
| 未處理 | 新進通知，尚未開始處理 |
| 處理中 | 管理員已標記正在跟進 |
| 已完成 | 已處理完畢或純資訊通知已讀 |

每筆通知顯示：類型標籤、摘要說明、關聯對象（訂單編號 / 申請 ID）、時間、是否需要手動處理、操作按鈕（前往處理 / 標記完成）。

**即時更新（SSE）**：管理員開啟後台時建立 SSE 連線，新通知產生時推送給**所有**當前有活躍 SSE 連線的 admin，頁籤角標自動更新，不需手動刷新頁面。

---

## 通知類型

### 需要手動處理（`requires_action = true`）

| 類型 | 觸發時機 | 說明 | 前往處理 |
|------|---------|------|---------|
| `quote_pending` | 客戶提交客製申請 | 新客製申請待報價 | 客製申請詳情 |
| `custom_order_paid` | 客製訂單狀態變為 `paid` | 客製訂單已付款，請進入備貨流程（印刷/包裝/出貨） | 訂單詳情 |
| `draft_revision_requested` | 客戶於報價頁點「要求修改」 | 客戶要求修改初稿 | 客製申請詳情頁 |
| `new_message` | 客戶在客製申請對話頁傳訊息（管理員不在頁面時）| 有新訊息待回覆 | 申請對話頁 |
| `payment_submitted` | 客戶填寫付款核對表單 | 付款資訊待核對確認 | 訂單詳情 |
| `payment_resubmitted` | 客戶重新填寫付款核對表單（管理員曾標記有誤）| 客戶已重填，待再次核對 | 訂單詳情 |

> 建立 `payment_resubmitted` 通知時，系統自動將同一訂單的舊 `payment_submitted` 通知標記為 `completed`，並在 `message` 欄位註記「已被新付款表單取代」，避免管理員看到重複的待處理項目。
| `shipment_overdue` | 出貨後 14 天無取貨確認（Celery Beat 每日掃描）| 請確認物流狀況 | 訂單詳情 |
| `stock_shortage` | 進貨更新後仍有預購訂單庫存不足 | 需進貨補充顏料 | 預購缺貨儀表板 |
| `production_failed` | production_job 失敗 | 製作任務失敗，需重新送出 | 製作模組 |
| `batch_completed` | production 批次全部處理完畢 | 批次 #XXX 已完成,N 筆成功、M 筆失敗,請前往審核 | 製作模組 |

### 純資訊通知（`requires_action = false`）

| 類型 | 觸發時機 | 說明 |
|------|---------|------|
| `order_cancelled` | 客戶取消訂單（pending_payment 階段）| 訂單已自動取消 |
| `quote_confirmed` | 客戶確認報價並進入付款流程 | 可準備製作 |
| `quote_rejected` | 客戶拒絕報價 | 申請已取消 |
| `ecpay_status` | ECpay Webhook 物流狀態更新 | 物流進度同步 |
| `order_completed_by_customer` | 客戶主動點確認收貨 | 訂單已由客戶確認完結 |

---

## 資料庫欄位

**管理員通知表（admin_notifications）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| type | 通知類型（見上方類型代號）|
| requires_action | 是否需要手動處理（boolean）|
| status | `unhandled` / `in_progress` / `completed` |
| reference_type | 關聯資源類型（`order` / `custom_request` / `physical_color`）|
| reference_id | 關聯資源 ID |
| message | 通知摘要文字 |
| created_at | 建立時間 |
| updated_at | 狀態更新時間 |

> 純資訊通知（`requires_action = false`）預設建立為 `unhandled`，管理員讀取後可一鍵標記 `completed`。
> 後續有新通知類型時，在此文件新增對應列即可。

> **stock_shortage 去重規則**：若該 physical_color 已存在 `status ∈ {unhandled, in_progress}` 的 stock_shortage 通知，**不產生新通知**，僅 UPDATE 該通知的 `updated_at = now()` 與 `message`（例如更新缺口量）。管理員處理完（標記為 completed）後，下次進貨仍不足才會產生新通知。
