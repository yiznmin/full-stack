# 管理者端：客戶訂單管理模組

---

## 5.1 訂單生命週期

**一般目錄商品**

```
客戶結帳 → 建立訂單（pending_payment）
    ↓
24 小時內完成銀行轉帳
    ↓ 逾期未付
payment_expired（自動取消，保留歷史記錄）
    ↓ 已付款
管理員確認付款 → paid → processing → shipped → completed

【狀態轉換規則】
- processing → shipped：訂單底下**至少一筆** shipments.status ∈ {shipped, delivered}
- shipped → completed：訂單底下**所有** shipments.status = delivered，或客戶主動點「確認收貨」
```

**客製服務（方案 D：先看初稿再付款）**

```
客戶提交申請表單 + 上傳照片 → 建立客製申請（quote_pending）
系統自動發歡迎訊息
    ↓
管理員與客戶透過訊息系統溝通（可選：negotiating，管理員在申請詳情頁手動點「標記洽談中」切換，不自動觸發）
    ↓
管理員於製作模組「從客製申請帶入照片」→ 跑 production_job
    ↓ 同一 transaction 內
**custom_requests.status: quote_pending → negotiating(自動)**
**對應 admin_notifications(type=quote_pending)自動標為 completed**
客戶從會員中心會看到狀態變為「洽談中」,此時申請內容鎖定(不可再改照片/偏好/備註)
    ↓
管理員完成後處理、顏色對應（approved=true）
    ↓
管理員計算報價（公式 × 2.0 倍，可手動覆寫）
管理員點「送出報價 + 初稿」→ quote_sent
系統寄 email 給客戶，含：
  - 初稿預覽圖（filled_template.png）
  - 報價金額明細
  - 確認連結（/custom/quote/:token）
    ↓
客戶於報價確認頁操作：
  ├── 確認報價 → quote_confirmed → 建立訂單（pending_payment）
  ├── 要求修改（revision_count<3 才顯示）→ draft_revision
  │    └→ 管理員調整 → 再次送出 → 回到 quote_sent
  └── 拒絕報價 → quote_rejected
        └── 客戶可重新申請（parent_request_id 關聯原申請）
    ↓ 報價逾期未回應
quote_expired（自動取消，保留記錄）
    ↓ 付款後
paid → processing → shipped → completed
```

【設計理由】
- 先做模板讓客戶看到成品預覽才付款，提升轉換率與客戶安心感
- 報價依實際 num_colors_used 精算，避免付款後發現色數超出估算
- 修改次數上限 3 次，避免無限制修改造成工時浪費
- 被拒絕或逾期的 production_job 保留，供未來分析參考

**取消 / 退款**

- 客戶在 `paid` 狀態前可自行取消
- `paid` 之後需聯繫管理員人工處理；管理員**不可直接將已付款訂單改為 cancelled**，必須走退款流程
- 退款透過人工對談處理，訂單標記 `refund_processing` → 全額退款 `refunded` / 部分退款 `partially_refunded`

---

## 5.2 訂單狀態一覽

> `quote_pending / negotiating / quote_sent / quote_confirmed / quote_rejected / quote_expired` 是 `custom_requests.status` 的狀態，存於 `custom_requests` 表，**不是** `orders.status`。客製申請在客戶確認報價後才建立 `orders` 記錄，進入 `pending_payment`。

**`orders.status` 狀態（目錄商品 + 客製服務共用）**

| 狀態 | 說明 |
|------|------|
| pending_payment | 等待付款（24 小時倒數）|
| payment_expired | 逾期未付，自動取消 |
| paid | 管理員已確認付款 |
| processing | 備貨中（客製服務含製作時間）；尚未有任何 shipment 出貨 |
| shipped | 已出貨；訂單底下至少一筆 shipments.status ∈ {shipped, delivered} |
| completed | 已完成；訂單底下所有 shipments.status = delivered，或客戶主動確認收貨 |
| cancelled | 已取消（付款前由客戶或管理員觸發）；見 cancel_reason_code |
| refund_processing | 退款處理中，管理員已受理但尚未實際退款 |
| refunded | 已退款（全額）|
| partially_refunded | 部分退款完成 |

**`custom_requests.status` 狀態（客製申請專用，見 5.9）**

| 狀態 | 說明 |
|------|------|
| quote_pending | 等待管理員計算報價 |
| negotiating | 洽談中 |
| quote_sent | 報價已寄出，等待客戶確認（含初稿預覽圖）|
| draft_revision | 客戶已要求修改，等待管理員重新調整 |
| quote_confirmed | 客戶確認報價，等待付款（此時建立 orders 記錄）|
| quote_rejected | 客戶拒絕報價 |
| quote_expired | 報價逾期未回應，自動取消 |

所有取消 / 逾期 / 拒絕記錄保留在資料庫，含原因說明，不實際刪除。

