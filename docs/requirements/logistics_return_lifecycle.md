# 物流退貨生命週期需求

> 業務需求：客戶申請退貨後，實體商品如何從客戶手中送回賣家、與既有「退款金錢流」如何銜接、admin 與客戶各自看到什麼。
>
> 對應規格檔：[`docs/integration_specs/ecpay_return.md`](../integration_specs/ecpay_return.md)
> 範圍：**逆物流（reverse logistics）— 限 HOME 黑貓宅配**（中華郵政與超商 C2C 不支援 ECpay 逆物流 API）

---

## 1. 概念區分：退款 vs 逆物流

```
退款（既有，已實作）：
  錢從賣家退給客戶
  Order.status: paid/processing/shipped/completed → refund_processing → refunded
  搭配既有 cancel_order / process_refund 等 endpoint

逆物流（本文件範圍，未實作）：
  實體商品從客戶送回賣家倉庫
  ECpay /7416/ 排黑貓收件、/7422/ 推狀態
  完成後賣家確認收到包裹才能放心退錢
```

兩者**通常一起發生**但 API 是獨立的。

---

## 2. 完整生命週期

```
T0  客戶下單 → 付款 → 出貨 → 送達 → 客戶取得商品

T1  客戶申請退貨（既有 cancel_order endpoint，status='cancelled'）
    或 發現商品瑕疵 → admin 主動標 refund_processing

T2  admin 審核同意退貨退款
    → Order.status = 'refund_processing'（已實作）

T3  【新增】admin 點「建立逆物流訂單」按鈕
    → 後端呼叫 ECpay /7416/
    → 若帶 AllPayLogisticsID（原訂單）→ ECpay 自動反向填地址
    → 收件人欄位填賣家寄件人地址（admin sender info）
    → 寄件人欄位填客戶收件地址
    → ECpay 回 1|OK
    → 我們建 ReturnShipment row（status='pending'）

T4  ECpay 通知黑貓司機到客戶家收件
    → ECpay 推 /7422/ webhook「已收件」(RtnCode=300 系列)
    → ReturnShipment.status='in_transit'
    → admin notification「客戶端取件成功」

T5  黑貓送回賣家倉庫
    → ECpay 推 /7422/「已送達寄件人」(RtnCode=5003 或類似)
    → ReturnShipment.status='delivered'
    → admin notification「請確認收到退貨包裹」

T6  admin 物理上確認包裹完整無缺
    → 點「確認收到退貨」按鈕
    → 進入既有的退款金額流程（既有 process_refund endpoint）
    → Order.status='refunded' / 'partially_refunded'
    → 退錢給客戶
```

---

## 3. 替代方案（短期推薦）

如果還沒做 /7416/ 整合，**短期可以這樣**：

```
T1-T2 同上

T3 admin 自己預約黑貓收件（黑貓官網 / 致電）
    → 不走 ECpay /7416/
    → 寫進 admin_notes：「2026-05-07 已預約黑貓收件，預定 5/9 取件」

T4-T5 admin 手動追蹤（不靠 webhook）

T6 admin 收到包裹 → 既有退款流程
```

**這個方式不用工程，admin 多花點時間。** 量起來（每月 >5 筆退貨）再做 ECpay 整合。

---

## 4. 客戶端（store）UI 要求

### 4.1 退貨申請流程（既有 cancel-order，已實作）

無新需求。

### 4.2 退貨進行中顯示（未實作）

訂單詳情頁 status='refund_processing' 時：
- 顯示「退貨進行中」橫條
- 若有 ReturnShipment：顯示託運單號 + 黑貓追蹤連結
- 顯示客戶要做什麼：「物流人員會到你的地址取件」/「包裹已送回賣家，正在處理退款」

---

## 5. Admin 端 UI 要求

### 5.1 訂單詳情頁

新增區塊 `ReturnShipment`（status='refund_processing' 或更後階段才顯示）：

- **「建立逆物流訂單」按鈕**（status='refund_processing' + 沒有 ReturnShipment 時顯示）
  - 點擊 → confirm dialog 顯示要從哪到哪寄
  - 預填：sender = 原 ReceiverAddress（客戶家）；receiver = system_settings 的賣家地址
  - 確認後呼叫 `POST /api/v1/admin/orders/{id}/return-shipment`

- **ReturnShipment 詳情**（已建立時）
  - 託運單號（BookingNote）+ 黑貓追蹤連結
  - 最新狀態：last_rtn_msg
  - 「重新查詢狀態」按鈕（webhook 掉包用）

- **「確認收到退貨」按鈕**（ReturnShipment.status='delivered' 時）
  - admin 物理檢查包裹後點擊
  - 觸發既有退款金額處理流程

