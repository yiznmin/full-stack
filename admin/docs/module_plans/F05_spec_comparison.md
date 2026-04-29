# 規格比對報告 — F05 客製訂單管理

針對 `F05_custom_requests.md` 規劃書，逐項對照 `docs/api.md`、`docs/requirements/admin_orders.md`、`docs/EVENT_MATRIX.md`、`docs/requirements/admin_routes.md`。

---

## 1. api.md 端點比對

| Endpoint | api.md（§ 模組十五）| 規劃書頁面 | 結果 |
|---|---|---|---|
| GET /admin/custom-requests | query: `status, request_type, page, page_size` | ListPage | ⚠️1 |
| GET /admin/custom-requests/{id} | 詳情 + messages（OpenAPI 已含 `messages`、`parent_request_id`、`order_id`、`quoted_at`、`rejected_at`、`user_name`、`user_email`、`admin_notes`）| DetailPage 主資料源 | ✓ |
| PATCH /admin/custom-requests/{id}/mark-negotiating | 手動標記洽談中 | DetailPage HeaderActions | ✓ |
| POST /admin/custom-requests/{id}/quote | body `{quoted_price, detail, surcharge_ids, quote_note?}`、resp `{quote_expires_at}` | QuoteDialog | ✓ |
| POST /admin/custom-requests/{id}/messages | body `{message}` | MessagesCard.MessageInput | ✓ |
| GET /admin/custom-requests/{id}/photo-signed-url | 15 分鐘簽章 URL | PhotoCard 下載按鈕 | ✓（注意 backend 為 stub）|
| GET /admin/custom-requests/sse | SSE bus | F09 統一管理 | ✓ |
| GET /admin/custom-photo-prices | 列出基礎價格表（OpenAPI 已存在）| QuoteDialog 試算列 | ✓ |
| GET /admin/custom-photo-surcharges | 列出加費項目（OpenAPI 已存在）| QuoteDialog 加費勾選 | ✓ |

⚠️1 — api.md 的 status enum 列了 `quote_pending|negotiating|quote_sent|quote_confirmed|quote_rejected|quote_expired`（**6 個**），但 admin_orders.md §5.2 與 EVENT_MATRIX E11-B 都明確規定有 **`draft_revision`** 第 7 個狀態。屬 api.md 文件錯漏。前端按 admin_orders.md 跑 7 個狀態，列表 query 也允許篩 `draft_revision`。**待確認 1**：後端列表 `?status=draft_revision` 是否能正確過濾？或要先補後端 enum？

---

## 2. admin_orders.md 業務規則比對

| 規則 | 來源 | 規劃書對應 UX | 結果 |
|---|---|---|---|
| 7 個 custom_requests.status | §5.2 | StatusBadge 7 色 + 列表篩選 | ✓ |
| 客戶提申請後系統自動發歡迎訊息 | §5.1 客製服務（方案 D）+ E07 | DetailPage MessagesCard 顯示歡迎訊息（差異化視覺）| ✓ |
| 管理員手動標記洽談中（備用） | §5.1 + §5.7 | quote_pending 才顯示「標記洽談中」按鈕 | ✓ |
| 自動進 negotiating（製作系統帶入照片）| §5.1 + EVENT_MATRIX E26 | 不主動操作，由 invalidation 被動更新 status | ✓ |
| 客製申請進 negotiating 後**內容鎖定** | §5.1 | admin 端只看不操作客戶端 | ✓（客戶端規範由 store/ 處理）|
| 報價公式 base × 2.0 倍率 + 加費 + 可手動覆寫 | §5.7 + pricing_formula.md | QuoteDialog 試算列 + 覆寫 input | ✓ |
| 修改次數上限 3 次 | §5.1 + EVENT_MATRIX E11-B | revision badge 顯示 X/3，admin 端不限制按鈕（限制在 store/ 端）| ✓ |
| 客戶要求修改 → status: quote_sent → draft_revision | §5.1 | admin 端被動顯示 status，draft_revision 仍可開報價 dialog 重送 | ✓ |
| 報價逾期（Celery 自動，5 分鐘）| §5.2 | quote_expired badge 顯示，dialog 不可開 | ✓ |
| 客戶確認報價 → 同步建立訂單 | §5.1 + E14/E15 | 詳情頁顯示 `order_id` 連結（已在 detail response）| ✓ |
| 客戶拒絕 / 重新申請 parent_request_id 鏈 | §5.1 + E16/E17 | 詳情頁顯示「此為重新申請，原申請 #X」可跳鏈 | ✓ |
| 報價金額來源 = 公式 or 管理員覆寫 | §5.7 | 試算 + 覆寫 input | ✓ |
| 訊息系統三層通知（admin 端）| EVENT_MATRIX E10 | 第一版本不接 SSE，靠 visibility/refetch 模擬（待確認 2）| ⚠️2 |
| 訊息系統三層通知（admin 發訊→客戶）| EVENT_MATRIX E09 | admin 不負責，後端做 | ✓ |
| 並發保護 | §5.2 | mutation onError 攔 409/400「狀態」字樣 + invalidate | ✓ |
| 客製照片下載（Firebase 私有）| §5.7 | photo-signed-url endpoint，admin 端開新分頁 | ✓ |
| production_job 在 detail 顯示（filled_template 預覽 / approved 狀態）| §5.1 + E11 前置 | detail response **沒** join production_job — 要另打 endpoint，或先省略 | ⚠️3 |