**自動化定時任務（Celery Beat）**

以下三個狀態變更由 Celery Beat 排程定時掃描執行，非人工觸發：

| 任務 | 掃描條件 | 執行頻率 | 動作 |
|------|---------|---------|------|
| 付款逾期 | `status = pending_payment` 且 `payment_deadline < now()` | 每 5 分鐘 | 狀態改為 `payment_expired`，寄通知 email |
| 報價逾期 | `custom_requests.status = quote_sent` 且 `quote_expires_at < now()` | 每 5 分鐘 | 狀態改為 `quote_expired`，寄通知 email |
| 出貨逾期提醒 | `orders.status = shipped` 且存在 `shipments.shipped_at < now() - 14 days` 且無 `shipments.status = delivered` | 每天一次 | 發 email 通知管理員確認物流狀況，不自動變更狀態 |

**狀態變更並發保護**

所有訂單狀態變更（客戶取消、系統自動逾期、管理員確認付款）必須使用資料庫交易 + `SELECT FOR UPDATE` 鎖定訂單列，並在鎖定後重新確認當前狀態符合前置條件才執行，否則拒絕並回傳錯誤。

```
例：客戶取消 與 系統自動 payment_expired 同時觸發
→ 先搶到鎖的操作成功執行
→ 後到的操作讀到狀態已變更，條件不符，自動拒絕
→ 前端顯示「訂單狀態已變更，請重新整理」
```

**付款期限絕對上限（防止長期佔用庫存）**

`orders.payment_deadline` 可因管理員 flag 付款有誤而延期，但有絕對上限：

- **初始值**：`orders.created_at + 24h`
- **每次 flag 重設時**：`payment_deadline = MIN(now() + 24h, orders.created_at + 48h)`
- **絕對期限**：48 小時後（`created_at + 48h`）強制進入 `payment_expired`，無論當下是否正在等客戶重填

> 48 小時存於 `system_settings.payment_absolute_deadline_hours`，預設 48，管理員可後台調整。
> 設計理由：避免異常訂單（例如客戶反覆填錯）長期佔用庫存，擋住其他客戶下單。48 小時足以應對「一次匯款錯 + 一次重填」的情境；極端情況下客戶可重新下單。

**緊急提醒機制**

當管理員 flag 付款有誤時，系統判斷該訂單剩餘時間（`payment_deadline - now()`）：
- **≥ 6 小時**：正常寄送「付款資訊有誤」email，標題例如「請重新填寫付款資訊 #PL-XXX」
- **< 6 小時**：email 標題改為「**緊急：還剩 X 小時重新填寫付款資訊 #PL-XXX**」，內文開頭加上紅字警示

這確保客戶在剩餘時間不多時會特別注意信件，降低逾期風險。

---

## 5.3 購物車與一般訂單內容

**購物車**

- 客戶可將多個商品變體加入購物車一起結帳
- 同一變體可加入多件（`quantity` 不限 1）
- 結帳時快照商品資訊（商品名稱、規格、單價），避免之後商品修改影響歷史訂單

**庫存拆單邏輯**

下單數量超過現有庫存時，系統自動拆分同一 order_item 為現貨 + 預購：

```
客戶下單 quantity = 3，現有庫存可供 = 1
→ fulfilled_qty = 1（現貨，正常出貨）
→ preorder_qty = 2（預購，等待庫存補齊後出貨）
```

結帳頁顯示拆單明細，讓客戶確認後再送出訂單。
預購部分庫存補齊時，系統自動通知客戶並進入出貨流程。

---

## 5.4 物流整合（ECpay）

使用 **ECpay（綠界科技）** 作為物流聚合器，統一處理三種取貨方式：

| 取貨方式 | ECpay 支援 |
|---------|-----------|
| 宅配到府 | 黑貓宅急便 |
| 7-11 店到店 | 統一超商 |
| 全家店到店 | 全家便利商店 |

**出貨流程**

1. 管理員在後台點「出貨」→ 確認收件資訊（已從下單時快照帶入）
2. 系統透過 ECpay API 建立物流訂單 → ECpay 回傳物流追蹤號碼
3. 系統自動記錄追蹤號碼至 `shipments.tracking_number`，寄出貨通知 email 給客戶
4. ECpay Webhook 監聽物流狀態變更

**Webhook URL 設定**：直接使用 Railway 部署後的公開 URL（如 `https://paintlearn-backend.up.railway.app/webhooks/ecpay`），填入 ECpay 後台。開發與正式環境共用同一套部署流程，不需本機穿透工具。

**Webhook 安全驗證**：後端驗證 ECpay 回傳的 `CheckMacValue`，防止偽造請求，驗證失敗回傳 400。

**已完成判定（三軌並行）**

