# ECpay 逆物流規格（退貨流程）

> 涵蓋兩個 API：
> - **`/7416/` 產生逆物流訂單Ⅱ** — 客戶退貨時建立反向物流，黑貓上門收
> - **`/7422/` 逆物流狀態通知 (Webhook)** — 退貨流程中 ECpay 推送狀態變化
>
> ⚠️ **僅 TCAT (黑貓) 支援**。中華郵政（POST）不提供逆物流。
> ⚠️ **CVS 超商不在這份範圍**：超商退貨走另一套（用戶自己拿到原寄件門市）。

---

## 1. 業務情境

```
客戶申請退貨 → admin 審核同意
   ↓
admin 點「建立退貨物流」→ ECpay /7416/
   ↓
ECpay 通知黑貓司機到收件人地址（客戶家）取件
   ↓
司機到貨送回賣家（我們 yiimui 倉庫）
   ↓ ECpay 推 /7422/ 狀態變化
我們收到「已送達寄件人」（=賣家）
   ↓
admin 確認收到包裹 → 進入退款流程（既有的 refund flow）
```

**注意**：
- 「逆物流訂單建立」 ≠「退款」。退款是錢的事，逆物流是「實體商品送回」
- 兩者通常同時發生，但 API 是獨立的
- 我們既有的 refund_processing 流程處理錢的退；/7416/ 只處理物流

---

## 2. `/7416/` 逆物流訂單建立

### 2.1 Endpoint
- Stage: `https://logistics-stage.ecpay.com.tw/Express/ReturnHome`
- Production: `https://logistics.ecpay.com.tw/Express/ReturnHome`

### 2.2 HTTP
POST · `application/x-www-form-urlencoded` · `Accept: text/html`

### 2.3 Request 參數

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `MerchantID` | String(10) | ✓ | 特店編號 |
| `AllPayLogisticsID` | String(20) | 條件 | 原本正向物流訂單的 ID（帶這個會反向自動填收件人＝原寄件人） |
| `LogisticsSubType` | String(20) | 條件 | `TCAT`（黑貓）— 只能填這個 |
| `ServerReplyURL` | String(200) | ✓ | 逆物流狀態通知 URL（指向 /7422/ 接收 endpoint） |
| `SenderName` | String(10) | 條件 | 退貨人姓名（4-10 字）— 客戶 |
| `SenderPhone` | String(20) | 條件 | 退貨人電話 |
| `SenderCellPhone` | String(20) | 條件 | 退貨人手機（09 開頭 10 碼） |
| `SenderZipCode` | String(6) | 條件 | 退貨人郵遞區號 |
| `SenderAddress` | String(60) | 條件 | 退貨人地址（>6 字）— 客戶家 |
| `ReceiverName` | String(10) | 條件 | 收件人姓名（4-10 字）— **賣家自己** |
| `ReceiverPhone` | String(20) | 條件 | — |
| `ReceiverCellPhone` | String(20) | 條件 | — |
| `ReceiverZipCode` | String(6) | 條件 | — |
| `ReceiverAddress` | String(60) | 條件 | 收件人地址（>6 字）— 賣家倉庫 |
| `ReceiverEmail` | String(50) | — | — |
| `GoodsAmount` | Int | ✓ | 商品金額 1-20000 元 |
| `GoodsName` | String(60) | — | 商品名稱 |
| `Temperature` | String(4) | — | `0001`/`0002`/`0003` 同正向 |
| `Distance` | String(2) | — | `00`/`01`/`02` |
| `Specification` | String(4) | — | `0001`-`0004`，冷藏/凍禁 150cm |
| `ScheduledPickupTime` | String(1) | — | 固定 `4` |
| `ScheduledDeliveryTime` | String(2) | — | `1`-`4` |
| `Remark` | String(200) | — | 備註 |
| `PlatformID` | String(10) | — | 平台商代號 |
| `CheckMacValue` | String | ✓ | 簽章 |

### 2.4 Response
**純字串**（無欄位名稱）：
- 成功：`1|OK`
- 失敗：其他內容（如 `0|錯誤訊息`）

⚠️ 跟正向建單 `/7414/` 不一樣 — 正向回 `1|MerchantID=xxx&...`（含完整資料）；逆物流只回 `1|OK`。**所以建立後我們拿不到 BookingNote**，要靠後續 webhook 通知或 `/7418/` 查。

### 2.5 注意事項

- **若帶 `AllPayLogisticsID`**：寄件人/收件人欄位**會反向自動填**（原正向訂單的 receiver 變這次的 sender，反之亦然）。我們可以省事，只填 `AllPayLogisticsID + LogisticsSubType + ServerReplyURL + GoodsAmount + CheckMacValue`。
- **姓名禁 emoji 與特殊符號**，4-10 字
- **冷藏/冷凍禁 150cm**
- 建立後沒有立刻拿到託運單號，要等 `/7422/` webhook 推

