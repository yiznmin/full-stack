# 規格比對報告 — F04 訂單管理

針對 `F04_orders.md` 規劃書，逐項對照 `docs/requirements/admin_orders.md`、`docs/api.md`、`docs/EVENT_MATRIX.md`、`docs/requirements/admin_routes.md`。

---

## 1. api.md 端點比對

| Endpoint | api.md 規定（§ 模組十二）| 規劃書頁面 / 處理 | 結果 |
|---|---|---|---|
| GET /admin/orders | query: `status, search, date_from, date_to, order_type, page, page_size` | OrdersListPage 篩選列；URL query 同步 | ✓ |
| GET /admin/orders/{id} | 含 payment_submissions / production_progress / shipments | OrderDetailPage 主資料源 | ✓ |
| PATCH /admin/orders/{id}/status | body `{status, admin_notes?}`；status ∈ paid / processing / shipped / completed / refund_processing / cancelled | ConfirmStatusDialog；**僅 paid / processing / refund_processing / cancelled 暴露給管理員** | ⚠️1 |
| POST /admin/orders/{id}/shipments | body `{shipment_type}`；resp 201 `{shipment_id, tracking_number, ecpay_logistics_id}`；resp 502 ECpay 失敗 | ShipmentDialog；502 toast「物流系統暫時無法連線」+ 重試 | ✓ |
| PATCH /admin/orders/{id}/production-progress/{progress_id} | body `{status, notes?}`；status ∈ manufacturing / packaging / ready_to_ship | OrderItemsCard row 內按鈕；in_production 不暴露給管理員（自動）| ✓ |
| POST /admin/orders/{id}/refund | body `{refund_amount, returned_item_ids, cancel_reason}` | RefundFinalizeDialog | ✓ |
| PATCH /admin/orders/{id}/payment-submissions/{sub_id}/flag | body `{is_flagged: true, admin_note}`；resp `{payment_deadline}` | PaymentFlagDialog | ✓ |
| PATCH /admin/orders/{id}/admin-notes | body `{admin_notes}` | AdminNotesCard 顯式儲存 | ✓ |

⚠️1 — api.md 列出 PATCH /status 可推進到 `shipped` / `completed`，但 admin_orders.md §5.2 與 §5.10 明確規定 **shipped / completed 由 shipments 聚合自動推進，不由 PATCH /status 觸發**。前端不暴露這兩個選項，避免管理員誤點。後端是否拒絕需詢問（待確認 1）。

---

## 2. requirements/admin_orders.md 業務規則比對