| 方式 | 說明 | 優先序 |
|------|------|--------|
| ECpay Webhook | 收到「已取貨/已投遞」事件 → 將對應 `shipment.status` 改為 `delivered`；所有 shipments 均 `delivered` 後自動將 `order.status` 改為 `completed`。其他中間物流狀態（如「派送中」）只建立 `ecpay_status` 類型的 admin_notification，不改訂單狀態。 | 最高 |
| 客戶主動確認 | 點「確認收貨」按鈕 → 立即 completed | 次之 |
| 逾期提醒 | 出貨後 14 天無取貨確認 → 系統發 email 通知管理員確認物流，由管理員手動處理 | 備用 |

完成後觸發 email 通知客戶（內容：「您的訂單已完成，感謝購買」），並發放回饋券（若符合條件）。

---

## 5.5 運費

- 方案：固定費用 + 免運條件
- 宅配到府：NT$120
- 超商店到店（7-11 / 全家）：NT$70
- 同一訂單統一一種取貨方式，運費只收一次
- 任一邊 > 40cm 的商品建議宅配，結帳時若選超商會顯示警告提示（如 40×60、60×40、50×50 等）
- 選擇「分開出貨」時，現貨與預購各自建立一筆 ECpay 物流訂單，實際產生兩次物流費用，差額由店家自行吸收，不向客戶額外收費

**免運條件（任一符合即免運）**

| 條件 | 說明 |
|------|------|
| subtotal ≥ NT$800 | 商品小計（折扣前）滿 NT$800 |
| 總數量 ≥ 3 件 | order_items 總 quantity 達 3 件 |

> 免運判斷以折扣前小計為基準，使用折扣券不影響免運資格。

---

## 5.6 金額計算

```
小計（subtotal）  = Σ（單價 × quantity）
折扣（discount）  = 折扣券 或 auto_checkout 促銷折抵（取最優惠，擇一）
運費（shipping）  = 依取貨方式（符合免運條件則為 0）
總計（total）     = subtotal - discount + shipping
```

> 折扣券 `min_purchase` 以**折扣前小計**為基準，與免運條件一致。

---

## 5.7 管理員操作

| 操作 | 說明 |
|------|------|
| 訂單列表 | 分頁、篩選（狀態、日期區間、訂單類型）；關鍵字搜尋範圍：訂單編號、客戶名稱、客戶 email |
| 訂單詳情 | 客戶資訊、商品明細、金額明細、收件資料、目前狀態 |
| 確認付款 | 將狀態從 pending_payment 改為 paid，觸發付款確認 email |
| 更新狀態 | 手動推進訂單狀態（processing → shipped 等）|
| 出貨 | 確認收件資訊 → 系統呼叫 ECpay API 建立物流訂單（帶入 `shipping_profiles.email`，若為 null 則用 `users.email` 作為物流通知 email），追蹤號碼自動取得並寄出貨通知。若 ECpay API 失敗，前端顯示錯誤訊息，訂單狀態維持不變，管理員可重試。|
| 新增內部備註 | 管理員對訂單的內部說明（客戶不可見），任何狀態下均可修改 |
| 查看取消歷史 | 顯示所有逾期 / 取消訂單，含原因 |
| 標記付款資訊有誤 | 填寫原因（如：金額不符）→ 系統重設 `payment_deadline = MIN(now()+24h, created_at+48h)` → email 通知客戶重新填寫（剩餘 < 6h 時觸發「緊急」標題）→ 訂單維持 pending_payment |
| 查看付款核對表單 | 訂單詳情中顯示客戶所有提交記錄，以最新一筆為準（金額、時間、帳號末五碼）|
| 標記退款處理中 | 將訂單狀態改為 `refund_processing`，填寫退款原因（客戶退貨 / 管理員主動退款等）；此時尚未實際處理退款，不改動庫存與優惠券。**系統自動寄 email 通知客戶「您的退款申請已受理,我們將盡快為您處理」** |
| 標記已退款 | 確認退款完成後開啟「退款明細」介面：(1) 填入 `refund_amount`；(2) 勾選「此項退回」的 order_items（勾選的項目庫存會回補）；(3) 系統依勾選結果決定最終狀態——若**勾滿全部 items** → 自動轉為 `status = refunded`（走全額退款邏輯）；若**僅勾選部分** → `status = partially_refunded` |

### 退款副作用規則

依最終狀態觸發不同的庫存、優惠券、回饋券處理：

**全額退款（status = refunded）**

| 項目 | 處理 |
|------|------|
| 庫存 | **所有 order_items** 的 fulfilled_qty × required_ml 回補到 physical_colors.stock_ml |
| 優惠券（user_coupons） | `is_used = false`，清空 `used_at` 與 `used_in_order_id` |
| public_code（promo_codes） | `total_used -= 1`（原子遞減）|
| 回饋券撤銷（source_order_id） | 來源為此訂單的 user_coupons 中，未使用者 → `expires_at = now()` 立即作廢；已使用者不處理 |

