# F04 訂單管理 模組規劃書

> 對應後端 Module 09 (orders)、admin_routes 訂單區、admin_orders.md。
> 規格來源見章節末「規格定位」表。本規劃書遵循 `admin/docs/frontend_sop.md`。

---

## 1. 路由清單

| 路由 | 頁面元件 | guard | 說明 |
|---|---|---|---|
| `/admin/orders` | `OrdersListPage.vue` | requireAdmin | 訂單列表 + 篩選 + 搜尋 |
| `/admin/orders/:id` | `OrderDetailPage.vue` | requireAdmin | 訂單詳情（狀態流、出貨、退款、備註）|

兩條路由統一在 `admin/src/app/router.ts` 加在 layout 之下。`AdminLayout` sidebar 已有「訂單管理」入口。

---

## 2. 後端 API 對應表

| Endpoint | Method | 用途 | 觸發頁面 |
|---|---|---|---|
| `/admin/orders` | GET | 列表（分頁、篩選、搜尋） | OrdersListPage |
| `/admin/orders/{id}` | GET | 詳情 | OrderDetailPage |
| `/admin/orders/{id}/status` | PATCH | 推進狀態（paid / processing / refund_processing / cancelled） | OrderDetailPage |
| `/admin/orders/{id}/shipments` | POST | 出貨（呼叫 ECpay） | OrderDetailPage / ShipmentDialog |
| `/admin/orders/{id}/production-progress/{progress_id}` | PATCH | 推進生產進度 | OrderDetailPage |
| `/admin/orders/{id}/payment-submissions/{sub_id}/flag` | PATCH | 標記付款資訊有誤 | OrderDetailPage / PaymentFlagDialog |
| `/admin/orders/{id}/refund` | POST | 標記已退款（含勾選 items 與金額） | OrderDetailPage / RefundDialog |
| `/admin/orders/{id}/admin-notes` | PATCH | 修改內部備註 | OrderDetailPage |

> Request / response 欄位以 `docs/api.md` 為準；本模組不重列 schema，由 zod 對齊。

---

## 3. 元件樹

```
OrdersListPage
├─ PageHeader（含主標、副標、總筆數）
├─ OrderFilterBar
│  ├─ SearchInput（搜尋訂單號 / 客戶名 / email）
│  ├─ StatusMultiSelect（10 個狀態，可多選；query 仍以單一 status 查—多選時拆多個 query 或前端 client filter）
│  ├─ DateRangePicker（date_from / date_to）
│  ├─ OrderTypeSelect（all / regular / custom）
│  └─ ClearFilters
├─ OrdersTable
│  ├─ row：訂單號 / 客戶 / 類型 badge / 狀態 badge / 金額 / 下單時間 / 動作
│  └─ hover row → 點擊跳詳情
├─ Pagination
└─ EmptyState（無結果）

OrderDetailPage
├─ Breadcrumb（工坊 / 訂單 / #PL-...）
├─ OrderHeader
│  ├─ OrderNumber + OrderStatusBadge（10 種色票）
│  ├─ TimelineSummary（建立 → 付款 → 出貨 → 完成 / 退款）
│  └─ HeaderActions（依目前狀態浮現的主操作按鈕）
├─ Grid 兩欄（lg: 8/4）
│  ├─ Main 欄
│  │  ├─ OrderItemsCard
│  │  │  └─ row：商品名（snapshot）+ 規格 + 單價 + 數量（fulfilled / preorder 拆顯）+ ProductionProgress 子卡片
│  │  ├─ ShipmentsCard
│  │  │  ├─ shipment 行：類型 / status / tracking / 動作（複製單號 / 出貨）
│  │  │  └─ CreateShipmentButton（依 fulfilled / preorder 與 shipping_preference）
│  │  ├─ PaymentSubmissionsCard
│  │  │  └─ 每筆 submission：金額 / 帳號末五碼 / 時間 / FlagBadge / FlagButton
│  │  └─ AdminNotesCard（inline 編輯，autosave 或顯式儲存）
│  └─ Side 欄
│     ├─ CustomerInfoCard（user.name / email / 聯絡電話）
│     ├─ ShippingSnapshotCard（收件人 / 取貨方式 / 地址或門市 / notify_email）
│     ├─ AmountSummaryCard（subtotal / discount + 折扣來源 / shipping / total / refund_amount）
│     └─ HistoryCard（status_history 簡化版：何時改成什麼狀態，誰改的）
└─ Dialogs（teleport）
   ├─ ConfirmStatusDialog（推進 paid / processing / cancelled）
   ├─ ShipmentDialog（fulfilled or preorder，呼叫 ECpay 前確認收件資訊）
   ├─ PaymentFlagDialog（填管理員備註 + 預覽 email 標題會不會變「緊急」）
   ├─ RefundProcessingDialog（status → refund_processing，填退款原因）
   └─ RefundFinalizeDialog（勾 items + 填金額 → POST /refund）
```

