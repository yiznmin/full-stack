# ECpay 物流狀態追蹤規格（查詢 + Webhook）

> 涵蓋兩個 API：
> - **`/7418/` 查詢物流訂單** — 主動查單目前狀態（admin 刷新按鈕／webhook 掉包補救）
> - **`/7420/` 物流狀態通知 (Webhook)** — ECpay 主動推送狀態變化到我們
>
> **Day 3 主軸**：把 `/7420/` 接好，正常情況不用 `/7418/`；偶發掉包再用 `/7418/` 救援。

---

## 1. 兩 API 的關係

```
正常路徑（推送）：
  ECpay 物流系統狀態變化（如客戶取貨）
     ↓ HTTPS POST
  我們的 ServerReplyURL：/api/v1/logistics/status-callback
     ↓ 驗章 + 寫 DB
  Shipment.status = 'delivered'  Order.status = 'completed'
     ↓
  必須回 "1|OK" 給 ECpay（不回會重發 3 次）

備援路徑（pull）：
  admin 「重新查詢狀態」按鈕
     ↓ HTTPS POST
  ECpay /Helper/QueryLogisticsTradeInfo/V5
     ↓
  ECpay 回該訂單最新狀態
     ↓
  我們依 LogisticsStatus 比對 webhook 是否漏掉，補同步
```

---

## 2. `/7420/` 物流狀態通知 Webhook 規格

### 2.1 Endpoint
**我們提供的 URL（ServerReplyURL）**：
- Production: `https://paint-web-production.up.railway.app/api/v1/logistics/status-callback`
- 跨環境統一由 build_create_shipment_form() 的 `server_reply_url` 參數注入

### 2.2 HTTP
- POST · `application/x-www-form-urlencoded` · 全程 HTTPS

### 2.3 ECpay 推送的欄位

| 欄位 | 型別 | 說明 |
|---|---|---|
| `MerchantID` | String(10) | 我們的特店編號 |
| `MerchantTradeNo` | String(20) | 我們建單時送的 order_number |
| `RtnCode` | Int | 物流狀態代碼（見 §2.5） |
| `RtnMsg` | String(200) | 狀態說明 |
| `AllPayLogisticsID` | String(20) | ECpay 物流交易編號（與 Shipment.ecpay_logistics_id 比對） |
| `LogisticsType` | String(20) | CVS / HOME |
| `LogisticsSubType` | String(20) | UNIMARTC2C / FAMIC2C / TCAT / POST 等 |
| `GoodsAmount` | Int | 商品金額 |
| `UpdateStatusDate` | String(20) | yyyy/MM/dd HH:mm:ss |
| `ReceiverName` | String(60) | 收件人姓名 |
| `ReceiverPhone` | String(20) | 收件人電話 |
| `ReceiverCellPhone` | String(20) | 收件人手機 |
| `ReceiverEmail` | String(50) | email |
| `ReceiverAddress` | String(200) | 地址 |
| `CVSPaymentNo` | String(15) | 寄貨編號（CVS） |
| `CVSValidationNo` | String(10) | 驗證碼（7-Eleven C2C） |
| `BookingNote` | String(50) | 託運單號（HOME） |
| `CheckMacValue` | String | **必驗** |

### 2.4 我們必回的格式

**成功**：
```
1|OK
```
純字串、**不可含 HTML 標籤、空格、換行、其他符號**。

**失敗**：未回或回非 `1|OK` 的內容 → ECpay 排程重發：
- 失敗 3 次後延到隔天
- 從狀態更新日起維持**3 天**重發
- 3 天後放棄

### 2.5 物流狀態代碼（RtnCode）— 我們需要對映的核心狀態

| 客戶看到的步驟 | 7-Eleven B2C | 7-Eleven C2C | 全家 / 萊爾富 / OK | HOME 黑貓 |
|---|---|---|---|---|
| 商品已送至物流中心 | 2030 | 2030 | 3024 | 3003 |
| 商品已送達門市 / 配送中 | 2063 | 2073 | 3018 | 3006 |
| **消費者成功取件 / 已送達** | **2067** | **2067** | **3022** | **3003** |
| 七天未取件 / 退回 | 2074 | 2074 | 3020 | — |
| 重新配達 | 2098 | 2098 | — | — |

我們系統需要的最低映射：
- `RtnCode in [2067, 3022]` → `Shipment.status = 'delivered'` + `delivered_at = UpdateStatusDate`
- 任何狀態 → 紀錄到 `Shipment.notes` 或新增 `ShipmentStatusLog` 表（看實作擇一）
- 全部 `Shipment.status = 'delivered'` → `Order.status = 'completed'`

### 2.6 安全考量

- **必須驗 CheckMacValue**（webhook 公開可被任何人 POST）
- 驗章失敗 → 仍回 `1|OK`（不暴露失敗訊息）+ log 警告
- 比對 `AllPayLogisticsID` 對應 Shipment 是否存在 → 不存在不報錯，只 log
- **idempotency**：同一個狀態通知可能重發，我們要防重複處理
  - 用 `(AllPayLogisticsID, RtnCode, UpdateStatusDate)` 三元組做 dedup key
  - 已收過 → 直接回 `1|OK`，不重複寫 DB

### 2.7 開發測試限制

⚠️ **測試環境（stage）無模擬通知功能**，必須在 production 測試。
- 對 dry_run 模式無意義（沒實際物流訂單）
- 切 production 後才能驗 webhook

---

