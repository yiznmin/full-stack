# F05 客製訂單管理 模組規劃書

> 對應後端 Module 10 (custom)、admin_routes 客製訂單區、admin_orders.md 客製章節 §5.1。
> 規格來源見章節末「規格定位」表。本規劃書遵循 `admin/docs/frontend_sop.md`。

---

## 1. 路由清單

| 路由 | 頁面元件 | guard | 說明 |
|---|---|---|---|
| `/admin/custom-requests` | `CustomRequestsListPage.vue` | requireAdmin | 申請列表 + 篩選（狀態 / 類型）|
| `/admin/custom-requests/:id` | `CustomRequestDetailPage.vue` | requireAdmin | 詳情：申請內容、訊息對話、報價操作 |

side bar 入口要新增「客製訂單」連結（目前 sidebar 已有「客製訂單」項目，路由是 `/admin/custom-requests`，沿用）。

---

## 2. 後端 API 對應表

| Endpoint | Method | 用途 | 觸發頁面 |
|---|---|---|---|
| `/admin/custom-requests` | GET | 列表（分頁、status / request_type 篩選） | ListPage |
| `/admin/custom-requests/{id}` | GET | 詳情（含 messages、photo_url 簽章前的引用 path）| DetailPage |
| `/admin/custom-requests/{id}/photo-signed-url` | GET | 取得 15 分鐘簽章 URL，下載原圖 | DetailPage 點「下載原圖」|
| `/admin/custom-requests/{id}/mark-negotiating` | PATCH | 手動標記洽談中 | DetailPage（少數情境）|
| `/admin/custom-requests/{id}/messages` | POST | 管理員發訊息 | DetailPage 對話區 |
| `/admin/custom-requests/{id}/quote` | POST | 送出報價 + 寄初稿 email | DetailPage `QuoteDialog` |
| `/admin/custom-requests/sse` | GET (SSE) | 推播訊息 / 通知 — **F09 通知中心擁有 SSE bus，本模組只訂閱** | （不在本模組）|

> SSE 訂閱由 F09 統一管理（每個分頁一條長連線；推播訊息按 type 分流）。本模組詳情頁從 F09 取「目前訂閱中的 SSE event」並 filter `request_id == 本頁` 來局部 refetch。本模組**不**自己建第二條 SSE 連線。
> 第一個迭代如果 F09 還沒做，先用「焦點回視窗時 refetch」+「用戶送訊息後立刻 refetch」即時感模擬，等 F09 落地再串。

---

## 3. 元件樹

```
CustomRequestsListPage
├─ PageHeader
├─ FilterBar
│  ├─ StatusSelect（7 個狀態，可單選）
│  ├─ TypeSelect（custom_photo / custom_spec）
│  └─ ClearFilters
├─ AppDataTable
│  └─ row：申請號 / 客戶 / 類型 / 狀態 / 報價金額 / 建立時間 / revision_count
└─ AppPagination

CustomRequestDetailPage
├─ Breadcrumb（工坊 / 客製訂單 / #...）
├─ Header
│  ├─ Title + StatusBadge（7 種色票）
│  ├─ revision badge（X / 3）
│  └─ HeaderActions（依 status 浮現）
│     ├─ 標記洽談中（quote_pending only）
│     └─ 開啟報價 dialog（quote_pending / negotiating / draft_revision）
├─ Grid 兩欄
│  ├─ Main 欄
│  │  ├─ RequestInfoCard（畫布 / 細緻度 / 難易度 / 客戶備註 / parent_request 連結）
│  │  ├─ PhotoCard（顯示縮圖 + 下載原圖按鈕呼叫 signed-url endpoint）
│  │  ├─ ProductionJobCard（顯示對應 production_job 狀態與 filled_template 預覽，若已 approved 顯示「可送報價」）
│  │  └─ MessagesCard
│  │     ├─ 訊息流（按 created_at asc）
│  │     ├─ 系統歡迎訊息標記（差異化視覺）
│  │     └─ MessageInput（admin 端送訊息）
│  └─ Side 欄
│     ├─ CustomerInfoCard
│     ├─ TimelineCard（建立 / 報價送出 / 報價過期 / 重新申請鏈）
│     └─ QuoteSummaryCard（已送報價時：金額 / 細緻度 / 加費項目 / quote_expires_at / is_extended）
└─ Dialogs
   └─ QuoteDialog（POST /quote — 表單欄位：quoted_price / detail / surcharges checkbox / quote_note）
```

