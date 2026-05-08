# Module 21 - Store 客製化前端 + Backend SSE 補完

> Backend custom 模組 (`Module 10`) 已完成，admin custom_requests UI 也完成；本模組做 **store 端 4 個客製化頁面 + 商品詳情頁 custom_spec 入口 + backend SSE webhook 補實作**。
>
> 對應規格：
> - [`docs/requirements/store/store_custom.md`](../requirements/store/store_custom.md)
> - [`docs/module_plans/10_custom.md`](10_custom.md) §4.1-4.2 endpoint
> - [`docs/api.md`](../api.md) L1014-1126 客製申請 / 報價 endpoints
> - [`docs/yii_mui_static_pages_spec.md`](../yii_mui_static_pages_spec.md) §第二頁 客製化流程視覺

---

## 0. 已拍板決定（2026-05-08，含 v1.1 修正）

| Q | 決定 | 來源 |
|---|---|---|
| Q1 上傳機制 | Firebase signed URL（同既有商品圖模式） | 用戶確認 |
| Q2 未登入流程 | **B**：未登入可填文字資料到 sessionStorage，**照片要登入後再選** | 用戶確認 |
| Q3 參考價 | **B**：依尺寸+難度顯示價格區間（從 `custom_photo_prices` 表） | 用戶確認 |
| Q5 商品詳情頁 custom_spec 入口 | **第一版不做**（2026-05-08 修正）：custom_spec 整套 backend / DB / admin 完整保留不動，store 前端第一版**不做** `?type=custom_spec` query 切換邏輯，CustomPage 表單僅 custom_photo 一條路。商品頁 `/custom` CTA 保持原樣（連到 custom_photo 主流程）。v2 評估時可不破壞地重啟。 | 用戶確認 |
| Q6 訊息附圖 | 第一版**不做**，純文字訊息 | 建議採用 |
| Q7 訊息更新 | **SSE**（順便補 backend，不留 polling tech debt） | 用戶確認 |
| Q11 案例「諮詢類似規格」 | **要做**：點案例 → CaseDetailDialog → 帶尺寸/難度預填客製表單 | 用戶確認 |
| Q12 quote_pending 自由修改 | **要全部補完**（2026-05-08 加）：依 store_orders.md L100-122，quote_pending 狀態客戶可修改 photo / 偏好 / 備註；negotiating 後鎖定 409。Backend 需補 `PATCH /custom-requests/{id}` partial update endpoint。 | 用戶確認 |
| Q13 過期重申請 CTA | **要做**：`quote_expired` 狀態下顯示「重新申請」按鈕，預填上次資料 | 用戶確認 |
| Q14 v1.1 修正項目 | 重讀規格後發現 12 處違規（精細度欄位/難易度級數/尺寸選填/檔案上限/PriceRangeHint/未登入照片disabled/提示文字 …），須一次補齊 | 用戶確認 |
| Q15 reviewer fixes | 反思審查找到 3 處後端缺陷：(1) PATCH 對 canvas/notes 缺範圍 / 長度驗證 (2) 兩個 public GET 缺 `response_model` (Gate 3 規範) (3) PATCH 空 body 仍 commit；已修並補 4 個測試。 | 反思審查 |

### 待 v2 細緻討論（2026-05-08 記錄）

| 主題 | 待議內容 |
|---|---|
| **CaseDetailDialog 視覺** | 第一版用輕量設計（左大圖 + 右文字 + 底部 CTA）；v2 需更深入討論案例頁雜誌風視覺、是否做 lightbox / 案例分類過濾 / 案例間切換等 |
| **custom_spec 入口** | v2 重新討論：custom_spec 在「客戶想要某商品的不同規格」情境是否真的需要，或是改用「先諮詢再開單」流程取代 |

---

## 1. 範圍

### 1.1 新建檔案

#### Backend（補 SSE）
```
backend/custom/sse.py                        # SSE pub/sub helper（共用 admin / customer）
backend/custom/router.py                     # 加 GET /custom-requests/{id}/sse + GET /admin/custom-requests/sse
```