**部分退款（status = partially_refunded）**

| 項目 | 處理 |
|------|------|
| 庫存 | **僅 is_returned = true** 的 order_items 回補庫存（勾選部分）|
| 優惠券（user_coupons） | **維持 is_used = true**（訂單仍有部分成立）|
| public_code（promo_codes） | **維持 total_used 不變** |
| 回饋券撤銷（source_order_id） | 依「剩餘有效金額」判斷：`remaining = order.total - refund_amount`；若 remaining 仍 ≥ 當時的 trigger_threshold → **不撤銷**；若 < trigger_threshold → 撤銷（同全額退款邏輯）|

**設計理由**
- 部分退款代表訂單仍有部分商品實際成立，客戶享受了部分交易，因此 coupon 的使用權不回補
- 庫存只回補「實際退回」的部分，由管理員勾選決定，避免按金額比例推算的誤差
- 回饋券撤銷機制依「有效剩餘金額」判斷，保留公平性——若退款後訂單金額已不足觸發回饋券門檻，則撤銷回饋

### 退款明細介面規格（管理員後台）

管理員點「標記已退款」→ 開啟介面：

```
訂單 #PL-20260418-000312 退款處理
──────────────────────────────────
退款金額：[     ] 元

退回明細（勾選要退回的項目，將回補對應庫存）：

☐ [商品名稱] 30×40 入門 標準 × 1   NT$434
☐ [商品名稱] 40×50 中級 細緻  × 2   NT$1156
☐ [商品名稱] 60×60 進階 高級  × 1   NT$860

原訂單總額：NT$2450
本次退款：  NT$___

[取消] [確認退款]
──────────────────────────────────
```

**送出後後端處理：**

1. 驗證 `refund_amount > 0` 且 `refund_amount ≤ order.total`
2. 計算勾選比例：
   - 若勾選**全部 items** → `orders.status = refunded`，走全額退款副作用
   - 若勾選**部分 items** → `orders.status = partially_refunded`，走部分退款副作用
3. 對勾選的 items 設 `is_returned = true`，並回補對應 stock_ml
4. 依狀態觸發對應的優惠券/回饋券處理（見退款副作用規則）
5. 更新 `orders.refund_amount` 與 `refunded_at = now()`
6. 寄 email 給客戶（退款完成通知，含退款金額與退回明細,**並附「確認已收到退款」連結**）

### 退款流程的雙重確認機制

管理員標記退款完成(E42)不代表客戶真的收到錢,需額外的客戶確認步驟:

**流程:**
1. 管理員實際完成銀行轉帳(系統外部動作)
2. 管理員於後台點「退款明細」→ 勾選 items + 填 refund_amount + 按確認
3. 系統執行所有副作用(狀態變更、庫存回補、優惠券回補、email 通知客戶)
4. email 內含「確認已收到退款」連結(導向訂單詳情頁)
5. 客戶於訂單詳情頁或 email 連結點「確認已收到退款」
6. 系統 UPDATE `orders.refund_confirmed_at = now()`
7. 訂單詳情頁狀態標示改為「退款已完成(客戶已確認收到)」

**設計理由:**
- 副作用(庫存、優惠券)在管理員按退款時**立即發生**,不等客戶確認;避免客戶不確認造成庫存長期佔用
- `refund_confirmed_at` 純紀錄性,不影響訂單狀態機
- 客戶若一直不確認,後端不處理,訂單詳情頁持續顯示「已退款,請確認」,無自動過期
- 此機制保障雙方:客戶不會被當作已收到退款的冤大頭、管理員有書面紀錄證明客戶確認

**訂單詳情頁顯示邏輯:**
- `orders.status ∈ {refunded, partially_refunded}` AND `refund_confirmed_at IS NULL` → 顯示「已退款,請確認收到」+ 確認按鈕
- `orders.status ∈ {refunded, partially_refunded}` AND `refund_confirmed_at IS NOT NULL` → 顯示「退款已完成,客戶已於 YYYY-MM-DD 確認收到」

---

## 5.8 Email 通知

**發信服務：Resend**（後端 Python SDK 呼叫，免費額度 3,000 封/月）

所有 email 均由系統在狀態變更時自動發出，不論觸發來源為 Celery 排程、客戶操作或管理員操作。

**與 admin_notifications 的分野**

Email 與 admin_notifications 是**兩套獨立通知系統**，對應不同角色與目的：

| 系統 | 對象 | 用途 |
|------|------|------|
| Email（Resend）| 以**客戶**為主，偶爾發給管理員（例如：shipment_overdue、批次失敗的客戶告知）| 系統向外傳遞需要閱讀的事件 |
| admin_notifications | 僅**管理員**（後台通知中心）| 管理員待辦清單，需手動處理或已讀確認 |