---

## 3. EVENT_MATRIX 副作用比對（管理員觸發的事件）

| Event | 動作 | 副作用 | 前端責任 | 結果 |
|---|---|---|---|---|
| E08 標記洽談中 | PATCH /mark-negotiating | UPDATE status | 送 request → invalidate | ✓ |
| E09 admin 發訊息 | POST /messages | INSERT message + 通知客戶 | 送 request → 訊息流 invalidate | ✓ |
| E11 送出報價 | POST /quote | UPDATE status, quoted_price, quote_expires_at + INSERT message + Email 客戶 | 送 request → invalidate；QuoteSummaryCard 出現 | ✓ |

被動觀察的事件（admin 端只收結果不操作）：
- E07（客戶提申請）— invalidate 列表
- E10（客戶發訊息）— SSE / refetch 進詳情
- E11-B（客戶要求修改）— invalidate 詳情，狀態改為 draft_revision
- E12（Celery 報價逾期）— 偶爾 refetch
- E13（客戶延長）— refetch；is_extended 更新
- E14（客戶確認）— refetch；order_id 出現
- E16（客戶拒絕）— refetch
- E17（客戶重新申請）— 列表 invalidate，新申請帶 parent_request_id
- E18（客戶換照片）— 詳情 invalidate；photo_url 新值
- E26（管理員在製作系統帶入照片）— 詳情 invalidate；status 自動變 negotiating

---

## 4. admin_routes.md 路由比對

| 規定路由 | 規劃書對應 | 結果 |
|---|---|---|
| `/admin/custom-requests` | CustomRequestsListPage | ✓ |
| `/admin/custom-requests/:id` | CustomRequestDetailPage | ✓ |

sidebar 既有「客製訂單」已連到 `/admin/custom-requests`（不需動）。

---

## 5. 手動測試覆蓋表

對應 `F05_custom_requests.md §7` 已完整列出 22 個 case，含 happy path + 錯誤路徑 + 邊界 + 響應式。

---

## 6. 差異與待確認

### ⚠️1 列表 status query 是否支援 `draft_revision`
- api.md enum 缺漏，admin_orders.md / EVENT_MATRIX 有
- **問**：後端是否接受？要不要先補 api.md / enum？
- **傾向**：列表前端 select 出全部 7 個選項，後端如果回 422 就變成 backlog 修

### ⚠️2 第一版本是否接 SSE
- F09 通知中心還沒做。SSE bus 集中在 F09 比較合理。
- 第一版本沒 SSE → 詳情頁訊息流靠：(a) admin 送訊息後立刻 refetch；(b) `document.visibilitychange` 回前景時 refetch。
- 客戶在客製對話頁打字 → admin 開的詳情頁不會即時看到 → 需手動切視窗或重新整理。
- **傾向**：先做 (a)+(b)，F09 落地後補 SSE。同意？

### ⚠️3 production_job 預覽
- detail response 沒含 production_job 資訊
- 報價 dialog 需要 `production_job.approved == true` 才能送出（後端會 400 攔截）
- 詳情頁要顯示 filled_template 預覽圖才能讓管理員審視「我要報價的依據」
- 解法 A：detail 加 join 回 `production_job` 子物件（後端動）
- 解法 B：前端在 detail 載入時，找對應 job_id 另打 `/admin/production/jobs/{id}`（多一個 query，現有 endpoint 是否回完整 filled_template_url？要確認）
- 解法 C：第一版本先不顯示預覽，只在 dialog 內顯示「production_job 必須已 approved」提示，靠後端攔截
- **傾向 C**（最快），F06 製作系統做完後一起補預覽（規劃書 §9 已列為「不在本模組範圍」）

### ⚠️4 報價金額上限
- zod 我先寫 max 100000
- **問**：實際業務上限？要不要拿掉 max（後端校驗即可）？
- **傾向**：拿掉前端硬上限，只校驗 > 0 + 整數

### 結論

- ⚠️1：先全 7 個都暴露，碰到 422 再補
- ⚠️2：**等待你回覆**
- ⚠️3：**等待你回覆**（傾向 C）
- ⚠️4：**等待你回覆**（傾向拿掉 max）

**有 ⚠️2、⚠️3、⚠️4 三項待確認，未解決前不開始實作。**