---

## 4. 狀態 / Query 設計

### TanStack Query keys（沿用 F03 命名風格）

```ts
const KEYS = {
  ordersList: (params: OrdersListParams) =>
    ['admin', 'orders', 'list', params] as const,
  order:       (id: string)              => ['admin', 'orders', 'detail', id] as const,
}
```

- `OrdersListParams` 包：`status?: OrderStatus[] | OrderStatus`、`search?`、`date_from?`、`date_to?`、`order_type?`、`page`、`page_size`
- 列表 staleTime 30s；詳情 staleTime 10s（狀態變動較頻繁）
- 任一 mutation 成功 → invalidate `['admin','orders']`（連列表帶詳情）

### Pinia store

不需 global store。詳情頁所有 dialog 開關用 page-local `ref`；filter state 走 query string（`useRoute().query` ↔ params），保證 F5 / 分享網址 / 上下頁可重現。

---

## 5. zod 表單 schema（admin/src/features/orders/schemas.ts）

```ts
const orderStatusEnum = z.enum([
  'pending_payment','payment_expired','paid','processing',
  'shipped','completed','cancelled',
  'refund_processing','refunded','partially_refunded',
])

const filterSchema = z.object({
  search:     z.string().trim().max(80).optional(),
  status:     z.array(orderStatusEnum).optional(),
  date_from:  z.string().date().optional(),
  date_to:    z.string().date().optional(),
  order_type: z.enum(['regular','custom']).optional(),
  page:       z.coerce.number().int().min(1).default(1),
  page_size:  z.coerce.number().int().min(10).max(100).default(20),
})

const flagPaymentSchema = z.object({
  admin_note: z.string().min(2, '請說明哪裡有誤').max(500),
})

const adminNotesSchema = z.object({
  admin_notes: z.string().max(2000),
})

const refundProcessingSchema = z.object({
  reason: z.string().min(2).max(500),  // 寫入 admin_notes 或 cancel_reason_note
})

const refundFinalizeSchema = z.object({
  refund_amount:      z.coerce.number().int().positive(),
  returned_item_ids:  z.array(z.string().uuid()).min(1, '至少勾一項'),
  cancel_reason:      z.string().min(2).max(500),
}).superRefine((v, ctx) => {
  // refund_amount ≤ order.total（執行期由 page 注入 order.total 比對）
})
```

> 客戶取消、Celery 自動逾期、ECpay webhook、客戶確認收貨 / 退款 — **不在前端 admin 介面**，列為觀察點而非操作。

---

## 6. 設計決策（沿用 admin/docs/design_system.md）

| 項目 | 決策 |
|---|---|
| 狀態色票 | 10 個狀態統一用 `state-*` token：`pending_payment` 暖警示、`paid` 木綠、`shipped` 木藍、`completed` 木褐穩、`cancelled` 灰、`refund_*` 沙銅 |
| 表格密度 | 沿用 F03 商品列表行高 56px、12px 內距 |
| Dialog | 沿用今天剛修好的 flex column + body 可捲版本 |
| 訂單號樣式 | `font-mono` 強調 + 點擊複製（hover 顯示複製 icon）|
| 金額欄 | 一律 `font-tabular`、千分號、小數 2 位 |
| 日期 | `YYYY-MM-DD HH:mm`（zh-TW）；表格中 hover 顯示完整 ISO + 時區 |
| 出貨 / 退款 dialog | 強制二次確認；不可重試的危險動作 → 按鈕用 `danger` variant |

特殊處理：

- 並發保護回的 `409 / 400 「狀態已變更」` 錯誤訊息要友善：「訂單狀態已被其他人變更，已自動重新整理」並 `qc.invalidateQueries(KEYS.order(id))`
- ECpay 出貨 503：toast「物流系統暫時無法連線，請稍後再試」+ 顯示重試按鈕
- 付款剩餘時間 < 6h：在訂單詳情頁頂端用紅色 banner 顯示倒數，並提示 flag 時 email 會用「緊急」標題

---

## 7. 手動測試覆蓋表