**不是一對一對應**：
- 有些事件只發 Email、不進 admin_notifications（例如：客戶註冊驗證信）
- 有些事件只進 admin_notifications、不發 Email（例如：quote_pending，客戶已在頁面上看到狀態）
- 有些事件兩者都做（例如：quote_confirmed 進 admin_notifications，同時也發 Email 給管理員）

以下表格為 Email 通知清單，並非 admin_notifications 清單（後者見 admin_notifications.md）。

| 觸發時機 | 觸發來源 | 收件人 | 內容 |
|---------|---------|-------|------|
| 訂單建立 | 客戶下單 | 客戶 | 訂單明細 + 付款帳號 + 24 小時付款期限 |
| 逾期未付（`payment_expired`）| Celery Beat 自動 | 客戶 | 訂單已取消說明 |
| 客戶主動取消 | 客戶操作 | — | **無**（客戶自行點取消,頁面即顯示結果,不重複發信）|
| 管理員取消訂單 | 管理員操作 | 客戶 | 取消原因（來自 `cancel_reason_note`）+ 聯絡客服說明與方式 |
| 管理員確認付款（`paid`）| 管理員操作 | 客戶 | 付款已確認,我們將盡快為您製作與出貨 |
| 管理員標記付款資訊有誤 | 管理員操作 | 客戶 | 說明哪裡有誤 + 請重新填寫付款核對表單（剩餘時間 < 6h 時標題改為「緊急:還剩 X 小時」）|
| 訂單出貨（ECpay 建單成功）| 系統自動 | 客戶 | 出貨通知 + 追蹤號碼 + 取貨方式說明 |
| 預購商品到貨備貨 | 系統自動（進貨觸發）| 等待中的客戶 | 「您預購的商品已備齊,即將出貨」|
| 送達 5 天未確認取貨 | Celery Beat | 客戶（僅寄一次）+ 管理員 | 客戶:「您的商品已送達 5 天,若已收到請點『確認收貨』完成訂單」;管理員:提醒確認物流 |
| **退款受理**（`refund_processing`）| 管理員標記 | 客戶 | 您的退款申請已受理,我們將盡快為您處理 |
| 退款完成（`refunded` / `partially_refunded`）| 管理員標記退款完成 | 客戶 | 退款金額 + 退回明細 + **「確認已收到退款」連結**(導向訂單詳情頁觸發 `refund_confirmed_at` 更新)|
| 管理員送出報價（客製）| 管理員操作 | 客戶 | 初稿預覽圖 + 規格摘要 + 報價金額 + 確認連結（`/custom/quote/:token`,Token 本身即為認證憑證,客戶不需登入即可查看;Token 過期後才需登入）|
| **客戶提交客製申請** | 客戶操作 | 客戶 | 您的客製申請已收到,預計 X 個工作天內回覆報價(X 從 `system_settings.quote_reply_days` 讀取)|
| 報價逾期未回應（`quote_expired`）| Celery Beat 自動 | 客戶 | 申請已自動取消說明 |
| 客戶確認報價 | 客戶操作 | 管理員（若不在後台）| 通知可進入備貨流程,含訂單連結 |
| 客戶要求修改初稿 | 客戶操作 | 管理員（若不在後台）| 客戶已要求修改初稿,請前往調整 |
| 客戶延長報價時間 | 客戶操作 | 管理員（若不在後台）| 客戶已延長報價考慮時間 + 1 天 |
| 客製申請收到新訊息 | 客戶操作 | 管理員（**完全不在後台時才寄**,見三層通知邏輯）| 訊息摘要 + 導回對話頁連結 |
| 客戶收到新訊息 | 管理員操作 | 客戶（若不在對話頁）| 訊息摘要 + 導回對話頁連結 |
| 付款核對表單（新提交/重新提交）| 客戶操作 | 管理員（**完全不在後台時才寄**）| 付款核對表單待處理,含訂單連結 |
| 製作批次完成 | Celery 自動 | 管理員（完全不在後台時才寄）| 批次 #XXX 已完成,N 成功/M 失敗,請前往審核 |

---

## 5.9 客製申請管理介面

管理員後台獨立頁面，管理所有 `custom_requests`。

**列表頁**
- 顯示所有申請，依建立時間倒序排列
- 可依狀態篩選（quote_pending / negotiating / quote_sent / quote_confirmed / quote_rejected / quote_expired）
- 每筆顯示：申請類型、客戶名稱、提交時間、目前狀態

**詳情頁**
- 申請規格：類型、畫布尺寸、難易度、細緻度、備注
- 客戶上傳照片（custom_photo 類型）
- 訊息對話區（與客戶來回溝通）
- 報價操作：帶入基礎定價建議 → 勾選加費項目 → 確認或手動覆蓋 → 送出報價
- 從 `admin_notifications` 通知點入時直接跳至此頁