#### Store 前端
```
store/src/features/custom/
├── api.ts                                   # 11 個 endpoint wrapper
├── queries.ts                               # TanStack Query mutations + queries
├── pages/
│   ├── CustomPage.vue                       # /custom 主頁（案例 + 申請表單）
│   ├── CustomRequestListPage.vue            # /custom/requests 我的申請列表
│   ├── CustomRequestDetailPage.vue          # /custom/requests/:id 詳情 + SSE 訊息
│   └── QuotePage.vue                        # /custom/quote/:token 報價確認
├── components/
│   ├── CustomPhotoForm.vue                  # 客製照片申請表單
│   ├── CaseGallery.vue                      # 案例展示
│   ├── CaseDetailDialog.vue                 # 案例詳情 + 「諮詢類似規格」
│   ├── PhotoUploadField.vue                 # 照片上傳元件（Firebase signed URL）
│   ├── MessageThread.vue                    # 訊息對話 UI（SSE 即時更新）
│   ├── PriceRangeHint.vue                   # 參考價格區間
│   └── QuoteExpireCountdown.vue             # 報價過期倒數
└── composables/
    ├── usePendingFormStorage.ts             # sessionStorage 存表單草稿（Q2-B）
    └── useCustomRequestSse.ts               # SSE 訊息訂閱
```

#### Store 既有檔案修改
```
store/src/features/products/pages/ProductDetailPage.vue
  └─ 加「想要不同規格」按鈕 → 跳 /custom?ref_product_id=xxx&type=custom_spec
store/src/app/router.ts
  └─ 4 個 custom 路由補對應 component（拿掉 Placeholder）
```

### 1.2 不在本範圍

- backend custom 業務邏輯（已完成）
- admin custom_requests UI（已完成）
- 客製訂單付款流程（既有 order 流程處理）

---

## 2. Backend SSE 補實作（Phase 1）

### 2.1 規格