---

## 4. 狀態 / Query 設計

```ts
const KEYS = {
  customRequestsList: (params) => ['admin', 'custom-requests', 'list', params] as const,
  customRequest:      (id)     => ['admin', 'custom-requests', 'detail', id] as const,
  surchargesList:                ['admin', 'custom-photo-surcharges'] as const,
  customPhotoPrices:             ['admin', 'custom-photo-prices'] as const,
}
```

- 列表 staleTime 30s
- 詳情 staleTime 10s
- 任一 mutation 成功 → invalidate `['admin','custom-requests']`
- F09 SSE 訂閱回傳 `request_id` 時，invalidate 對應 detail key

`Pinia store` — 不需要。filter / dialog 全 page-local。

---

## 5. zod schemas（admin/src/features/custom_requests/schemas.ts）

```ts
const customStatus = z.enum([
  'quote_pending','negotiating','quote_sent','draft_revision',
  'quote_confirmed','quote_rejected','quote_expired',
])

const filterSchema = z.object({
  status:       customStatus.optional(),
  request_type: z.enum(['custom_photo','custom_spec']).optional(),
  page:         z.coerce.number().int().min(1).default(1),
  page_size:    z.coerce.number().int().min(10).max(100).default(20),
})

const messageSchema = z.object({
  message: z.string().trim().min(1, '訊息不可為空').max(2000),
})

const quoteSchema = z.object({
  quoted_price:  z.coerce.number().int().positive().max(100000),
  detail:        z.enum(['rough','standard','detailed','premium']),
  surcharge_ids: z.array(z.string().uuid()),
  quote_note:    z.string().max(1000).optional().nullable(),
})
```

---

## 6. 設計決策

| 項目 | 決策 |
|---|---|
| 7 種狀態色票 | 沿用 F04 模式：pending=warning、negotiating=info、quote_sent=accent、draft_revision=warning、quote_confirmed=success、quote_rejected=muted、quote_expired=muted |
| 訊息流 UI | admin 訊息靠右、customer 靠左；系統歡迎訊息置中、灰底；無已讀指示（規格無此欄位）|
| 訊息送出 | 顯式按 Enter 或「送出」按鈕；Shift+Enter 換行 |
| 報價金額顯示 | 系統建議價（base × multiplier）+ 加費總和 = 試算列；管理員確認價 input（`tabular-nums`，自動 prefill 試算值）|
| 加費項目 | checkbox 列表（從 `system_settings` / `custom_photo_surcharges` 拉），勾選後即時加總並更新試算 |
| 客戶端的更換照片 / 修改規格 | 不在 admin 範圍 — 但 detail 頁要監聽 invalidation，被動顯示新值 |
| 一頁多管理員並發 | 後端有 SELECT FOR UPDATE；前端 mutation onError 攔截 409 / 400 → toast「狀態已變更」+ refetch |

---

## 7. 手動測試覆蓋表