---

## 5.10 資料庫欄位

**購物車（cart_items）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| user_id | FK → users.id（需登入才能使用）|
| product_variant_id | FK → product_variants.id |
| quantity | 數量 |
| created_at | 加入購物車時間 |

> 購物車只存一般目錄商品。客製申請（custom_photo / custom_spec）走 custom_requests 流程，不進購物車。
> 購物車不儲存價格快照，結帳時以當下 `product_variants.price` 為準。若管理員在客戶加入後調整售價，購物車頁面即時顯示新價格。
> 結帳時後端驗證每個購物車項目的 `is_active` 狀態，若有已下架變體則拒絕結帳，前端提示「部分商品已下架，請移除後再結帳」，並在購物車頁面將該項目標記為灰色。

**訂單表（orders）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| order_number | 訂單編號（格式：PL-YYYYMMDD-XXXXXX，流水號由全域 PostgreSQL SEQUENCE 原子產生，永遠遞增不重置。日期為建立當天，流水號不跨日歸零，例如當日第一筆可能為 PL-20260418-000312）|
| user_id | FK → users.id |
| status | 見 5.2 |
| subtotal | 商品總價 |
| discount_amount | 折扣總額（來源為折扣券或 auto_checkout，擇優） |
| discount_source | coupon / auto_checkout（記錄實際套用的折扣來源）|
| shipping_fee | 運費 |
| total | 實付金額（subtotal - discount_amount + shipping_fee）|
| user_coupon_id | FK → user_coupons.id（nullable）|
| shipping_type | home / seven_eleven / family_mart |
| shipping_preference | together / separate（含預購項目時的出貨偏好）|
| shipping_snapshot | 收件資料快照 JSON（含收件人、地址/門市）|
| payment_deadline | 付款期限。初始值為 `created_at + 24h`；管理員 flag 時重設為 `MIN(now()+24h, created_at + payment_absolute_deadline_hours)`（預設上限 48h）|
| paid_at | 付款確認時間 |
| completed_at | 完成時間 |
| cancel_reason_code | 取消原因分類：`payment_expired`（逾期自動取消）/ `customer_cancelled`（客戶於付款前取消）/ `admin_cancelled`（管理員取消）；僅 status=cancelled 時有值 |
| cancel_reason_note | 取消原因自由說明文字（管理員取消時建議填寫）；逾期或客戶取消時通常為 null |
| refund_amount | 退款金額（nullable，退款時填入，支援部分退款）|
| refunded_at | 退款完成時間（nullable）|
| refund_confirmed_at | 客戶確認已收到退款的時間（nullable;僅紀錄用,不影響狀態機)|
| customer_notes | 客戶備注 |
| admin_notes | 管理者備註 |
| created_at | 下單時間 |
| updated_at | 最後更新時間 |

> `tracking_number` 與 `shipped_at` 移至 `shipments` 表，一筆訂單可對應多筆出貨記錄。

**出貨記錄表（shipments）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| order_id | FK → orders.id |
| shipment_type | `fulfilled`（現貨出貨）/ `preorder`（預購出貨）|
| status | `pending` / `shipped` / `delivered`（見下方說明）|
| tracking_number | ECpay 物流追蹤號 |
| ecpay_logistics_id | ECpay 物流訂單 ID |
| shipped_at | 出貨時間（ECpay API 成功回傳追蹤號時自動填入）|
| delivered_at | 取貨 / 投遞確認時間（ECpay Webhook 填入，nullable）|
| created_at | 建立時間 |

**shipments.status 說明**

| 值 | 說明 |
|---|---|
| `pending` | 已建立出貨記錄，尚未填入追蹤號 |
| `shipped` | 已填入追蹤號，物流進行中 |
| `delivered` | 已送達 / 已取貨（ECpay Webhook 回報或客戶主動確認）|

> 一般合併出貨只有一筆 `shipments` 記錄；選「分開出貨」時現貨與預購各建一筆。
> 客戶與管理員均可查看所有出貨記錄與各自的追蹤號碼。

**order.status 與 shipments.status 的聚合規則（動作導向）**

`order.status` 不由單一 shipment 事件觸發，而由訂單底下**所有 shipments 的聚合狀態**決定：

| 聚合條件 | order.status |
|---|---|
| 尚未建立任何 shipment，或全部 pending | paid / processing（不由 shipments 決定） |
| 至少一筆 status ∈ {shipped, delivered} 且未全部 delivered | shipped |
| 所有筆 status = delivered | completed |

**合併出貨（1 筆 shipment）**
- 管理員點出貨 → ECpay API 成功 → shipments[0].status = shipped → order.status 改為 shipped
- ECpay Webhook 回報 delivered → shipments[0].status = delivered → order.status 改為 completed

