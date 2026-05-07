# Module 20 - ECpay 物流整合（logistics）

> 把 Module 09 訂單系統裡的 **ECpay stub** 換成真實 API 整合，並新增超商選店、狀態通知 webhook、託運單列印。
> 本模組分 4 階段（Day 1–4）漸進推進，每段獨立可上線測試。
> 來源文件：[ECpay Developers](https://developers.ecpay.com.tw/) — 各 API 詳見 §3 endpoint 對照表。

---

## 0. 整體推進節奏（4 階段）

| 階段 | 範圍 | 對應 ECpay API | 狀態 |
|---|---|---|---|
| **Day 1** | 超商選店（電子地圖） | [/8795/](https://developers.ecpay.com.tw/8795/) | ✅ **完成 + 用戶端驗收通過**（2026-05-07，C2C UNIMARTC2C/FAMIC2C）|
| **Day 2** | 物流訂單建立（CVS + 宅配） | [/8809/](https://developers.ecpay.com.tw/8809/) + [/7414/](https://developers.ecpay.com.tw/7414/) | ✅ Backend + Admin UI 完成（dry_run 模式驗收通過） |
| **Day 3** | 物流狀態追蹤（webhook + query） | [/7420/](https://developers.ecpay.com.tw/7420/) + [/7418/](https://developers.ecpay.com.tw/7418/) | ⏳ Pending — 已寫 spec / 需求 |
| **Day 4** | 託運單列印（HOME） + production 切換 | [/7438/]() | ⏳ Pending |
| **Day 5（後）** | 逆物流（退貨） | [/7416/](https://developers.ecpay.com.tw/7416/) + [/7422/](https://developers.ecpay.com.tw/7422/) | 🟢 短期人工處理；長期再做 |

**規則：** 每階段完成後必須 commit + push + user 實測通才往下；不自動連跑。

### 帳號類型確認（2026-05-07）

User 帳號 `3497730` 經 `probe-subtypes` API 實測確認為 **C2C**：
- ✅ UNIMARTC2C / FAMIC2C / HILIFEC2C / OKMARTC2C
- ❌ UNIMART / FAMI / UNIMARTFREEZE / HILIFE

**對 Day 2 的影響（重要）：**
- C2C **不用測標** → Day 2 建單可以直接動工，不卡 3-7 天等待
- C2C 按單收費，不用月結合約
- Picker 預設 SubType = `UNIMARTC2C` / `FAMIC2C`

---

## 1. 帳號與環境

### 帳號類型分辨
- **物流** 跟 **電子發票** 是兩個獨立 ECpay 帳號，各有自己的 MerchantID / HashKey / HashIV
- 本模組只用「物流」那組

### 環境差異
| 項目 | Stage（沙箱） | Production（正式） |
|---|---|---|
| Endpoint | `logistics-stage.ecpay.com.tw` | `logistics.ecpay.com.tw` |
| 簽章 | MD5 | MD5 |
| 行為 | **電子地圖固定門市**，不會跳出實際地圖 | 真實地圖選店 |
| 資料保留 | 不留正式記錄 | 真實託運單號、可能收費 |

### Env vars（Railway backend service Variables）
```
ECPAY_MERCHANT_ID=2000132            # sandbox 公開測試組（可放）
ECPAY_HASH_KEY=5294y06JbISpM5x9      # sandbox 公開
ECPAY_HASH_IV=v77hoKGq4kWxNNIS       # sandbox 公開
ECPAY_ENV=stage                       # stage / production
ECPAY_SERVER_REPLY_URL=               # 留空 → service 自動由 request.base_url 推導
```

正式上線：把 4 個換成 user 正式帳號的（HashKey/HashIV 不寫進這份文件、不傳輸）。

### CheckMacValue 規則（物流 = MD5）
1. 參數依 key 字典序升冪排序
2. 串成 `HashKey=xxx&Key1=Val1&...&HashIV=yyy`
3. URL encode（.NET style：保留 `-_.!*()` 不編碼）
4. 全部轉小寫
5. **MD5** （非金流的 SHA256）
6. 轉大寫

⚠️ 金流 API 用 SHA256，**物流 API 用 MD5**，不要混。

---

## 2. 檔案清單

### 既有（Day 1 已完成）
```
backend/
├── core/config.py             # +ECPAY_* env vars (4 個)
├── logistics/
│   ├── __init__.py
│   ├── service.py             # CheckMacValue (MD5) + map URL builder + verify
│   └── router.py              # /cvs-map (auto-submit form) + /cvs-callback (postMessage)
└── main.py                    # 註冊 logistics_router

store/src/features/profile/components/
├── ConvenienceStorePicker.vue   # popup + window.message 接收
└── ShippingProfileForm.vue      # 7-11/全家自動換 picker
```

### Day 2 要建（物流訂單建立）
```
backend/logistics/
├── service.py                 # +create_cvs_shipment() / create_home_shipment()
└── router.py                  # +POST /admin/orders/{id}/create-shipment

修改既有：
├── orders/service.py          # 移除既有 ECpay stub，改呼叫 logistics.service
└── orders/router.py           # POST /admin/orders/{id}/shipments 改用真實實作

admin/src/features/orders/
└── pages/OrderDetailPage.vue  # 加「建立物流訂單」按鈕（付款確認後出現）
```

### Day 3 要建（狀態通知）
```
backend/logistics/
├── service.py                 # +parse_status_callback() + map_status_to_shipment_enum()
├── router.py                  # +POST /logistics/status-callback (公開、ECpay 來打)
└── tests/test_logistics.py    # webhook 單元測試（驗章、狀態映射）
```

### Day 4 要建（列印 + edge cases）
```
backend/logistics/
├── service.py                 # +get_print_info() + get_print_token()
└── router.py                  # +POST /admin/orders/{id}/print-shipping-label

admin/src/features/orders/
└── pages/OrderDetailPage.vue  # +「列印託運單 / 重印」按鈕
```

---

## 3. DB 模型（已存在，本模組不改 schema）

`Shipment` 表（[orders/models.py:165](backend/orders/models.py#L165) 已存在）：
- `tracking_number` VARCHAR — ECpay 回的 ShipmentNo
- `ecpay_logistics_id` VARCHAR — ECpay 回的 AllPayLogisticsID
- `shipment_type` ENUM('fulfilled','preorder')
- `status` ENUM('pending','shipped','delivered')
- `shipped_at` / `delivered_at` TIMESTAMP

**Day 1–4 全部沿用既有欄位**，不需 alembic migration。

---

## 4. Endpoints 與業務流程

### Day 1 ✅ — 電子地圖（CVS Map）
參考 [/8795/](https://developers.ecpay.com.tw/8795/)

#### `GET /api/v1/logistics/cvs-map?type=UNIMARTC2C`
- 依 `type` 產生 ECpay map page 所需參數（含 CheckMacValue）
- 回 auto-submit form HTML，瀏覽器一打開就 POST 到 ECpay
- 用戶選店完，ECpay POST 回 ServerReplyURL

#### `POST /api/v1/logistics/cvs-callback`
- 接 ECpay form POST，欄位：`MerchantID, MerchantTradeNo, LogisticsSubType, CVSStoreID, CVSStoreName, CVSAddress, CVSTelephone, CVSOutSide, ExtraData, CheckMacValue`
- 驗 CheckMacValue → 用 `window.opener.postMessage({...})` 把資料傳給 opener → close

⚠️ 注意：規格沒列 RtnCode/RtnMsg，**callback 不要解這兩個欄位**。

---

### Day 2 ⏳ — 物流訂單建立

#### CVS 建單（C2C）— [/7414/](https://developers.ecpay.com.tw/7414/)
**Endpoint：** `POST /Express/Create`

主要參數：
- `MerchantTradeNo`（廠商交易編號，唯一）
- `MerchantTradeDate`
- `LogisticsType=CVS`
- `LogisticsSubType=UNIMARTC2C / FAMIC2C / ...`
- `GoodsAmount`（總金額）
- `GoodsName`
- `SenderName / SenderCellPhone / SenderZipCode / SenderAddress`（寄件人）
- `ReceiverName / ReceiverCellPhone / ReceiverEmail`（收件人）
- `ReceiverStoreID`（從 Day 1 Map 拿到的門市代碼）
- `ServerReplyURL`（ECpay 推狀態的 URL — 對應 Day 3）
- `ClientReplyURL`（client 跳轉用）
- `LogisticsC2CReplyURL`（C2C 寄件碼通知）

回傳：`MerchantTradeNo, RtnCode, RtnMsg, AllPayLogisticsID, BookingNote, CVSPaymentNo, CVSValidationNo`

#### 宅配建單 — [/2870/]
**Endpoint：** `POST /Express/Create`

主要差異：
- `LogisticsType=HOME`
- `LogisticsSubType=TCAT / ECAN`（黑貓 / 宅配通）
- `ReceiverZipCode / ReceiverAddress` 取代門市代碼
- `Temperature=0001 (常溫)/0002(冷藏)/0003(冷凍)`
- `Specification=0001 (60cm)/0002(90cm)/0003(120cm)/0004(150cm)`

#### 我們的 endpoint：`POST /api/v1/admin/orders/{order_id}/create-shipment`
**業務流程：**
1. 驗 admin auth
2. Load order + shipping_snapshot
3. 依 shipping_snapshot.type 決定 LogisticsType (CVS/HOME) 與 SubType
4. Build params + CheckMacValue
5. POST 到 ECpay Express/Create
6. Parse response：成功 → 寫 Shipment(tracking_number, ecpay_logistics_id, status='shipped', shipped_at=now())
7. 失敗 → 不寫 DB、回 502 給 admin

---

### Day 3 ⏳ — 物流狀態通知（webhook）
參考 [/10127/](https://developers.ecpay.com.tw/10127/)

#### `POST /api/v1/logistics/status-callback`（公開）
ECpay 在以下時點主動 POST：
- 包裹送達物流中心
- 派送中
- 已送達 / 客戶取貨
- 退貨

**參數：** `MerchantID, MerchantTradeNo, RtnCode, RtnMsg, AllPayLogisticsID, GoodsAmount, UpdateStatusDate, ReceiverName, ..., CheckMacValue`

**狀態映射：**
| ECpay RtnCode | 含意 | 我們 shipment.status |
|---|---|---|
| 300 | 訂單建立成功 | shipped |
| 2030 | 已送達物流中心 | shipped |
| 2068 | 派送中 | shipped |
| 2067 / 3022 | 已取貨 / 已投遞 | delivered |
| 3019 | 退貨完成 | （另起 admin notification） |

**業務流程：**
1. 驗 CheckMacValue（驗失敗回 200 `0\|ERROR`，不洩漏資訊）
2. 依 AllPayLogisticsID 找 Shipment
3. 更新 status / delivered_at
4. **聚合判斷**：該訂單所有 shipments = delivered → `order.status = completed`（觸發 E40）
5. 回 `200 "1|OK"`（ECpay 強制要求格式）

---

### Day 4 ⏳ — 列印託運單

#### `POST /Helper/PrintTradeDocument` — [/7438/]
ECpay 回一個 HTML 表單，用瀏覽器打開可以列印託運單。

#### 我們的 endpoint：`POST /api/v1/admin/orders/{order_id}/print-shipping-label`
回包含 ECpay print form 的 HTML，admin 點擊新分頁開啟可列印。

---

## 5. EVENT_MATRIX 對照

對照 [docs/EVENT_MATRIX.md](../EVENT_MATRIX.md) 既有事件：

| Event | 觸發點 | 副作用 | 本模組變化 |
|---|---|---|---|
| E36 建立 shipment | admin 點按鈕 | INSERT shipment, 更新 order.status, 寄通知 email | **stub → 真實 ECpay create** |
| E37 標 shipped | shipment 建立成功時 | UPDATE shipment.shipped_at, 寄出貨通知 email | 由 ECpay 回應觸發 |
| E38 標 delivered | webhook 收到 | UPDATE shipment.delivered_at | **新增 webhook 觸發** |
| E40 訂單完成 | 所有 shipments delivered | UPDATE order.status=completed, 寄完成通知 | webhook 聚合判斷觸發 |

**新增事件（本模組）：**
- E36b ECpay 建單失敗 → CREATE admin_notification(type='ecpay_create_failed')，不寫 shipment
- E38b ECpay 退貨通知 → CREATE admin_notification(type='ecpay_returned')

---

## 6. 測試覆蓋範圍

### Day 1（CVS Map）
- ✅ CheckMacValue MD5 算法（happy path + 已知 ECpay 範例驗算）
- ✅ URL encode 保留 `-_.!*()`
- 🔲 callback 驗章成功 → postMessage payload 正確
- 🔲 callback 驗章失敗 → ok=false
- 🔲 sub_type 不支援 → 400

### Day 2（建單）
- 🔲 CVS C2C 建單成功（mock ECpay 回 RtnCode=300）
- 🔲 宅配建單成功
- 🔲 ECpay 連線失敗 → 不寫 DB、回 502
- 🔲 重複建單防呆（同 order 已有 shipment.tracking_number）→ 409

### Day 3（webhook）
- 🔲 簽章驗證失敗 → 200 "0|ERROR"
- 🔲 RtnCode=2067 → shipment.status=delivered
- 🔲 全部 shipments delivered → order.status=completed
- 🔲 找不到對應 AllPayLogisticsID → 200 "0|ERROR"

### Day 4（列印）
- 🔲 列印 endpoint 回 HTML form 含正確 CheckMacValue

---

## 7. 短期權宜（Day 1 上線到 Day 2 完成之間）

只用 Day 1 拿到的門市代碼，admin 自己每天看訂單後台 → 拿包裹去 7-11 用「店到店」貼自家標籤寄出 → 客戶取貨後手動把訂單狀態改成「已完成」。

可以**先開賣不卡 Day 2**，但每筆訂單要人工處理。

---

## 8. 待確認事項

1. ~~預計每天訂單量~~ ✅ **要做批次建單**（user 2026-05-07 確認）
2. ~~宅配走 ECpay 還是自己叫黑貓~~ ✅ **走 ECpay**（user 2026-05-07 確認）
3. ~~C2C vs B2C~~ ✅ **已確認 C2C**（2026-05-07 經 probe-subtypes 實測）
4. **重印託運單的場景？** 客戶要求重新列印貼紙還是只是 admin 內部備份？影響 Day 4 是否需要做版本控管。
5. ~~Day 2 宅配 SubType 開通狀態~~ ✅ **已確認**（2026-05-07 probe-subtypes 擴充版實測）
   - HOME 開通：TCAT (黑貓) / POST (中華郵政) / ECAN (宅配通；ECpay 已停用此服務)
   - CVS C2C 開通：UNIMARTC2C / FAMIC2C / HILIFEC2C / OKMARTC2C
   - CVS B2C 全未開

---

## 9. 已知 TODO（正式上線前清理）

- 🧹 **刪 `/api/v1/logistics/debug-config` endpoint**（router.py 內）— diagnostic 工具，正式環境會洩漏 HashKey 頭尾字元
- 🧹 **刪 `/api/v1/logistics/probe-subtypes` endpoint** — 同上，是過渡期診斷工具
- 🧹 **生產環境替換 `paint-web-production.up.railway.app` → 正式 yiimui 網域**（如果你之後綁自家網域）

---

## 10. 文件交叉索引（完整地圖）

### 規格檔（technical specs）
| 內容 | 路徑 |
|---|---|
| Day 1 CVS Map (/8795/) | `docs/integration_specs/ecpay_cvs_map.md` |
| Day 2 建單 (/8809/ + /7414/) | `docs/integration_specs/ecpay_create_shipment.md` |
| Day 3 狀態追蹤 (/7418/ + /7420/) | `docs/integration_specs/ecpay_status_tracking.md` |
| Day 5 逆物流 (/7416/ + /7422/) | `docs/integration_specs/ecpay_return.md` |

### 業務需求（business requirements）
| 內容 | 路徑 |
|---|---|
| 物流生命週期（付款→送達→完成） | `docs/requirements/logistics_status_lifecycle.md` |
| 退貨流程（退貨 + 退款銜接） | `docs/requirements/logistics_return_lifecycle.md` |

### 其他
| 內容 | 路徑 |
|---|---|
| 整體推進計畫（這份） | `docs/module_plans/20_logistics_ecpay.md` |
| 過程踩坑紀錄 | `docs/issues_log.md` |