| Case | 預期 | 驗證 |
|---|---|---|
| 列表預設載入 | 200 + 分頁 | screenshot |
| 篩 status / request_type | URL query 同步 | reload 仍保留 |
| 點 row 進詳情 | 200 + 訊息流載入 | screenshot |
| 標記洽談中（quote_pending）| PATCH 200，badge 變 negotiating | screenshot |
| 標記洽談中（非 quote_pending）→ 不顯示按鈕 | UI 條件渲染 | screenshot |
| 下載原圖 | GET signed-url 200 → 開新分頁 | screenshot + URL 正確 |
| 送訊息 | POST 200 → 訊息出現在流末 | screenshot 前後 |
| 送訊息（空字串）| 前端阻擋送出 | manual |
| 開報價 dialog（status=negotiating）| dialog 開啟、試算列顯示 | screenshot |
| 開報價 dialog（status=quote_sent）→ 按鈕隱藏 | UI 條件 | screenshot |
| 勾加費項目 | 試算金額即時更新 | screenshot |
| 手動覆寫 quoted_price | 試算列保留、最終以管理員價為準 | screenshot |
| 送出報價 | POST 200，狀態變 quote_sent，QuoteSummaryCard 顯示報價 | screenshot |
| 送出報價（production_job 未 approved）| 後端 400，前端 toast | mock |
| revision_count 顯示 | 詳情頁 `2 / 3` 之類 badge | screenshot |
| revision_count = 3 後客戶要求修改 | （客戶端動作，admin 只看到 status=draft_revision + admin_notes 多一條）| 手測或注入 |
| parent_request 連結 | 詳情頁顯示「此申請為重新申請，原申請 #X」並可點擊跳過去 | screenshot |
| quote_expired 看起來 | 灰底 badge，不可開報價 dialog | screenshot |
| 401 cookie 失效 | 踢回 login + next | clear cookie |
| 403 非 admin | 顯示無權限 | mock |
| 404 不存在 | 顯示「申請不存在」+ 返回列表 | bad id |
| F5 reload 詳情 | 重 fetch | screenshot |
| < 768px 寬 | 不爆版 | resize |

---

## 8. 規格定位（規格比對報告會用到）

| 規格 | 來源檔案 |
|---|---|
| 路由 | `docs/requirements/admin_routes.md` |
| 客製生命週期 | `docs/requirements/admin_orders.md` §5.1 客製服務（方案 D）|
| 7 個 custom_requests.status | `docs/requirements/admin_orders.md` §5.2 |
| 報價計算公式 / 倍率 / 覆寫 | `docs/requirements/pricing_formula.md` + `admin_orders.md` §5.7 |
| 訊息三層通知（SSE / admin_notif / email）| `docs/EVENT_MATRIX.md` E09–E10 |
| 修改次數限制 | `docs/requirements/admin_orders.md` §5.1 末段 + EVENT_MATRIX E11-B |
| 從製作系統帶入照片 → 自動 negotiating | `docs/EVENT_MATRIX.md` E26 |
| 重新申請鏈 parent_request_id | `docs/EVENT_MATRIX.md` E17 |
| 客戶端會影響 admin 顯示的事件 | E11-B / E13 / E14 / E16 / E17 / E18 |
| 資料表欄位 | `docs/schema.md` custom_requests / custom_request_messages / custom_photo_surcharges / custom_photo_prices |

---

## 9. 不在本模組範圍

- 客戶端報價確認頁（/custom/quote/:token） — 屬 store/
- 客戶上傳照片 / 申請建立 — 屬 store/
- Celery Beat 報價逾期 — 屬 backend
- 製作系統內「從客製申請帶入照片」操作 — 屬 F06 製作系統
- 通知中心列表 — 屬 F09，本模組不渲染 admin_notifications；但要假設 SSE 推播會讓詳情頁更新

---

## 10. 待確認事項

1. **SSE 是否本迭代要做**：F09 還沒做。第一版本傾向「不接 SSE，靠 visibility-change refetch + mutation 後立刻 refetch」模擬即時感；F09 落地後一起補。**問**：同意這樣的階段性？
2. **加費項目 / 報價試算的後端 endpoint**：規格說有 `custom_photo_surcharges` 與 `custom_photo_prices` 表，但 api.md 沒列「給 admin 拉這兩張表」的 endpoint。報價 dialog 需要它們才能顯示加費勾選清單與系統建議價。**問**：這兩個 endpoint 後端有嗎？沒有要先補後端？
3. **production_job 預覽 / approved 狀態**：詳情頁要顯示對應 job 的 filled_template 縮圖與「是否 approved」。`GET /admin/custom-requests/{id}` 的 response 是否會 join 該 job？若不會，前端要不要另外打 `/admin/production/jobs/{job_id}`？**問**：請確認 detail 是否含 production_job snapshot。
4. **報價 quoted_price 上限**：zod 我先寫 max 100000。實際業務上限是？