## 3. `/7418/` 查詢物流訂單規格

### 3.1 Endpoint
- Stage: `https://logistics-stage.ecpay.com.tw/Helper/QueryLogisticsTradeInfo/V5`
- Production: `https://logistics.ecpay.com.tw/Helper/QueryLogisticsTradeInfo/V5`

### 3.2 HTTP
POST · `application/x-www-form-urlencoded`

### 3.3 Request

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `MerchantID` | String(10) | ✓ | 特店編號 |
| `AllPayLogisticsID` | String(20) | 擇一 | ECpay 物流交易編號 |
| `MerchantTradeNo` | String(20) | 擇一 | 廠商交易編號 |
| `TimeStamp` | Int | ✓ | Unix 時間戳，**3 分鐘內**有效 |
| `PlatformID` | String(10) | — | 平台商代號，一般留空 |
| `CheckMacValue` | String | ✓ | 簽章 |

### 3.4 Response

| 欄位 | 型別 | 說明 |
|---|---|---|
| `AllPayLogisticsID` | String(20) | ECpay 物流交易編號 |
| `MerchantTradeNo` | String(20) | 廠商交易編號 |
| `LogisticsStatus` | String(8) | **目前狀態（最重要）** |
| `LogisticsType` | String(20) | CVS / HOME |
| `BookingNote` | String(50) | 託運單號（HOME） |
| `CVSPaymentNo` | String(15) | 寄貨編號（CVS） |
| `CVSValidationNo` | String(10) | 驗證碼（7-11 C2C） |
| `ShipmentNo` | String(25) | 配送編號（CVS B2C） |
| `GoodsAmount` | Int | 商品金額 |
| `GoodsName` | String(200) | 商品名稱 |
| `GoodsWeight` | Number | 商品重量（POST，最多小數 3 位，kg） |
| `ActualWeight` | Number | 實際重量（POST） |
| `HandlingCharge` | Int | 物流費用 |
| `CollectionAmount` | Int | 代收金額 |
| `CollectionChargeFee` | Int | 代收手續費 |
| `CollectionAllocateAmount` | Int | 代收撥款金額 |
| `CollectionAllocateDate` | String(10) | 代收撥款日期（yyyy/MM/dd） |
| `ShipChargeDate` | String(10) | 物流運費扣款日期 |
| `TradeDate` | String(20) | 訂單成立時間 |
| `SenderName` | String(10) | 寄件人姓名 |
| `SenderPhone` | String(20) | 寄件人電話（可能空） |
| `SenderCellPhone` | String(10) | 寄件人手機 |
| `CheckMacValue` | String | 必驗 |

### 3.5 用途

1. **admin「刷新狀態」按鈕**：webhook 沒收到時手動拉
2. **每天定時 cron** 把 `Shipment.status='shipped'` 的單拉一次（以防 webhook 掉包）
3. **財務對帳**：拿 HandlingCharge / CollectionAllocateAmount

### 3.6 注意事項

- TimeStamp 嚴格 3 分鐘內，server clock skew 要注意
- 7-11 代收特殊：CollectionAllocateAmount = 0 + 代收金額不為 0 → 尚未撥款（不是「無代收」）

---

## 4. CheckMacValue 規則

跟 [/7424/](https://developers.ecpay.com.tw/7424/) 同一支演算法（MD5 大寫），與 Day 1 / Day 2 共用 `service.calculate_check_mac_value()`。

---

## 5. 我們的實作對應

### 5.1 Webhook endpoint
```
POST /api/v1/logistics/status-callback
```
- 公開（require_auth=False）
- 驗章 → 找 Shipment by AllPayLogisticsID → 依 RtnCode 映射狀態 → 回 "1|OK"

### 5.2 Query endpoint（admin only）
```
POST /api/v1/admin/orders/{order_id}/refresh-shipment-status
```
- admin 點按鈕 → 我們呼 ECpay /Helper/QueryLogisticsTradeInfo/V5 → 比對 → 補同步

### 5.3 DB 變動

無新 table，但需要：
- `Shipment.last_rtn_code` (Int, nullable) — 最後收到的狀態碼
- `Shipment.last_rtn_msg` (String, nullable) — 最後狀態訊息
- `Shipment.last_status_at` (TIMESTAMP, nullable) — UpdateStatusDate
- 或：另開 `ShipmentStatusLog` 表記每筆通知（更完整 audit）

⚠️ alembic 不通用，要靠 `init_db.py` `ALTER TABLE IF NOT EXISTS`。

### 5.4 安全與 idempotency
- 用 `Shipment.last_status_at` < `UpdateStatusDate` 才寫，否則 skip（防重發）
- 簽章驗失敗 → log + 回 "1|OK"（避免 ECpay 重發）

---

## 6. 文件交叉索引

| 內容 | 路徑 |
|---|---|
| /8795/ CVS Map | `docs/integration_specs/ecpay_cvs_map.md` |
| /8809/ /7414/ 建單 | `docs/integration_specs/ecpay_create_shipment.md` |
| **本文件 — /7418/ /7420/ 狀態追蹤** | `docs/integration_specs/ecpay_status_tracking.md` |
| /7416/ /7422/ 逆物流 | `docs/integration_specs/ecpay_return.md`（待寫） |

---

## 7. 變更紀錄

| 日期 | 內容 |
|---|---|
| 2026-05-07 | 初版 — 涵蓋 /7418/ + /7420/，含狀態碼對映表、idempotency、安全考量 |