**分開出貨（2 筆 shipment，現貨先出、預購後出）**
- 第一次出貨：shipments[0]=shipped → order.status 改為 shipped
- 第二次出貨：shipments[1]=shipped → order.status 維持 shipped
- 任一筆 delivered：order.status 維持 shipped（尚未全部 delivered）
- 兩筆皆 delivered：order.status 改為 completed

**客戶主動點「確認收貨」**
- 僅 order.status=shipped 後顯示
- 點擊後：所有尚未 delivered 的 shipments.status 設為 delivered，order.status 改為 completed，completed_at=now()

訂單詳情頁內各 shipment 各自顯示狀態與追蹤號碼，客戶可清楚掌握每筆出貨進度。

**訂單明細表（order_items）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| order_id | FK → orders.id |
| product_variant_id | FK → product_variants.id（nullable，客製訂單為 null）|
| custom_request_id | FK → custom_requests.id（nullable，一般目錄商品為 null）|
| production_job_id | 對應的製作任務 id（nullable，僅客製訂單有值）。**寫入時機**：客戶於報價確認頁點「確認」→ 建立 order → 建立 order_items 時，系統從 `custom_request.id` 反查該申請關聯的 approved production_job，將 id 直接寫入本欄位。採「建立時一次寫入」，不做事後觸發反查。|
| product_title_snapshot | 下單時商品名稱快照 |
| variant_spec_snapshot | 下單時規格快照 JSON |
| unit_price | 下單時單價快照 |
| quantity | 購買總數量 |
| fulfilled_qty | 現貨數量（下單時庫存足夠的部分）|
| preorder_qty | 預購數量（庫存不足需等待的部分）|

> 客製訂單（`custom_request_id` 非 null）：`fulfilled_qty = 0`、`preorder_qty = 1`，全部算預購。製作進度以 `production_progress` 狀態為準，不更新這兩個欄位。

**客製申請表（custom_requests）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| user_id | FK → users.id |
| request_type | `custom_photo`（客戶自帶照片）/ `custom_spec`（目錄圖自訂規格）|
| photo_url | 客戶上傳照片（custom_photo 用，Firebase Storage）。**僅 status = quote_pending 時**客戶可在申請詳情頁點「更換照片」重新上傳，系統覆蓋此欄位並刪除 Firebase 上的舊照片;其他狀態拒絕更換(回 409)。|
| ref_product_id | 參考商品（custom_spec 用，nullable）|
| canvas_w_cm | 指定畫布寬度（custom_photo 選填，nullable）|
| canvas_h_cm | 指定畫布高度（custom_photo 選填，nullable）|
| difficulty | 指定難易度（必填；選「讓管理員建議」時存 null，但前端必須要求客戶明確選擇此選項，不可空白送出）|
| detail | 指定細緻度（必填；選「讓管理員建議」時存 null，但前端必須要求客戶明確選擇此選項，不可空白送出）|
| customer_notes | 客戶備注 |
| quoted_price | 管理員填入的報價金額 |
| quote_token | 報價確認信的安全 token（hashed，用於 `/custom/quote/:token` 連結驗證，與 `quote_expires_at` 同步到期）|
| quote_expires_at | 報價有效期限（送出後 +1 天，延長後再 +1 天）|
| is_extended | 客戶是否已使用延長一次（boolean）|
| status | quote_pending / negotiating / quote_sent / quote_confirmed / quote_rejected / quote_expired |
| parent_request_id | FK → custom_requests.id（重新申請時指向原始申請，nullable）|
| order_id | 客戶確認後建立的訂單（FK → orders.id，nullable）|
| admin_notes | 管理員內部備注 |
| created_at | 申請時間 |
| quoted_at | 報價時間 |

> 照片保留政策：申請被拒絕或逾期後照片不自動刪除，保留供日後查閱。更換照片時舊照片立即從 Firebase 刪除。

**客製申請狀態說明**

| 狀態 | 說明 |
|------|------|
| quote_pending | 等待管理員報價 |
| negotiating | 洽談中（管理員與客戶來回溝通細節）|
| quote_sent | 報價已送出，等待客戶確認 |
| quote_confirmed | 客戶確認報價，等待付款 |
| quote_rejected | 客戶拒絕報價 |
| quote_expired | 報價逾期未回應 |

> 一位客戶可同時提交多筆客製申請，無數量限制，管理員依序處理。

**重新申請邏輯**

客戶拒絕報價後可重新申請：
- 系統建立新的 custom_request，帶入原始申請的規格資料
- 新申請的 `parent_request_id` 指向原申請（id）
- 原申請保留存檔，狀態維持 `quote_rejected`
- 管理員後台顯示「此為重新申請，原申請 #X 已拒絕」，可查看歷史

**訊息系統（custom_request_messages）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| request_id | FK → custom_requests.id |
| sender_type | admin / customer |
| message | 訊息內容 |
| created_at | 發送時間 |