| Case | 預期結果 | 驗證手段 |
|---|---|---|
| 列表預設載入 | 看到分頁、最新訂單在最上 | screenshot + network 200 |
| 篩 status=paid + date_from | URL query 同步、結果只剩符合者 | screenshot + 重新整理仍保留 |
| 搜尋訂單號 | 命中精確訂單 | screenshot |
| 搜尋客戶 email | 模糊命中 | screenshot |
| 切到客製訂單 | 列表只剩 order_type=custom | screenshot |
| 點 row 進詳情 | URL 更新、資料載入 | screenshot |
| pending_payment：點「確認付款」 | dialog 確認 → status=paid，detail 重 fetch、付款卡 disabled、production_progress 已建立 | screenshot 前後 |
| pending_payment：flag 付款有誤 | dialog 填原因 → API 200、payment_deadline 重設、UI 顯示新倒數 | screenshot + 確認 deadline 對 |
| paid：推進到 processing | dialog 確認 → 列表 / 詳情狀態都更新 | screenshot |
| processing：建立 fulfilled shipment | dialog 確認 → tracking 顯示、狀態自動跳 shipped | screenshot |
| processing：ECpay 503 | toast 顯示、訂單狀態未變 | mock 503 |
| shipped：手動推 production_progress 到 packaging | row 按鈕變 packaging | screenshot |
| paid：標記退款處理中 | dialog 填原因 → status=refund_processing | screenshot |
| refund_processing：勾全部 + 填金額 | status=refunded、refund_amount 顯示、refund_confirmed_at 仍 null（顯示「請客戶確認」）| screenshot |
| refund_processing：勾部分 | status=partially_refunded | screenshot |
| 內部備註 inline 改 + 儲存 | API 200、其他人 reload 仍在 | screenshot |
| 401（cookie 過期） | 自動踢回 `/admin/login?next=...` | 清 cookie 測 |
| 403（非 admin） | 顯示「無權限」頁 | mock |
| 404（id 不存在） | 顯示「訂單不存在」+ 返回列表連結 | screenshot |
| 500 | 顯示 ErrorState，可重試 | mock |
| 並發衝突（後端 409） | toast「狀態已變更」+ refetch | mock |
| F5 reload 詳情 | 正常重 fetch | screenshot |
| 鍵盤 Tab + Esc 關 dialog | OK | 手測 |
| 行動寬度 < 768 | 列表退化單欄、詳情主側欄堆疊、不爆版 | resize |

---

## 8. 規格定位（規格比對報告會用到）

| 規格 | 來源檔案 |
|---|---|
| 路由 | `docs/requirements/admin_routes.md`（`/admin/orders`、`/admin/orders/:id`）|
| 訂單生命週期 | `docs/requirements/admin_orders.md` §5.1 |
| 狀態一覽 | `docs/requirements/admin_orders.md` §5.2 |
| 並發保護 / 48h 期限 / 緊急提醒 | `docs/requirements/admin_orders.md` §5.2 |
| 拆單邏輯 | `docs/requirements/admin_orders.md` §5.3 |
| ECpay 出貨流程 | `docs/requirements/admin_orders.md` §5.4 |
| 運費 / 免運 | `docs/requirements/admin_orders.md` §5.5（admin 端只「顯示」不計算）|
| 金額計算 | `docs/requirements/admin_orders.md` §5.6 |
| 管理員操作清單 | `docs/requirements/admin_orders.md` §5.7 |
| 退款副作用 / 退款明細介面 | `docs/requirements/admin_orders.md` §5.7 末段 |
| status / shipments 聚合 | `docs/requirements/admin_orders.md` §5.10 |
| API 規格 | `docs/api.md` admin orders 區段 |
| 事件副作用 | `docs/EVENT_MATRIX.md` E19–E25, E35–E42-B |
| 資料表欄位 | `docs/schema.md` orders / shipments / order_items / production_progress |

---

## 9. 不在本模組範圍

以下功能屬其他模組或客戶端，本模組「只觀察、不操作」：

- 客戶端取消 / 確認收貨 / 確認退款收到 — 屬 `store/`，前端 admin 不做
- ECpay Webhook — 後端
- Celery Beat（payment_expired / quote_expired / shipment_overdue）— 後端
- 客製申請報價流程 — 屬 F05 (custom_requests)，本模組僅在訂單列表用 `order_type=custom` 標記，不處理 quote_* 狀態
- 折扣券發券邏輯 — 屬 F08 (discounts)
- 通知中心 — 屬 F09，本模組不直接渲染 admin_notifications，但要假設背景的 SSE 推播會讓相鄰分頁更新

---

## 10. 待確認事項

1. **狀態多選篩選**：規格只說「按狀態篩選」，未明示是否多選。我預設前端 `status: OrderStatus[]`，後端目前是 `?status=` 單值 — 是否要先補後端、或前端先單選？傾向**先單選**避免後端 API 異動，改善列為下個迭代。
2. **AdminNotes 的 autosave**：使用者操作頻率與意圖不確定。傾向用「顯式按儲存」按鈕，避免每打一字打一次 API。
3. **production_progress 在訂單詳情頁的層級**：規格 §5.7 說「每筆 order_item 旁顯示」，本規劃把它放在 OrderItemsCard 的 row 子卡片，與規格一致。
4. **狀態並發 409 的標準錯誤格式**：等實際 API call 看後端怎麼回，再決定 i18n 文字。
