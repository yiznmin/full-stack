# 物流狀態生命週期需求

> 業務需求：訂單從「付款」到「收貨完成」之間，整個物流狀態如何跟隨 ECpay 推送變化、admin 與客戶各自看到什麼、需要哪些 UI 與通知。
>
> 對應規格檔：[`docs/integration_specs/ecpay_status_tracking.md`](../integration_specs/ecpay_status_tracking.md)
> 範圍：**正向物流**（CVS C2C 超商寄件 + HOME 黑貓宅配 + HOME 中華郵政）

---

## 1. 完整生命週期（時間軸）

```
T0  客戶下單                      Order.status = pending_payment
                                  Shipment 不存在

T1  客戶付款                      Order.status = paid
T2  admin 確認付款                ProductionProgress 為每個 OrderItem 建 row（狀態 pending）
                                  寄付款確認 email 給客戶

T3  admin 點「印製模板」          ProductionProgress.status = manufacturing
                                  Order.status auto: paid → processing
                                  寄「開始製作」email

T4  admin 點「打包中」              ProductionProgress.status = packaging
T5  admin 點「備貨完成」            ProductionProgress.status = ready_to_ship

T6  admin「確認出貨資訊」鎖定      Order.shipping_locked = true

T7  admin 點「出貨」              ECpay 建單 → 拿 tracking_number / cvs_payment_no / cvs_validation_no / booking_note
                                  Shipment created (status=shipped)
                                  Order.status = shipped
                                  寄「已出貨」email + 託運單號 + 追蹤連結

T8  admin 拿包裹去 7-11 / 預約黑貓
                                  ECpay 收到「商品已送至物流中心」通知 (RtnCode 2030/3024/3003)
                                  → Webhook 推到我們 → 紀錄但不改 status
                                  → 客戶端顯示「商品已交付物流」

T9  包裹送達門市 / 配送中         ECpay 推「商品已送達門市」(2073/3018) 或「配送中」(3006)
                                  → Shipment.notes 更新；status 仍 shipped
                                  → 客戶端顯示「派送中」

T10 客戶取貨 / 簽收               ECpay 推「消費者成功取件」(2067/3022) 或「已送達」
                                  → Shipment.status = delivered
                                  → Shipment.delivered_at = UpdateStatusDate
                                  → Order 全部 shipments delivered → Order.status = completed
                                  → 寄「已送達」email
                                  → 客戶端顯示「已完成」

備援：Tn  超過 N 天 status 沒變化  → admin 點「重新查詢狀態」按鈕
                                  → 我們呼叫 /7418/ 拉最新狀態
                                  → 補同步遺漏的 webhook
```

---

## 2. 客戶端（store）UI 要求

### 2.1 訂單列表頁（OrderListPage）

訂單卡片顯示：
- 訂單狀態 STATUS_LABEL（已實作，含 10 個狀態）
- 訂單分類 STATUS_TAB（已實作 unpaid / shipping / done）

### 2.2 訂單詳情頁（OrderDetailPage）

新增需求（在「物流」區塊內）：

1. **託運單號顯示**（admin 已從 ECpay 拿到的）
   - CVS：顯示 `tracking_number`（CVSPaymentNo）+ 「拿這串到 7-11 ibon 機台輸入」（其實這段對客戶 c2c 沒意義，是 admin 自己用）
   - HOME：顯示 `tracking_number`（BookingNote）+ 「物流追蹤」連結

2. **物流追蹤連結**（HOME）
   - 黑貓 (TCAT)：`https://www.t-cat.com.tw/Inquire/Trace.aspx?BillID={booking_note}`
   - 中華郵政 (POST)：`https://trackings.post.gov.tw/?id={booking_note}`
   - 連結 target="_blank"

3. **狀態 stepper 進度**
   - 「商品已送達物流中心」→ stepper 卡在「已出貨」step（不換 step）
   - 「商品送達取件門市」/ 「派送中」→ 顯示 sub-step「派送中」
   - 「客戶取貨」/「已送達」→ stepper 推進「已完成」

4. **物流狀態歷史**（選擇性 Phase 2）
   - 顯示時間軸：「2026-05-07 14:30 商品已交付物流」「2026-05-08 10:00 派送中」「2026-05-09 16:00 已送達」
   - 資料來源：`ShipmentStatusLog`（待建表）

### 2.3 通知 / Email

- T7 已出貨 → 寄 email 含追蹤單號 + 連結（**已實作基本版**）
- T10 已送達 → 寄 email 通知（**待實作**）

---

## 3. Admin 端 UI 要求

### 3.1 訂單詳情頁（OrderDetailPage）

新增需求：

1. **物流狀態詳情區塊**
   - 託運單號（CVSPaymentNo / BookingNote）
   - CVSValidationNo（限 7-11 C2C，大字 mono + 複製鍵）
   - 最新狀態：`Shipment.last_rtn_msg`（如「客戶已取貨」）
   - 狀態更新時間：`Shipment.last_status_at`

2. **「重新查詢狀態」按鈕**（手動 pull）
   - 呼叫 `POST /api/v1/admin/orders/{id}/refresh-shipment-status`
   - 後端呼叫 ECpay /7418/ 拉最新狀態 → 寫 DB
   - 用途：webhook 掉包時補救