### 5.2 通知

- 客戶端取件成功 → admin notification
- 包裹送達賣家 → admin notification「請確認收到退貨包裹」（紅色警示）
- 取件失敗 / 客戶拒絕 → admin notification

---

## 6. DB schema

### 6.1 新表 `return_shipments`

```python
class ReturnShipment(Base):
    __tablename__ = "return_shipments"

    id = UUID primary_key
    order_id = FK to orders
    original_shipment_id = FK to shipments (nullable, 對應正向 Shipment)

    ecpay_logistics_id = String  # ECpay 給的逆物流交易編號
    rtn_merchant_trade_no = String(20)  # 我們建單時的逆物流 MerchantTradeNo
    booking_note = String(50)  # 託運單號（從 /7422/ 拿）

    status = Enum('pending', 'in_transit', 'delivered', 'failed')
    last_rtn_code = Int (nullable)
    last_rtn_msg = String (nullable)
    last_status_at = TIMESTAMP (nullable)

    sender_snapshot = JSONB  # 客戶地址 snapshot
    receiver_snapshot = JSONB  # 賣家地址 snapshot

    created_at = TIMESTAMP
    updated_at = TIMESTAMP
    received_at = TIMESTAMP (nullable)  # admin 確認收到時間
```

### 6.2 既有表變動

`Order` 加：
- `return_shipment_id` 不需要（一對多透過 FK 反查即可）

---

## 7. 業務規則

### 7.1 何時可建逆物流

- Order.status == 'refund_processing'
- 該訂單尚未有 ReturnShipment OR 既有 ReturnShipment.status='failed'（重建）
- LogisticsType == 'HOME' 且 LogisticsSubType == 'TCAT'（黑貓）
  - **CVS 超商不支援逆物流 API**：客戶要退超商商品，要自己拿到原寄件門市
  - **POST 中華郵政不支援**

### 7.2 退款金額流程

ReturnShipment.status='delivered' → admin 點「確認收到退貨」→ 才能執行既有 process_refund。

不能跳過：必須收到實體包裹才退錢。

### 7.3 失敗處理

- ReturnShipment.status='failed'：客戶不在家、拒絕、地址錯等
- admin 收 notification → 聯絡客戶 → 重建逆物流 OR 客戶自寄

---

## 8. EVENT_MATRIX 對應

```
E50 admin 建逆物流 → ReturnShipment created（新增）
E51 ECpay 推「客戶端取件」→ ReturnShipment.in_transit + notification（新增）
E52 ECpay 推「送達賣家」→ ReturnShipment.delivered + 紅色 notification（新增）
E53 admin 確認收到退貨 → received_at + 觸發既有 refund 流程（新增）
```

---

## 9. 優先度評估

| 階段 | 工作量 | 何時做 |
|---|---|---|
| 短期：admin 手動叫黑貓 + 既有退款流程 | 0 工程 | **現在** |
| 中期：/7416/ 建單 + /7422/ webhook | 1 天 | 量起來後（>5 筆/月） |
| 長期：自助退貨流程（客戶填表→自動建逆物流）| 2 天 | 量大後 |

---

## 10. 待確認事項

1. **退貨運費誰出？**
   - 賣家負擔（推薦）：客戶體驗好、退貨意願高
   - 客戶負擔：減少濫退但有抗拒
   - **預設方案**：賣家負擔（這也是 ECpay /7416/ 預設）

2. **超商退貨怎麼辦？**
   - ECpay 沒提供超商逆物流 API
   - 解法 A：admin 通知客戶自寄（傳統做法）
   - 解法 B：admin 派貨運上門收（黑貓收，但這是「黑貓不是超商」）
   - **預設方案**：解法 A（客戶自寄到指定地址）

3. **退貨期限？**
   - 多少天內可退（ROCA 7 天？國際慣例 14 天？）
   - **預設方案**：上線時寫進「退款政策」頁，目前先設 7 天（消保法 ROCA）

---

## 11. 文件交叉索引

| 內容 | 路徑 |
|---|---|
| /7416/ /7422/ 技術規格 | `docs/integration_specs/ecpay_return.md` |
| **本文件 — 退貨業務需求** | `docs/requirements/logistics_return_lifecycle.md` |
| 正向物流業務需求 | `docs/requirements/logistics_status_lifecycle.md` |
| 整體計畫 | `docs/module_plans/20_logistics_ecpay.md` |

---

## 12. 變更紀錄

| 日期 | 內容 |
|---|---|
| 2026-05-07 | 初版 — 涵蓋退貨全流程、短期人工方案、中期 ECpay 整合需求、優先度評估 |