| 規則 | 來源 | 規劃書對應 UX | 結果 |
|---|---|---|---|
| 訂單列表分頁、狀態 / 日期 / 類型篩選、訂單號 / 客戶名 / email 搜尋 | §5.7「訂單列表」 | OrderFilterBar 全部對到 | ✓ |
| 訂單詳情顯示客戶資訊、商品明細、金額明細、收件資料、目前狀態 | §5.7「訂單詳情」 | OrderDetailPage 兩欄佈局已涵蓋 | ✓ |
| 確認付款只能從 pending_payment | §5.7 + §5.2 | HeaderActions 條件渲染：status=pending_payment 才顯示「確認付款」 | ✓ |
| paid 之後不可直接 cancelled，必須走退款 | §5.1「取消 / 退款」 | 詳情頁 status≥paid 時，「取消」按鈕隱藏，改顯「標記退款處理中」 | ✓ |
| flag 付款有誤：重設 payment_deadline = MIN(now()+24h, created_at+48h)；< 6h 觸發「緊急」email 標題 | §5.2 + §5.7 | PaymentFlagDialog 顯示「目前剩餘 X 小時」，並提示是否會觸發緊急標題 | ✓ |
| 出貨呼叫 ECpay API；shipping_snapshot.notify_email null 時 fallback users.email；ECpay 失敗訂單狀態不變 | §5.4 + §5.7 | ShipmentDialog 顯示 notify_email 來源（snapshot 或 fallback）；502 不變狀態 | ✓ |
| 拆單 fulfilled / preorder；shipping_preference together / separate | §5.3 + §5.10 | OrderItemsCard row 顯示拆單；ShipmentsCard 依 preference 推算可建立的 shipment_type | ✓ |
| 內部備註任何狀態可改 | §5.7 | AdminNotesCard 永遠可編輯 | ✓ |
| 退款明細介面：填金額 + 勾 items；勾全部 → refunded；勾部分 → partially_refunded | §5.7「退款明細介面規格」 | RefundFinalizeDialog 完整對應 | ✓ |
| 退款副作用（庫存 / 優惠券 / 回饋券）後端處理 | §5.7「退款副作用規則」 | 前端只送 request 不重算，refetch 後依 server 結果顯示 | ✓ |
| refund_confirmed_at 顯示邏輯（null → 「請客戶確認」；非 null → 「客戶已於 YYYY-MM-DD 確認」）| §5.7「退款流程的雙重確認機制」 | OrderHeader 退款狀態下顯示對應文案 | ✓ |
| 並發保護：狀態變更失敗 → 「訂單狀態已變更，請重新整理」 | §5.2 | 全 mutation onError 處理 409 / 400「狀態」字樣 → toast + invalidate | ✓ |
| 狀態變更需先確認（dialog） | §5.7（語意）+ SOP 對抗式自我審查 | 所有狀態 mutation 走 dialog 確認 | ✓ |
| 完成（completed）由 shipments 全 delivered 或客戶確認觸發 | §5.4 + §5.10 | 前端 admin **不主動推 completed**；只觀察 | ✓ |
| 退款金額 ≤ order.total | §5.7 退款明細介面 | RefundFinalizeDialog superRefine 比對 page-level order.total | ✓ |
| 客製訂單不在 orders.status；以 order_items.custom_request_id != null 識別 | §5.2 註解 + §5.10 | 列表 order_type=custom 篩選；詳情 OrderItemsCard 顯示客製 badge | ✓ |
| Webhook、Celery Beat、客戶端動作不在前端 admin 範圍 | §5.2 / §5.4 | 規劃書 §9 明列「不在範圍」 | ✓ |

---

## 3. EVENT_MATRIX.md 副作用比對（管理員觸發的事件）

| Event | 動作 | 副作用（後端負責）| 前端責任 | 結果 |
|---|---|---|---|---|
| E21 確認付款 | PATCH /status status=paid | production_progress 建立、custom_order_paid 通知、Email 客戶、關閉 payment_submitted | 送 request；refetch 後顯示新 production_progress | ✓ |
| E22 flag 付款有誤 | PATCH /payment-submissions/{sub_id}/flag | 重設 deadline、Email 客戶（< 6h 緊急標題） | dialog 顯示剩餘時數預告 email 標題 | ✓ |
| E25 管理員取消 | PATCH /status status=cancelled | 庫存 / 優惠券回補、Email 客戶 | dialog 強制填 cancel_reason_note | ⚠️2 |
| E35 生產進度推進 | PATCH /production-progress/{id} | 依目標狀態自動 Email 客戶 | row 按鈕；不額外提示 email | ✓ |
| E36 點出貨 | POST /shipments | ECpay → tracking、shipments=shipped、production_progress=shipped、orders.status 聚合、Email 客戶；503 訂單不變 | dialog；503 toast | ✓ |
| E41 標記退款處理中 | PATCH /status status=refund_processing | Email 客戶「申請已受理」；不回補庫存 | dialog 填 reason → 寫入 admin_notes 或 cancel_reason_note | ⚠️3 |
| E42 標記已退款 | POST /refund | 庫存 / 優惠券 / 回饋券副作用、Email 客戶含確認連結 | dialog 勾 items + 金額 | ✓ |
| E42-B 客戶確認退款 | （客戶端，不在 admin） | refund_confirmed_at = now() | 詳情頁顯示已確認時間 | ✓ |

⚠️2 — admin_orders.md §5.7 表中「管理員取消」未在管理員操作清單中（僅在 §5.1 提到「客戶在 paid 前可取消」+ §5.2 的 cancel_reason_code 含 admin_cancelled）。**需確認管理員是否真的有「取消訂單」按鈕、能取消哪些狀態**（待確認 2）。

⚠️3 — PATCH /status `status=refund_processing` 的 body 在 api.md 只接受 `{status, admin_notes?}`，沒有獨立的 `cancel_reason` 欄位。前端 RefundProcessingDialog 應把退款原因寫入 `admin_notes`（追加而非覆蓋），或要求 backend 接 cancel_reason_note。**傾向寫 admin_notes**（待確認 3）。