- 申請建立時系統自動發送歡迎訊息（第一則，sender_type = admin）
- 管理員在後台訊息區回覆；客戶在「客製申請」頁回覆
- 管理員發送報價時，報價金額 + 備注訊息同步進入訊息系統
- 訊息僅支援純文字，不支援圖片附件；客戶需換圖請使用「更換照片」功能

**即時推送機制（SSE）**

**管理員端:** 管理員登入後台的**任何頁面**時,瀏覽器建立 SSE 連線,伺服器記錄該管理員在後台活躍中。登出或關閉所有後台分頁 → SSE 斷線 → 視為「不在後台」。

**客戶端:** 客戶開啟客製申請對話頁時建立 SSE 連線,離開該頁面即斷線(僅「對話頁」算活躍)。

**三層通知邏輯(客戶 → 管理員的訊息):**

| 管理員狀態 | 通知方式 |
|-----------|---------|
| 正開著該申請的對話頁 | SSE 即時推播訊息到頁面,不產生 admin_notification,不寄 email |
| 在後台但不在該申請的對話頁 | 產生 admin_notification(type=new_message)+ SSE 推播角標更新,**不寄 email** |
| 完全不在後台(無任何活躍 SSE 連線)| 產生 admin_notification + 寄 email 通知管理員 Gmail |

**客戶端的兩層邏輯(管理員 → 客戶):**

| 客戶狀態 | 通知方式 |
|---------|---------|
| 在該申請的對話頁 | SSE 即時推播,不寄 email |
| 不在對話頁(含完全離線)| 寄 email 通知客戶 |

> **判斷「活躍 SSE 連線」的實作**:伺服器維護連線表,key 為 user_id + context(對客戶只看對話頁、對管理員看整個後台),連線建立時寫入,斷線時移除。查詢時直接查表。

用戶離開頁面 → SSE 連線自動斷開 → 後端偵測離線。
用戶傳訊息給後端仍使用一般 HTTP POST;SSE 只負責伺服器→前端的推送。

**Railway SSE 保活機制（Heartbeat）**

Railway 負載平衡器會在連線閒置超過 60 秒時強制斷線。後端需每 30 秒推送一次 SSE 注解行保持連線：

```
: heartbeat\n\n
```

前端 `EventSource` 會自動忽略注解行，但 Railway 偵測到資料流動而不斷線。
前端需監聽 `onerror` 事件，斷線後自動重連（`EventSource` 瀏覽器原生支援）。

**付款核對表（payment_submissions）**

客戶付款後主動填寫轉帳資訊，方便管理員比對：

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| order_id | FK → orders.id |
| is_flagged | 管理員標記有誤（boolean，預設 false）|
| transfer_amount | 轉帳金額 |
| transfer_date | 轉帳日期 |
| transfer_time | 轉帳時間 |
| account_last5 | 轉帳帳號末五碼 |
| notes | 備注 |
| created_at | 填寫時間 |

客戶可多次填寫（如填錯可重填），管理員後台在訂單詳情中可查看所有提交記錄，以最新一筆為準，對照銀行帳款記錄。管理員標記有誤時，該筆記錄的 `is_flagged` 設為 true，同時系統重設 `orders.payment_deadline = now() + 24h`，並通知客戶重新提交。24 小時內未提交新的核對表單，Celery Beat 自動將訂單狀態改為 `payment_expired`。

**生產進度表（production_progress）**

每個訂單項目獨立追蹤生產狀態，狀態更新自動觸發 email 通知客戶。

**建立時機**：訂單狀態變為 `paid` 時，系統自動為每筆 `order_item` 建立一筆 `production_progress`，初始狀態為 `pending`。後續狀態由管理員手動推進。

**操作介面**：管理員在**訂單詳情頁**內，每筆 order_item 旁顯示目前生產狀態與「標記下一步」按鈕，直接操作不需跳頁。

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| order_item_id | FK → order_items.id |
| status | 見下方狀態說明 |
| notes | 備注（管理員填寫，客戶可見）|
| updated_at | 狀態更新時間 |
| created_at | 建立時間 |

**生產進度狀態**

| 狀態 | 說明 | 自動發 email |
|------|------|------------|
| pending | 等待開始（付款確認後建立）| 否 |
| in_production | 製作中（客製訂單專用：跑 production_job；一般目錄商品跳過此狀態）| 是 |
| manufacturing | 印製模板 + 備妥顏料套組 | 是 |
| packaging | 打包中 | 否 |
| ready_to_ship | 備貨完成，等待出貨 | 是 |
| shipped | 已出貨（管理員點「出貨」→ ECpay API 成功取得追蹤號後，系統自動將該訂單所有 production_progress 推進至此狀態，不需手動操作）| 是（含追蹤號碼）|