3. **「列印託運單」按鈕**（HOME 專用）
   - 對應 ECpay /7438/（**獨立 spec，待寫**）
   - dry_run 模式回 mock HTML

4. **「物流追蹤」外部連結**
   - HOME → 黑貓 / 郵政官網查詢頁

### 3.2 通知 / Email

- 客戶七天未取件（RtnCode 2074/3020）→ admin notification「請聯絡客戶」
- ECpay 連線失敗 / 異常狀態 → admin notification

---

## 4. 系統需求（背景作業）

### 4.1 Webhook receiver（必做）

```
POST /api/v1/logistics/status-callback
  - 公開、不需 auth
  - 驗 CheckMacValue
  - 依 RtnCode 對映 → 寫 Shipment.status / Order.status
  - 必回 "1|OK"
  - idempotent（用 (AllPayLogisticsID, RtnCode, UpdateStatusDate) 三元組防重）
```

### 4.2 主動查詢 endpoint（admin 用）

```
POST /api/v1/admin/orders/{order_id}/refresh-shipment-status
  - admin only
  - 對該 Shipment 呼 ECpay /7418/
  - 比對 LogisticsStatus + UpdateStatusDate
  - 比 last_status_at 新 → 更新
```

### 4.3 定時 cron（選擇性 Phase 2）

每 6 小時把 `Shipment.status='shipped' AND last_status_at < now - 6h` 的單拉一次 /7418/，補同步。

---

## 5. DB schema 變動

### 5.1 必要欄位

`Shipment` 加：
- `last_rtn_code` (Int, nullable)
- `last_rtn_msg` (String, nullable)  
- `last_status_at` (TIMESTAMP, nullable) — UpdateStatusDate

### 5.2 選擇性（更完整 audit）

新表 `ShipmentStatusLog`：
- id / shipment_id / rtn_code / rtn_msg / update_status_date / received_at
- 每收一個 webhook 寫一筆，永不修改

### 5.3 migration 策略

跟既有的 shipping_locked / cvs_payment_no 一樣，靠 `init_db.py` 的 `ALTER TABLE IF NOT EXISTS`。

---

## 6. 狀態轉換規則（business rules）

### 6.1 何時 Order.status = completed

兩條件擇一：
1. **客戶主動點「確認收貨」**（既有 `confirm_received` endpoint，已實作）
2. **所有 Shipment.status = delivered**（webhook 自動觸發，新增）

### 6.2 何時 Shipment.status = delivered

收到 ECpay webhook 且 `RtnCode in [2067, 3022]`（客戶取貨/已送達）。

### 6.3 七天未取件處理

收到 RtnCode in [2074, 3020] → admin notification「客戶 7 天未取件，包裹將退回」。
不自動改 status；等實際退回再處理。

### 6.4 webhook idempotency

相同 (AllPayLogisticsID, RtnCode, UpdateStatusDate) 重複收到 → 直接回 "1|OK" 不重複處理。

---

## 7. 對應的 EVENT_MATRIX 事件

```
E37 Shipment 已出貨 → email 通知客戶（既有，已實作）
E37b ECpay 物流狀態通知收到 → Shipment.status update + 必要時 Order.status update（新增）
E38 Shipment 已送達 → email 通知客戶（新增 webhook 觸發）
E40 訂單完成 → 觸發退貨期限計算等（既有，被 E38 觸發）
E41 客戶 7 天未取件 → admin notification（新增）
```

---

## 8. 短期 / 中期 / 長期路徑

### 短期（必做 — Day 3）
- /7420/ webhook receiver
- Shipment.last_rtn_code / last_rtn_msg / last_status_at 欄位
- 客戶端 OrderDetailPage 顯示託運單號 + 黑貓追蹤連結
- 「客戶已取貨 → Order.status=completed」自動推進

### 中期（補強）
- /7418/ admin「重新查詢狀態」按鈕
- ShipmentStatusLog audit table
- 七天未取件 notification

### 長期（量起來再做）
- 定時 cron 每 6 小時 pull
- 詳細時間軸 UI（客戶端時間線）

---

## 9. 待確認事項

1. **「客戶 7 天未取件」處理流程**：
   - 系統自動 admin notification？
   - 自動寄 email 提醒客戶？
   - 自動取消訂單退款？
   → 預設方案：先做 admin notification，其他人工處理

2. **Shipment 多筆訂單**（一張 Order 有 fulfilled + preorder 兩個 Shipment）：
   - 兩筆都 delivered 才算 Order completed？✓ 是
   - 各別追蹤連結（兩個追蹤碼分別顯示）？✓ 是

3. **退換貨**：屬於 logistics_return_lifecycle.md 範圍，不在這份。

---

## 10. 文件交叉索引

| 內容 | 路徑 |
|---|---|
| /7418/ + /7420/ 技術規格 | `docs/integration_specs/ecpay_status_tracking.md` |
| **本文件 — 業務需求** | `docs/requirements/logistics_status_lifecycle.md` |
| 退貨需求 | `docs/requirements/logistics_return_lifecycle.md`（待寫） |
| 整體推進計畫 | `docs/module_plans/20_logistics_ecpay.md` |

---

## 11. 變更紀錄

| 日期 | 內容 |
|---|---|
| 2026-05-07 | 初版 — 涵蓋從付款到完成的物流生命週期、客戶/admin UI 需求、webhook 邏輯 |