---

## 4. admin_routes.md 路由比對

| 規定路由 | 規劃書對應 | 結果 |
|---|---|---|
| `/admin/orders` | OrdersListPage | ✓ |
| `/admin/orders/:id` | OrderDetailPage | ✓ |

---

## 5. 手動測試覆蓋表（規劃書 §7 → 此處映射）

| Case 描述 | 預期狀態碼 / 結果 | 驗證手段 |
|---|---|---|
| 列表預設載入 | 200 + 分頁 | screenshot |
| 篩 status / date 等 query 同步 | URL ↔ state 一致 | reload 仍保留 |
| 搜尋訂單號 / email | 命中 | screenshot |
| 點 row 進詳情 | 200 + 完整詳情 | screenshot |
| 確認付款 happy path | PATCH 200 → 詳情新 production_progress | screenshot 前後 |
| flag 付款有誤 | PATCH 200 → 詳情顯示新 deadline 倒數 | screenshot |
| 推進到 processing | PATCH 200 | screenshot |
| 出貨 happy | POST 201 + tracking 顯示 | screenshot |
| 出貨 ECpay 502/503 | 訂單未變、toast 顯示重試 | mock |
| 推進 production_progress | PATCH 200 | screenshot |
| 標記退款處理中 | PATCH 200 + 狀態變 refund_processing | screenshot |
| 退款全額（勾全部） | POST 200 → status=refunded | screenshot |
| 退款部分（勾部分） | POST 200 → status=partially_refunded | screenshot |
| 退款金額 > total | 前端阻擋 | manual |
| 退款金額 ≤ 0 | 前端阻擋 | manual |
| 修改 admin_notes | PATCH 200 + 重 fetch 仍在 | screenshot |
| 401 cookie 失效 | 踢回登入 + next | clear cookie |
| 403 非 admin | 顯示無權限 | mock |
| 404 不存在 | 顯示「訂單不存在」 | bad id |
| 500 / 503 | ErrorState + 重試 | mock |
| 並發 409 / 400 | toast + invalidate | mock |
| F5 reload 詳情 | 重 fetch | screenshot |
| Esc 關 dialog、Tab 走得通 | OK | 手測 |
| < 768px 寬 | 不爆版 | resize |

---

## 6. 差異與待確認

### ⚠️1 PATCH /status 是否拒絕 `shipped` / `completed`
- **規格現狀**：api.md 容許；admin_orders.md 規定 shipped/completed 由聚合自動推進
- **前端決策**：不暴露這兩個選項給管理員（避免誤點）
- **問題**：後端目前是否會接受並執行？若會，需後端補 400 拒絕；若不會，前端只是被動避開
- **問**：這個是否要修？或維持 api.md 描述、前端不暴露就好？

### ⚠️2 是否提供「管理員取消訂單」按鈕
- **規格**：admin_orders.md §5.2 cancel_reason_code 列了 `admin_cancelled`，但 §5.7 操作清單沒「取消訂單」一條
- **EVENT_MATRIX**：E25 寫了「管理員取消訂單」但前置條件不明
- **問**：管理員是否能取消？若能，可取消的狀態是哪些（只 pending_payment？還是 paid 之前都可？paid 之後一律走退款？）

### ⚠️3 RefundProcessing 的原因要寫到哪
- 後端 PATCH /status 沒有 `cancel_reason` 或 `refund_reason` 獨立欄位
- 前端傾向寫到 `admin_notes`（追加格式：`[退款原因 2026-04-29] 客戶不滿意品質\n` + 既有內容）
- **問**：可以這麼做？還是要請後端補欄位？

### ⚠️4 狀態多選篩選
- api.md `?status=` 是單值
- 規劃書傾向先做單選，避免後端異動
- **問**：同意先單選？

### 結論

- ⚠️1：暫不阻擋（前端不暴露），後端是否補 guard 列為 backlog
- ⚠️2：**等待你回覆**（影響 OrderHeader 操作按鈕清單）
- ⚠️3：**等待你回覆**（影響 RefundProcessingDialog 表單結構）
- ⚠️4：傾向先單選（**等待你確認**）

**有 ⚠️2、⚠️3、⚠️4 三項待你決定，未解決前不開始實作。**