---

## 3. `/7422/` 逆物流狀態通知

### 3.1 Endpoint
**我們提供的 URL**（建單時的 ServerReplyURL）：
- `https://paint-web-production.up.railway.app/api/v1/logistics/return-status-callback`

### 3.2 HTTP
POST · `application/x-www-form-urlencoded` · 全程 HTTPS

### 3.3 Request 參數（ECpay 推送）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `MerchantID` | String(10) | 特店編號 |
| `RtnMerchantTradeNo` | String(20) | **逆物流交易編號**（注意：不是正向的 MerchantTradeNo） |
| `RtnCode` | Int | 物流狀態碼（例 100 = 取件成功） |
| `RtnMsg` | String(200) | 狀態說明 |
| `AllPayLogisticsID` | String(20) | ECpay 物流交易編號（與正向訂單的 ID 不同） |
| `GoodsAmount` | Int | 商品金額 |
| `UpdateStatusDate` | String(20) | yyyy/MM/dd HH:mm:ss |
| `BookingNote` | String(50) | 託運單號（HOME 才有） |
| `CheckMacValue` | String | 必驗 |

### 3.4 我們必回的格式
跟正向 webhook 一樣：純字串 `1|OK`，沒回會重發 3 次延 3 天。

### 3.5 邏輯映射

| RtnCode | 含意 | 我們處理 |
|---|---|---|
| 300 系列 | 取件成功 / 配送中 | 紀錄到 ReturnShipment.notes |
| **5003** 或類似 | **送達賣家** | ReturnShipment.status='delivered'，通知 admin 「請確認收到退貨包裹」 |
| 4xxx | 取件失敗 / 拒收 | admin notification |

具體狀態碼依 ECpay 物流狀態表，文件未在 `/7422/` 內列。

---

## 4. 我們的實作（規劃）

### 4.1 DB

需要新表 `ReturnShipment`：
```python
class ReturnShipment(Base):
    __tablename__ = "return_shipments"

    id = UUID primary_key
    order_id = FK to orders
    original_shipment_id = FK to shipments  # 對應正向 Shipment
    ecpay_logistics_id = String  # ECpay 給的逆物流交易編號（非正向的）
    rtn_merchant_trade_no = String  # 我們送的逆物流訂單編號
    booking_note = String  # 託運單號（從 /7422/ 拿）
    status = Enum('pending', 'in_transit', 'delivered', 'failed')
    last_rtn_code = Int
    last_rtn_msg = String
    last_status_at = TIMESTAMP
    created_at, updated_at
```

### 4.2 Endpoint

```
POST /api/v1/admin/orders/{order_id}/return-shipment
  body: { reason }
  - 驗證訂單已有 shipment + status in (refund_processing 或既有退貨流程)
  - 呼叫 /7416/ 用 AllPayLogisticsID 反向自動填地址
  - 寫 ReturnShipment row（status='pending'）

POST /api/v1/logistics/return-status-callback
  - 公開、驗 CheckMacValue
  - 找 ReturnShipment by AllPayLogisticsID
  - 寫狀態 → 通知 admin
```

### 4.3 與既有 refund 流程整合

```
[1] 客戶申請退貨退款（既有 store 端 cancel-order 流程）
[2] admin 標記 'refund_processing'（已實作）
[3] 新增：admin 點「建立逆物流」按鈕
    → /7416/ ECpay 排黑貓收件
    → ReturnShipment created
[4] 黑貓收件、配送、送回（ECpay /7422/ 推狀態）
[5] admin 收到「已送達」通知 → 確認包裹完整
[6] admin 點「完成退款」→ Order.status='refunded'，退錢給客戶（既有流程）
```

### 4.4 簡化方案（短期）

**逆物流 API 整合工程量大（建表 + endpoint + UI + webhook + 測試）。**

短期建議：
- ❌ 不做 ECpay 逆物流 API
- ✅ admin 自己叫黑貓收件（傳統做法）
- ✅ 既有 refund 流程就足夠處理金錢
- 等量起來（每月 >5 筆退貨）再做 ECpay 逆物流自動化

---

## 5. CheckMacValue 規則
跟其他 ECpay API 同一支（MD5 大寫），用既有 `service.calculate_check_mac_value()`。

---

## 6. 文件交叉索引

| 內容 | 路徑 |
|---|---|
| /8809/ /7414/ 建單 | `docs/integration_specs/ecpay_create_shipment.md` |
| /7418/ /7420/ 狀態追蹤 | `docs/integration_specs/ecpay_status_tracking.md` |
| **本文件 — /7416/ /7422/ 退貨** | `docs/integration_specs/ecpay_return.md` |

---

## 7. 變更紀錄

| 日期 | 內容 |
|---|---|
| 2026-05-07 | 初版 — 整理逆物流規格 + 業務流程 + 短期建議（先不做、admin 手動叫黑貓） |