依 [api.md L1068, L1171](../api.md#L1068)：
```
GET /custom-requests/{id}/sse              # 客戶端訂閱（auth + owner 驗證）
GET /admin/custom-requests/sse             # admin 全局訂閱
```

### 2.2 設計

**用 in-memory pub/sub**（不需要 Redis；單 worker 部署 OK）：

```python
# custom/sse.py
class SSEHub:
    """In-memory pub/sub. 每個 subscriber 拿到一個 asyncio.Queue。"""
    customer_subscribers: dict[UUID, list[asyncio.Queue]]  # request_id → [queues]
    admin_subscribers: list[asyncio.Queue]

    def subscribe_customer(request_id) → Queue
    def subscribe_admin() → Queue
    def publish_to_customer(request_id, event) → None
    def publish_to_admin(event) → None
    async def stream(queue) → AsyncGenerator[bytes]
        # yield SSE format: "event: msg\ndata: {...}\n\n"
        # heartbeat 每 30 秒一次："event: heartbeat\ndata: ok\n\n"
```

### 2.3 publish points

修改 `custom/service.py`：
- `post_customer_message()` 結尾 → `hub.publish_to_admin({"type": "new_message", "request_id": ...})`
- `admin_post_message()` 結尾 → `hub.publish_to_customer(request_id, {...})`
- `create_custom_request()` 結尾 → `hub.publish_to_admin({"type": "new_request", ...})`
- `confirm_quote()` / `reject_quote()` / `request_revision()` → 也 publish 給 admin

### 2.4 Heartbeat

每 30 秒推 `event: heartbeat\ndata: ok\n\n` 防 Railway 切連線（既有 admin/notifications/sse.py 有同模式可參考）。

### 2.5 為什麼 SSE 不用 WebSocket
- 訊息單向（server → client），SSE 簡潔
- 自動重連、HTTP/HTTPS 同 transport 不需 upgrade
- Railway 友善（WebSocket 在 serverless 邊緣不穩）

---

## 3. Store 端詳細設計

### 3.1 路由

```
/custom                            CustomPage  公開（未登入也能看）
/custom?type=custom_spec&ref_product_id=xxx   從商品頁帶參數進來
/custom/requests                   CustomRequestListPage  require_auth
/custom/requests/:id               CustomRequestDetailPage  require_auth
/custom/quote/:token               QuotePage  require_auth（spec 強制）
```

### 3.2 CustomPage.vue（主頁）

**結構**：
```
┌─ Hero（雜誌風 — 直接複用 yii_mui_static_pages_spec.md §第二頁設計）
│  「有些照片，值得花一點時間慢慢畫」
│
├─ Section: 完成案例展示（CaseGallery）
│  ├─ 案例網格（後台案例 fetch /api/v1/custom-cases）
│  ├─ 點卡片 → CaseDetailDialog（大圖 + 說明 + 「諮詢類似規格」）
│  └─ 「諮詢類似規格」按鈕 → 滾到下方表單 + 帶 query 預填
│
├─ Section: 客製照片申請表單（CustomPhotoForm）
│  ├─ 照片上傳區（PhotoUploadField）
│  │  - 未登入：disabled + 提示「請先登入後選擇照片」
│  │  - 已登入：拖曳 / 點選 → 上傳 → 顯示縮圖
│  ├─ 畫布尺寸（select 下拉）— 從 /api/v1/canvas-sizes 拉 is_active=true
│  ├─ 難易度（4 選一 + 「讓管理員建議」 = 不送 difficulty）
│  ├─ 備註 textarea
│  ├─ 參考價格區間（PriceRangeHint）— 依尺寸+難度從 /api/v1/custom-photo-prices 計算
│  └─ 「送出申請」按鈕
│      - 未登入：點擊 → 暫存表單到 sessionStorage → 跳 /login?redirect=/custom
│      - 已登入：呼叫 POST /custom-requests
│
├─ Section: 流程說明（複用 static page 4 step 視覺）
│
└─ Section: CTA（雙按鈕：看現成款 / 已是客戶 → 查看我的申請）
```

**Q2-B 邏輯**：
- 未登入：填文字欄位 OK，但「上傳照片」disabled，hint「需登入才能上傳」
- 點「送出」：
  - 未登入 → 暫存 (formData minus photo) 到 sessionStorage[`pending_custom_form`] → redirect to /login?next=/custom
  - 登入後 store 會檢查 sessionStorage → 自動回填表單（photo 還是空）→ user 補上傳 → 送出
- composable `usePendingFormStorage`:
  ```ts
  savePending(formData)     // session storage
  loadPending() → formData | null
  clearPending()
  ```

### 3.3 CustomRequestListPage.vue

```
┌─ 我的客製申請
│  └─ Filter: status (待報價 / 報價中 / 已確認 / 已拒絕 / 已過期)
│
└─ 卡片列表（每筆 1 張）
   ├─ 申請編號 + 申請類型 (照片/規格)
   ├─ 狀態 badge
   ├─ 報價金額（quote_sent / quote_confirmed 才顯示）
   ├─ 報價過期倒數（quote_sent 狀態才顯示）
   └─ 點卡片 → /custom/requests/:id
```

**狀態映射**：
```
quote_pending      → 待報價（橘）
negotiating        → 洽談中（藍）
quote_sent         → 報價已送達，待確認（綠 + 倒數）
draft_revision     → 修改中（黃）
quote_confirmed    → 已確認，已建單（深綠）
quote_rejected     → 已拒絕（灰）
quote_expired      → 已過期（紅）— Q13 顯示「重新申請」CTA
```

### 3.4 CustomRequestDetailPage.vue

```
┌─ 申請資訊區塊
│  ├─ request_type / status / 上傳照片預覽 / 偏好規格
│  └─ 訊息計數
│
├─ 訊息對話 (MessageThread)
│  ├─ 既有訊息 (按時間順序) — fetch GET /custom-requests/{id} 回的 messages
│  ├─ SSE 訂閱新訊息（useCustomRequestSse composable）
│  ├─ 輸入框 + 「送出」（POST /custom-requests/{id}/messages）
│  └─ 訊息送出後局部更新（不等 SSE 自己 push）
│
└─ 動作區塊（依 status）
   ├─ quote_pending: 顯示「可重新上傳照片」按鈕（PATCH photo）
   ├─ quote_sent: 顯示「查看報價」大按鈕 → /custom/quote/:token
   ├─ quote_expired: 顯示「重新申請」按鈕（Q13）→ /custom?prefill=last
   └─ quote_confirmed: 顯示「查看訂單」按鈕 → /orders/:order_id
```

**SSE composable**（`useCustomRequestSse.ts`）：
```ts
useCustomRequestSse(requestId, onNewMessage)
  - 用 EventSource subscribe to /api/v1/custom-requests/{id}/sse
  - onmessage: 解析 event type → 觸發 callback
  - onerror: 自動重連（EventSource 內建）
  - onUnmounted: close
```

### 3.5 QuotePage.vue

```
┌─ /custom/quote/:token
│
├─ 浮水印預覽圖（左側大圖）
│  └─ <img src="/api/v1/custom/quote/{token}/preview" />
│
├─ 報價詳情（右側）
│  ├─ 規格（spec_summary）
│  ├─ 報價金額（quoted_price，大字）
│  ├─ 過期倒數（QuoteExpireCountdown 元件）
│  └─ revision_count 顯示「已修改 N/3 次」
│
└─ 動作按鈕（4 個）
   ├─ 確認製作（primary）
   │   └─ 點擊 → 跳 confirmed dialog
   │       ├─ 列出用戶 ShippingProfile（fetch /users/me/shipping-profiles）
   │       ├─ 沒有 → 顯示「請先去新增收件資料」+ link to /profile/shipping
   │       ├─ 選定後送 POST /custom/quote/{token}/confirm body={shipping_profile_id}
   │       └─ Response → 跳 /checkout/complete?order={order_id}（既有頁）
   │
   ├─ 要求修改（secondary）
   │   └─ 點擊 → 跳 modal 輸入 reason → POST .../request-revision
   │      （response_count 達 3 時 disabled）
   │
   ├─ 拒絕（ghost）
   │   └─ 點擊 → confirm dialog → POST .../reject
   │
   └─ 延長 1 天（small ghost button，is_extended=true 時 disabled）
       └─ POST .../extend
```

### 3.6 商品詳情頁 custom_spec 入口（Q5-A）

`store/src/features/products/pages/ProductDetailPage.vue` 加：
```vue
<button @click="goToCustomSpec">
  <Sparkles /> 想要不同規格？
</button>

function goToCustomSpec() {
  router.push({
    path: '/custom',
    query: {
      type: 'custom_spec',
      ref_product_id: product.id,
      ref_canvas_w: product.canvas_w_cm,
      ref_canvas_h: product.canvas_h_cm,
    }
  })
}
```

CustomPage 收到 `type=custom_spec` query：
- 切換成「客製規格申請」表單（不要照片上傳，要 ref_product_id readonly）
- POST 時 `request_type='custom_spec'`、`ref_product_id` 帶 query

---

## 4. 階段 / 工作分割

### Phase 1 — Backend SSE（~1 小時）
- 寫 `custom/sse.py` SSEHub
- 加兩個 SSE endpoint
- 在 service 各動作 publish
- smoke-test：用 curl 訂閱 + 觸發 publish 驗證

### Phase 2 — Store API + queries 層（~1 小時）
- `api.ts`：11 個 endpoint wrapper + 型別
- `queries.ts`：TanStack mutations / queries
- `composables/useCustomRequestSse.ts` SSE 訂閱
- `composables/usePendingFormStorage.ts` sessionStorage

### Phase 3 — CustomPage（~2-3 小時）
- 案例展示（CaseGallery + CaseDetailDialog）
- 客製照片表單（PhotoUploadField + 動態尺寸下拉 + 參考價）
- 客製規格表單（query type=custom_spec 切換）
- sessionStorage 暫存 + 登入回填
- 「諮詢類似規格」預填邏輯

### Phase 4 — RequestList + RequestDetail（~2 小時）
- List 頁 with status filter + badge
- Detail 頁 messages 對話 UI
- SSE 即時更新訊息
- Q13 過期重申請 CTA

### Phase 5 — QuotePage（~2 小時）
- 預覽圖
- 4 個按鈕 + dialog
- 確認流程（選 shipping_profile + jump 結帳完成頁）

### Phase 6 — 商品詳情入口 + 整合測試（~1 小時）
- ProductDetailPage 加「想要不同規格」按鈕
- e2e 跑：客戶登入 → 看案例 → 申請 → admin 報價 → 客戶確認 → 訂單建立
- 整體 polish

---

## 5. 對應規格（business rules 摘要）

| 規則 | 出處 | 實作位置 |
|---|---|---|
| 客製訂單運費 home=120, conv=70 | module_plan §4.2 | backend confirm_quote 已處理 |
| 客製訂單不適用免運門檻 | api.md L1098 | 同上 |
| 客製訂單不套用折扣券 | api.md L1098 | 同上 |
| 報價有效期 24h | api.md L1108 | backend |
| 延長機會每筆 1 次（+24h） | api.md L1108 | QuotePage 顯示 is_extended 控制按鈕 |
| 修改機會 3 次 | api.md L1116 | QuotePage 顯示 revision_count + disabled |
| 過期自動 expire（5 分掃） | module_plan §4.5 | Celery |
| 建立後系統發歡迎訊息（含天數） | module_plan §4.1 | backend |

---

## 6. 測試覆蓋（self-test plan）

### 6.1 Phase 1 SSE
- [ ] curl 訂閱 customer SSE → 觸發 admin post message → 收到事件
- [ ] curl 訂閱 admin SSE → 觸發 customer create request → 收到事件
- [ ] 30 秒沒事件 → 收到 heartbeat
- [ ] 客戶 SSE 不能訂閱別人的 request_id（403）

### 6.2 Phase 3 CustomPage
- [ ] 未登入填表單 → sessionStorage 有資料 → 登入後表單回填
- [ ] 已登入直接送出 → 後端建立成功 → 跳 RequestDetail 頁
- [ ] 案例「諮詢類似規格」→ 滾到表單 + 規格預填
- [ ] type=custom_spec query → 表單切換成「規格申請」、隱藏照片上傳
- [ ] 參考價依尺寸+難度動態更新
- [ ] 上傳超過 10MB → 前端報錯
- [ ] 上傳非 JPG/PNG → 前端報錯

### 6.3 Phase 4 RequestList + Detail
- [ ] 列表狀態 filter 切換正確
- [ ] 過期狀態顯示「重新申請」CTA
- [ ] Detail 頁訊息 SSE 即時推送（admin 端發訊息 → 客戶端不重新整理收到）
- [ ] 客戶端發訊息 → 局部立即顯示（不等 SSE）
- [ ] quote_pending 可重傳照片
- [ ] quote_sent 跳 QuotePage 按鈕

### 6.4 Phase 5 QuotePage
- [ ] 預覽圖載入
- [ ] 倒數計時準確
- [ ] 4 按鈕依 state disable 正確
- [ ] 確認 → 列出 shipping_profile → 選定 → 跳結帳完成頁
- [ ] 沒 shipping_profile → 引導去新增
- [ ] 拒絕 / 修改 / 延長各別 endpoint 串通

### 6.5 Phase 6 商品入口 + 整合
- [ ] ProductDetail 「想要不同規格」按鈕跳 CustomPage
- [ ] CustomPage 收到 query → 切到 custom_spec 模式
- [ ] 完整 e2e 跑通（客戶 → admin → 客戶確認 → 訂單）

---

## 7. 待確認事項（規劃中遇到再 surface）

1. **檔案上傳容量限制**：規格寫 10MB；前端要不要做圖片壓縮？
   - 建議：不壓縮，超過 10MB 就退錯；客戶用手機原檔通常都 < 10MB
2. **SSE 與 polling 並存 fallback**：SSE 連線失敗 → 自動降為 polling？
   - 建議：第一版不做，EventSource 自帶重連機制
3. **報價預覽圖快取**：每次 fetch 真的重算？或客戶端快取？
   - backend 有 `Cache-Control: no-store` → 每次重算（已實作）

---

## 8. 文件交叉索引

| 內容 | 路徑 |
|---|---|
| 業務需求 | `docs/requirements/store/store_custom.md` |
| Backend module plan | `docs/module_plans/10_custom.md` |
| API 完整定義 | `docs/api.md` §模組十三-十五 |
| 視覺風格 | `docs/yii_mui_static_pages_spec.md` §第二頁 |
| **本實作計畫（這份）** | `docs/module_plans/21_store_custom_frontend.md` |

---

## 9. 變更紀錄

| 日期 | 內容 |
|---|---|
| 2026-05-08 | 初版 — 6 phases 拆分、SSE backend 補實作、user 8 個拍板問題均已收錄 |
