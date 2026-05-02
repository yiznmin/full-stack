# 事件 → 狀態變更 → 通知傳遞 對照表(EVENT_MATRIX)

> 系統中每一個「觸發事件」會連帶引起什麼狀態變更、資料庫寫入、訊息/通知/Email 發送?
> 本文件把所有散落在 23 份文件裡的事件集中成一張總表,方便:
> - **實作時**:寫一個 handler 就能對照這張表列出所有副作用,避免漏寫
> - **測試時**:每個事件的預期副作用都是測試案例
> - **除錯時**:「為什麼這筆訂單沒收到 email」→ 回頭查這張表
> - **修改時**:改動任一欄位前先看依賴
>
> **版本**:v1.0(已包含 ROUND 1~8 所有決議)

---

## SSE 活躍連線定義

**管理員端:** 管理員登入後台的**任何頁面**時 SSE 連線活躍;登出或關閉所有後台分頁 → 斷線 → 視為「不在後台」。

**客戶端:** 客戶開啟客製申請對話頁時活躍,離開即斷線(僅「對話頁」算活躍)。

**三層通知邏輯(客戶 → 管理員):**
| 管理員狀態 | 通知方式 |
|---|---|
| 開著該申請的對話頁 | SSE 推播,無 admin_notification,無 email |
| 在後台但不在對話頁 | admin_notification + SSE 推播角標,無 email |
| 完全不在後台 | admin_notification + 寄 email 通知管理員 |

**客戶端兩層邏輯(管理員 → 客戶):**
| 客戶狀態 | 通知方式 |
|---|---|
| 在對話頁 | SSE 推播,無 email |
| 不在對話頁 | 寄 email |

---

## 一、會員相關事件

### E01|客戶註冊

- **觸發者**:訪客
- **DB 寫入**:INSERT `users`(is_email_verified=false)+ INSERT `email_verification_tokens`(token_type=signup, expires_at=now+24h)
- **Email**:驗證信 → 該用戶
- **來源**:`auth_users.md §2`

### E02|Email 驗證完成(signup token)

- **觸發者**:客戶點驗證連結
- **狀態變更**:`users.is_email_verified: false → true`
- **DB 寫入**
  - UPDATE `users`、UPDATE `email_verification_tokens.used_at`
  - **自動觸發發放 new_user 歡迎券** → INSERT `user_coupons`(快照 coupon_configs 當下參數)
- **觸發條件**:`users.is_email_verified 從 false 變為 true` 的同一 transaction 內觸發
- **來源**:`auth_users.md §6`、ROUND 6

### E03|Email 變更申請

- **觸發者**:客戶於個人資料頁輸入新 email
- **前置檢查**:新 email 不得與 `users.email` 或 `users.pending_email` 任一相同
- **DB 寫入**:UPDATE `users.pending_email`、INSERT `email_verification_tokens`(token_type=email_change)
- **Email**:驗證信 → **新** email
- **其他副作用**:舊 email 仍可登入(直到 E04)
- **來源**:`auth_users.md §2`

### E04|Email 變更驗證完成(ROUND 8)

- **觸發者**:客戶點新 email 收到的驗證信
- **狀態變更(同一 transaction)**
  - `users.email: 舊 → 新`
  - `users.pending_email: 新 → null`
  - **舊 email 立即失效**,後續登入與 JWT 驗證皆以新 email 為準
- **不觸發**:new_user 歡迎券(只有 signup 會觸發)
- **來源**:`auth_users.md §6`、ROUND 8

### E05|密碼重設申請

- **觸發者**:客戶於忘記密碼頁輸入 email
- **DB 寫入**:舊 password_reset_tokens 全部標記已用 + INSERT 新 token(expires_at=now+1h)
- **Email**:重設信 → 該用戶
- **來源**:`auth_users.md §3, §7`

### E06|管理員停用帳號

- **觸發者**:管理員
- **前置**:`operator_id != target_id`
- **狀態變更**:`users.is_active: true → false`
- **影響**:被停用用戶下次 API 請求將回 401
- **來源**:`auth_users.md §2, §8`

---

## 二、客製申請事件(方案 D:先看初稿再付款)

### E07|客戶提交客製申請(ROUND 8 修正)

- **觸發者**:已登入客戶
- **DB 寫入**
  - INSERT `custom_requests`(status=quote_pending, revision_count=0)
  - INSERT `custom_request_messages`(sender_type=admin, message=系統歡迎訊息)
  - custom_photo:上傳照片至 Firebase Storage(**私有**)
  - INSERT `admin_notifications`(type=quote_pending, requires_action=true)
- **Email**:**寄給客戶**,文案「您的客製申請已收到,預計 X 個工作天內回覆報價」(X 從 `system_settings.quote_reply_days` 讀)
- **SSE 推播**:推播給活躍管理員
- **管理員通知判斷**:完全不在後台 → 另寄 email 通知 Gmail
- **來源**:ROUND 8

### E08|管理員手動標記為「洽談中」(ROUND 8 改為備用)

- **觸發者**:管理員
- **狀態變更**:`custom_requests.status: quote_pending → negotiating`
- **註**:大多數情況會在 E26(帶入照片跑 production_job)時**自動**觸發;E08 僅作為**備用**
- **來源**:ROUND 8

### E09|管理員於對話傳訊息給客戶

- **觸發者**:管理員
- **DB 寫入**:INSERT `custom_request_messages`(sender_type=admin)
- **通知客戶(兩層)**
  - 在對話頁 → SSE 推播,不發 email
  - 不在對話頁 → 發 email 通知
- **來源**:`admin_orders.md §5.8, §5.10`

### E10|客戶於對話傳訊息給管理員(ROUND 8 三層)

- **觸發者**:客戶
- **DB 寫入**:INSERT `custom_request_messages`(sender_type=customer)
- **通知管理員(三層)**
  - 在對話頁 → SSE 推播,無 admin_notification,無 email
  - 在後台但不在對話頁 → INSERT admin_notifications(type=new_message)+ SSE 推播角標,無 email
  - 完全不在後台 → INSERT admin_notifications + SSE 推播 + 寄 email 通知 Gmail
- **來源**:ROUND 8

### E11|管理員送出報價(ROUND 2 + ROUND 8 大修)

- **觸發者**:管理員
- **前置**:
  - production_job 已 approved、num_colors_used 已知
  - 管理員已檢視系統**建議報價**(公式 × 客製服務費率 2.0),可能手動調整
  - **客戶看到的 quoted_price 為管理員最終確認的金額,不是系統自動算的**
- **狀態變更**:`custom_requests.status: quote_pending / negotiating / draft_revision → quote_sent`
- **DB 寫入**
  - UPDATE `custom_requests`(quoted_price, quoted_at, quote_token, quote_expires_at=now+1day)
  - INSERT `custom_request_messages`(sender_type=admin)
- **Email**:寄給客戶,含 filled_template.png **初稿預覽圖** + 報價金額 + 確認連結 `/custom/quote/:token`(Token 為認證憑證,不需登入)
- **來源**:ROUND 2、ROUND 8

### E11-B|客戶要求修改初稿(ROUND 2 新增)

- **觸發者**:客戶於 `/custom/quote/:token` 或會員中心報價頁點「要求修改」
- **前置**:`custom_requests.revision_count < 3`
- **狀態變更**:`custom_requests.status: quote_sent → draft_revision`
- **DB 寫入**
  - UPDATE `custom_requests`(revision_count += 1)
  - INSERT `custom_request_messages`(sender_type=customer,填寫修改說明)
- **admin_notifications**:INSERT(type=draft_revision_requested, requires_action=true)
- **SSE 推播**:推播給活躍管理員
- **Email**:管理員(三層判斷)
- **UI**:revision_count >= 3 時「要求修改」按鈕隱藏
- **來源**:ROUND 2

### E12|報價逾期(Celery Beat)

- **觸發者**:Celery Beat,每 5 分鐘
- **掃描條件**:`custom_requests.status = quote_sent` AND `quote_expires_at < now()`
- **狀態變更**:`custom_requests.status: quote_sent → quote_expired`
- **Email**:客戶(申請自動取消)
- **來源**:`admin_orders.md §5.2`

### E13|客戶延長考慮時間

- **觸發者**:客戶
- **前置**:`is_extended = false`
- **狀態變更**:quote_expires_at +1 day,is_extended = true
- **Email**:管理員(三層判斷)
- **來源**:`admin_product.md §3.9`

### E14|客戶確認報價

- **觸發者**:客戶
- **狀態變更**:`custom_requests.status: quote_sent → quote_confirmed`
- **DB 寫入**
  - UPDATE `custom_requests.order_id`
  - 建立訂單(見 E15)
- **admin_notifications**:INSERT(type=quote_confirmed, requires_action=false)
- **SSE 推播**:推播給活躍管理員
- **Email**:管理員(三層判斷;文案「客製訂單已確認,客戶將付款」)
- **來源**:`admin_orders.md §5.1`

### E15|從客製申請建立訂單(連動 E14)

- **觸發者**:E14 內部連動(同一 transaction)
- **DB 寫入**
  - INSERT `orders`(status=pending_payment, payment_deadline=now+24h)
  - INSERT `order_items`(fulfilled_qty=0, preorder_qty=1, custom_request_id=關聯申請.id, **production_job_id=從 custom_request 反查已 approved 的 job 直接寫入**)
  - 更新 `custom_requests.order_id`
- **庫存扣減**:不扣減實體色(客製訂單在備料時才扣)
- **Email**:客戶(訂單建立 + 付款帳號 + 24h 期限)
- **來源**:ROUND 2

### E16|客戶拒絕報價

- **觸發者**:客戶
- **狀態變更**:`custom_requests.status: quote_sent → quote_rejected`
- **admin_notifications**:INSERT(type=quote_rejected, requires_action=false)
- **SSE 推播**:推播給活躍管理員
- **Email**:無
- **來源**:`admin_notifications.md`

### E17|客戶基於被拒申請重新發起

- **觸發者**:客戶於申請列表點「重新申請」
- **DB 寫入**:INSERT 新 `custom_requests`(status=quote_pending, parent_request_id=原申請.id, revision_count=0)
- **後續**:等同 E07
- **來源**:`admin_orders.md §5.10`

### E18|客戶更換客製照片(ROUND 8 限縮)

- **觸發者**:客戶
- **前置**:`custom_requests.status = quote_pending`(其他狀態拒絕,回 409)
- **狀態變更**:`custom_requests.photo_url` 覆蓋
- **其他副作用**:舊照片**立即**從 Firebase Storage 刪除
- **設計理由**:negotiating 後管理員已開始製作,照片鎖定
- **來源**:ROUND 8

### E18-B|客戶修改申請內容(ROUND 8 新增)

- **觸發者**:客戶
- **前置**:`custom_requests.status = quote_pending`
- **可修改欄位**:canvas_w_cm / canvas_h_cm / difficulty / customer_notes
- **DB 寫入**:UPDATE `custom_requests`
- **來源**:ROUND 8

---

## 三、訂單與付款事件

### E19|客戶結帳送出訂單(目錄商品)

- **觸發者**:已登入客戶
- **前置檢查**:購物車所有 variant `is_active = true`;庫存計算決定 fulfilled / preorder
- **DB 寫入**
  - INSERT `orders`(status=pending_payment, payment_deadline=now+24h)
  - INSERT `order_items`(fulfilled_qty / preorder_qty 拆單)
  - DELETE 對應的 `cart_items`
  - **庫存扣減**(SELECT FOR UPDATE):`physical_colors.stock_ml -= required_ml`
  - 若使用優惠券:UPDATE `user_coupons`(is_used=true, used_in_order_id)
  - 若使用 public_code:UPDATE `promo_codes.total_used += 1` + INSERT `user_coupons`(is_used=true 即時,永久保留)
- **Email**:客戶(訂單明細 + 付款帳號 + 24h 期限)
- **來源**:`admin_orders.md §5.1`、`admin_color.md §2.8`、`admin_discount.md §4.4`

### E20|客戶填寫付款核對表單(ROUND 8)

- **觸發者**:客戶於「未付款」訂單詳情
- **DB 寫入**:INSERT `payment_submissions`
- **admin_notifications**
  - 第一次:INSERT(type=payment_submitted)
  - 管理員曾 flag:INSERT(type=payment_resubmitted)+ 舊 payment_submitted 自動標 completed
- **SSE 推播**:推播給活躍管理員
- **Email**:管理員(**完全不在後台才寄**,三層邏輯)
- **來源**:ROUND 8

### E21|管理員確認付款(ROUND 8 修正文案)

- **觸發者**:管理員
- **狀態變更**:`orders.status: pending_payment → paid`,`orders.paid_at = now()`
- **DB 寫入**
  - UPDATE `orders`
  - 為每筆 order_item 建立 `production_progress`(status=pending)
- **客製訂單額外**:INSERT `admin_notifications`(type=custom_order_paid,文案「客製訂單已付款,請進入備貨流程」)
- **Email**:客戶,文案「**付款已確認,我們將盡快為您製作與出貨**」(不寫預估交期)
- **其他**:關閉 payment_submitted 通知(標 completed)
- **來源**:ROUND 2、ROUND 8

### E22|管理員標記付款資訊有誤(ROUND 3)

- **觸發者**:管理員
- **DB 寫入**
  - UPDATE 最新 `payment_submissions.is_flagged = true`
  - **重設** `orders.payment_deadline = MIN(now() + 24h, orders.created_at + 48h)`(絕對上限 48h)
  - 關閉對應 payment_submitted 通知(標 completed)
- **Email**:客戶(說明哪裡有誤)
  - 剩餘 < 6h → 標題改為「**緊急:還剩 X 小時重新填寫**」,內文加紅字警示
- **來源**:ROUND 3

### E23|付款逾期(Celery Beat)

- **觸發者**:Celery Beat,每 5 分鐘
- **掃描條件**:`orders.status = pending_payment` AND `payment_deadline < now()`
- **狀態變更**:`orders.status → payment_expired`
- **DB 寫入**
  - UPDATE `orders`(cancel_reason_code=payment_expired)
  - 回補庫存:`stock_ml += required_ml × fulfilled_qty`
  - 回補優惠券:`user_coupons.is_used=false`(若使用過)
  - public_code 退款:`promo_codes.total_used -= 1`
  - 未使用回饋券(source_order_id=此訂單)失效:`expires_at = now()`
- **Email**:客戶(訂單已取消)
- **來源**:`admin_orders.md §5.2`、`admin_color.md §2.8`、`admin_discount.md §4.8`

### E24|客戶主動取消訂單(ROUND 8)

- **觸發者**:客戶
- **前置**:`orders.status = pending_payment`
- **狀態變更**:`orders.status → cancelled, cancel_reason_code=customer_cancelled`
- **DB 寫入**:同 E23 的庫存/優惠券回補
- **admin_notifications**:INSERT(type=order_cancelled, requires_action=false)
- **SSE 推播**:推播給活躍管理員
- **Email**:**無**(客戶自行點取消)
- **來源**:ROUND 8

### E25|管理員取消訂單(ROUND 8)

- **觸發者**:管理員
- **限制**:paid 後不可直接改為 cancelled
- **狀態變更**:`orders.status → cancelled, cancel_reason_code=admin_cancelled, cancel_reason_note=具體原因`
- **庫存/優惠券回補**:同 E23
- **Email**:客戶(取消原因 + 聯絡客服說明)
- **來源**:ROUND 8

---

## 四、製作與生產事件

### E26|管理員送出 PBN 製作任務(ROUND 8 自動狀態連動)

- **觸發者**:管理員
- **DB 寫入**
  - INSERT `production_jobs`(status=pending, approved=false, batch_id=批次共用)
  - 批次中每組參數建一筆
  - 若來源客製申請:`custom_request_id` 非 null
  - **自動狀態連動**:若 custom_request.status = quote_pending:
    - UPDATE custom_requests.status → negotiating
    - 對應 admin_notifications(type=quote_pending, reference_id=custom_request.id)標為 completed
- **Celery**:依 batch_id 依序排入佇列,不並發
- **來源**:ROUND 8

### E27|Celery 任務開始處理

- **觸發者**:Celery Worker
- **狀態變更**:`production_jobs.status: pending → processing`
- **遮罩鎖定**:此時起 sam_points、polygons、mask_url 不得編輯
- **來源**:ROUND 6

### E28|Celery 任務完成

- **觸發者**:Worker
- **狀態變更**:`production_jobs.status: processing → completed`
- **DB 寫入**
  - UPDATE `production_jobs`(svg_url, filled_template_url, snapped_rgb_url, palette_json, num_colors_used)
  - Firebase Storage 寫入檔案
- **approved**:仍為 false
- **來源**:`admin_production.md §1.8`

### E28-B|批次全部處理完畢(ROUND 8 新增)

- **觸發者**:Celery 監控任務
- **觸發條件**:某 batch_id 的所有 production_jobs 均為 completed 或 failed
- **DB 寫入**:INSERT admin_notifications(type=batch_completed, message=「批次 #XXX 已完成,N 筆成功、M 筆失敗,請前往審核」)
- **SSE 推播**:推播給活躍管理員
- **Email**:管理員(三層判斷 — 完全不在後台才寄)
- **來源**:ROUND 8

### E29|Celery 任務失敗(ROUND 6)

- **觸發者**:Worker 觸發 on_failure 回呼
- **狀態變更**:`production_jobs.status → failed`
- **DB 寫入**
  - 同批次中尚未執行的 job 全部設為 cancelled
  - INSERT `admin_notifications`(type=production_failed)
- **Firebase Storage 清理**:刪除任務期間已上傳的中間檔案
- **SSE 推播**:推播給活躍管理員
- **客戶通知**:**完全不通知客戶**(不寄 email、不在 messages 插訊息)
- **來源**:ROUND 6

### E30|管理員審核通過製作結果

- **觸發者**:管理員於製作結果頁點「確認儲存」
- **狀態變更**:`production_jobs.approved: false → true`, `approved_at = now()`
- **後續**:
  - 目錄商品:可進入商品管理選為 variant
  - 客製申請(方案 D):管理員進入報價流程(E11)
- **來源**:`admin_production.md §1.8`

### E31|管理員進行後處理

- **觸發者**:管理員
- **狀態變更**
  - 格子合併 / 消邊界:`approved: true → false`(需重新審核)
- **DB 寫入**:UPDATE `production_jobs.palette_json`、DELETE `palette_color_mappings`、Firebase 覆寫
- **來源**:`admin_production.md §1.6`

### E32|管理員完成顏色對應

- **觸發者**:管理員在顏色工作台點「完成對應」
- **DB 寫入**:UPSERT `palette_color_mappings`,計算並寫入 `required_ml`
- **來源**:`admin_color.md §2.7, §2.8`

### E32-D|管理員硬刪除製作任務（ROUND ‑ 2026-05-02 補）

- **觸發者**:管理員於任務詳情頁點「刪除任務」（2-click 確認）
- **拒絕條件**:
  - `production_jobs.status = processing`（worker 寫入中，回 400）
  - 被 `product_variants` / `print_batches` / `order_items` 任一引用（回 400 含具體計數）
- **DB 寫入**（單一 transaction）:
  - DELETE `palette_color_mappings` WHERE `production_job_id = X`（schema 無 ondelete CASCADE，手動刪子資料）
  - DELETE `production_jobs` WHERE `id = X`
- **Firebase Storage 清理**（commit 後 best-effort）:
  - 逐一刪 `svg_url` / `filled_template_url` / `snapped_rgb_url` / `mask_url` 對應 blob
  - 任一失敗只 log warning，不回滾 DB（DB 已 commit）
- **SSE 推播 / Email**:無（純管理員自行清理，不通知客戶）
- **來源**:`admin_production.md §1.10`

---

## 五、庫存與備料事件

### E33|管理員進貨(ROUND 6 統一 ml 單位)

- **觸發者**:管理員
- **狀態變更**:`physical_colors.stock_ml += 輸入量`(單位 ml,管理員自行換算)
- **自動掃描預購**(見 E34)
- **來源**:ROUND 6

### E34|進貨觸發預購自動備貨(ROUND 8 修文案)

- **掃描條件**:所有 `order_items.preorder_qty > 0` 且訂單非 completed/cancelled,依 created_at 排序
- **每筆判斷**:
  - 若夠備:`stock_ml -= required_ml × preorder_qty`,`fulfilled_qty += preorder_qty, preorder_qty = 0`,推進 production_progress
  - Email 通知客戶「**您預購的商品已備齊,即將出貨**」
- **仍不足**:INSERT `admin_notifications`(type=stock_shortage)
  - **去重**(ROUND 6):同 physical_color 已有 unhandled/in_progress 通知 → 不產生新的,僅 UPDATE updated_at
- **來源**:ROUND 6、ROUND 8

### E35|生產進度推進(ROUND 8 前端合併)

- **觸發者**:管理員
- **狀態變更**:`production_progress.status` 推進一階
- **Email(依推進到的 status)**
  - `in_production` → 發
  - `manufacturing` → 發
  - `packaging` → 不發
  - `ready_to_ship` → 發
  - `shipped` → 發(含追蹤號,由 E36 連動)
- **客戶端顯示**:manufacturing 與 packaging 統一顯示「**備貨中**」(後端狀態機不動)
- **來源**:ROUND 8

---

## 六、出貨與物流事件

### E36|管理員點「出貨」(ROUND 1 動作導向)

- **觸發者**:管理員於訂單詳情
- **DB 寫入**
  - 呼叫 ECpay API → tracking_number + ecpay_logistics_id
  - UPDATE `shipments`(status=shipped, tracking_number, shipped_at=now())
  - 自動推進該訂單所有 production_progress 到 shipped
- **orders.status 聚合連動**:
  - 訂單至少一筆 shipments.status ∈ {shipped, delivered} → orders.status = shipped(若原本為 processing)
  - 分開出貨第一次點出貨:orders.status 從 processing → shipped
  - 後續出貨:orders.status 已是 shipped,不變
- **Email**:客戶(出貨通知 + 追蹤號碼)
- **失敗**:ECpay API 失敗 → raise `ExternalServiceError`,訂單不變,可重試
- **來源**:ROUND 1

### E37|ECpay Webhook 回報物流狀態

- **觸發者**:ECpay 伺服器
- **驗證**:CheckMacValue(驗證失敗回 400)
- **分流**:
  - 中間狀態(派送中)→ INSERT `admin_notifications`(type=ecpay_status)
  - 已取貨/已投遞 → UPDATE `shipments.status=delivered, delivered_at=now()`
    - 檢查訂單所有 shipments:全部 delivered → UPDATE `orders.status: shipped → completed`,連動 E40
- **Email**:completed 時發客戶(完成通知)
- **來源**:ROUND 1

### E38|客戶主動點「確認收貨」(ROUND 8)

- **觸發者**:客戶
- **前置**:`orders.status = shipped`
- **動作**
  - 所有尚未 delivered 的 shipments.status 設為 delivered
  - orders.status → completed,completed_at = now()
  - 連動 E40
- **admin_notifications**:INSERT(type=order_completed_by_customer, requires_action=false)
- **SSE 推播**:推播給活躍管理員
- **Email**:無
- **來源**:ROUND 8

### E39|送達 5 天無取貨(ROUND 8 大修)

- **觸發者**:Celery Beat,每日一次
- **掃描條件**(從「出貨後 14 天」改為「送達後 5 天」):
  - `shipments.status = delivered` AND `shipments.delivered_at < now() - 5 days`
  - AND 對應訂單 `orders.status != completed`
- **狀態變更**:**不自動改變訂單狀態**
- **DB 寫入**:INSERT admin_notifications(type=shipment_overdue, requires_action=true)
- **Email**
  - 管理員(提醒確認物流)
  - **客戶(僅寄一次)**,文案「商品已送達 5 天,若已收到請點『確認收貨』完成訂單」
- **去重**:同訂單已有 shipment_overdue 通知 → 不再產生,也不再寄客戶 email
- **來源**:ROUND 8

### E40|訂單完成的連動事件(由 E37 或 E38 觸發)

- **自動觸發回饋券(ROUND 6 偽碼)**
  ```
  if (用戶除此筆外有其他 completed 訂單) 
     AND (returning_loyal.is_active)
     AND (order.total >= returning_loyal.trigger_threshold):
      發 returning_loyal(source_order_id = 此訂單)
  elif (spend_reward.is_active)
       AND (order.total >= spend_reward.trigger_threshold):
      發 spend_reward(source_order_id = 此訂單)
  else:
      不發
  ```
- **Email**:已於 E37/E38 發訂單完成通知;若發券另發券通知
- **來源**:ROUND 6

---

## 七、退款事件(ROUND 4 + ROUND 8 雙重確認)

### E41|管理員標記退款處理中(ROUND 8)

- **觸發者**:管理員
- **狀態變更**:`orders.status → refund_processing, admin_notes=退款原因`
- **庫存/優惠券**:不回補(等 refunded 才動)
- **Email**:**寄給客戶**,文案「您的退款申請已受理,我們將盡快為您處理」
- **來源**:ROUND 8

### E42|管理員標記退款完成(ROUND 4 + ROUND 8)

- **觸發者**:管理員於退款明細介面勾選退回項目、填 refund_amount、按確認
- **狀態變更(依勾選結果)**:
  - 勾選**全部 items** → `orders.status: refund_processing → refunded`
  - 勾選**部分 items** → `orders.status: refund_processing → partially_refunded`
  - UPDATE `orders.refund_amount`、`refunded_at = now()`
  - **`refund_confirmed_at` 保持 null**(等客戶確認)
- **DB 寫入**
  - 勾選的 `order_items.is_returned = true`
  - **庫存回補**:對勾選項回補 `fulfilled_qty × required_ml`
  - **優惠券處理**:
    - 全額:`user_coupons.is_used=false`;public_code 的 `promo_codes.total_used -= 1`
    - 部分:維持不回補
  - **回饋券撤銷**(source_order_id = 此訂單):
    - 全額:未使用者 `expires_at = now()`
    - 部分:`remaining = order.total - refund_amount`;若 < trigger_threshold 則同全額;若 ≥ 則不處理
- **Email**:**客戶(退款金額 + 退回明細 + 「確認已收到退款」連結)**
- **來源**:ROUND 4、ROUND 8

### E42-B|客戶確認已收到退款(ROUND 8 新增)

- **觸發者**:客戶於訂單詳情頁或 email 連結點「確認已收到退款」
- **前置**:`orders.status ∈ {refunded, partially_refunded}` AND `refund_confirmed_at IS NULL`
- **狀態變更**:`orders.refund_confirmed_at: null → now()`
- **不改變**:`orders.status`、庫存、優惠券(E42 時已全部處理)
- **Email / admin_notification**:無
- **設計理由**:雙重確認機制保障雙方 — 客戶有主動確認管道,管理員有書面紀錄
- **來源**:ROUND 8

---

## 八、折扣券事件

### E43|管理員手動發券(manual 類型)

- **觸發者**:管理員
- **DB 寫入**:INSERT `user_coupons`(coupon_config_id=manual 設定, source_order_id=null)
- **Email**:後台發券時有勾選「是否通知客戶」的彈性選項
- **來源**:ROUND 6

### E44|結帳套用折扣

- **觸發者**:客戶結帳
- **決策優先序**
  1. 客戶輸入 public_code → 嘗試驗證 → 套用 public_code
  2. 客戶選擇持有券 → 套用該券
  3. 無券 → 查符合條件的 auto_checkout,取折扣金額最高者
- **DB 寫入**
  - public_code:INSERT `user_coupons`(is_used=true 即時,永久保留);UPDATE `promo_codes.total_used += 1`
  - 持有券:UPDATE `user_coupons`(is_used=true, used_in_order_id)
  - auto_checkout:UPDATE `orders.discount_source=auto_checkout`
- **UPDATE orders**:discount_amount, discount_source
- **來源**:`admin_discount.md §4.4`

---

## 九、Celery Beat 定時任務總表

| 任務 | 頻率 | 觸發事件 |
|---|---|---|
| 付款逾期掃描 | 每 5 分鐘 | E23 |
| 報價逾期掃描 | 每 5 分鐘 | E12 |
| 送達 5 天無確認提醒 | 每日 1 次 | E39 |

---

## 十、外部服務失敗回退邏輯

| 服務 | 失敗時 | 主流程影響 |
|---|---|---|
| ECpay(建立物流) | raise `ExternalServiceError`(503) | 訂單狀態不變,可重試 |
| ECpay Webhook 驗證失敗 | 回 400 | 不更新狀態 |
| Firebase Storage(上傳) | raise `ExternalServiceError`,Celery on_failure 清理 | production_job → failed;批次其餘 job → cancelled |
| Resend(Email) | **不 raise**,寫 warning log | **主流程繼續**(寄信失敗不影響訂單/狀態) |
| SAM 模型(懶載入) | 首次 5~10 秒冷啟動 | 正常完成,只是慢 |

來源:`backend_conventions.md §5.3`

---

## 十一、SSE 推播觸發總表

| 觸發事件 | 推播目標 | 內容 |
|---|---|---|
| 新 `admin_notifications` 建立 | 所有活躍管理員 | 通知角標 + 新通知項目 |
| 客戶傳訊息 | 當前在對話頁的管理員 | 訊息內容 |
| 管理員傳訊息 | 當前在對話頁的客戶 | 訊息內容 |
| Heartbeat | 所有活躍連線 | `: heartbeat\n\n`(每 30 秒) |

---

## 十二、通知矩陣簡表

| 事件代號 | 客戶 Email | 管理員 Email | admin_notification | SSE |
|---|---|---|---|---|
| E01 註冊 | ✓(驗證信) | | | |
| E02 驗證完成 | | | | |
| E03 改 email | ✓(新信箱) | | | |
| E05 忘記密碼 | ✓(重設信) | | | |
| E07 提交客製 | ✓(收到確認) | ✓*(不在後台) | ✓ quote_pending | ✓ |
| E09 管理員傳訊息 | ✓*(不在對話頁) | | | ✓(在對話頁) |
| E10 客戶傳訊息 | | ✓*(完全不在後台) | ✓*(不在對話頁) | ✓ |
| E11 送出報價 | ✓ | | | |
| E11-B 要求修改 | | ✓*(不在後台) | ✓ | ✓ |
| E12 報價逾期 | ✓ | | | |
| E13 延長報價 | | ✓*(不在後台) | | |
| E14 確認報價 | | ✓*(不在後台) | ✓ quote_confirmed | ✓ |
| E16 拒絕報價 | | | ✓ quote_rejected | ✓ |
| E19 結帳 | ✓ | | | |
| E20 付款表單 | | ✓*(完全不在後台) | ✓ payment_submitted/resubmitted | ✓ |
| E21 確認付款 | ✓ | | ✓(客製 custom_order_paid) | ✓ |
| E22 標記付款有誤 | ✓(剩餘<6h 緊急) | | | |
| E23 付款逾期 | ✓ | | | |
| E24 客戶取消 | ✗ | | ✓ order_cancelled | ✓ |
| E25 管理員取消 | ✓(原因+客服) | | | |
| E28-B 批次完成 | | ✓*(完全不在後台) | ✓ batch_completed | ✓ |
| E29 製作失敗 | | | ✓ production_failed | ✓ |
| E34 預購備貨 | ✓(備齊) | | | |
| E35 生產進度 | ✓*(部分狀態) | | | |
| E36 出貨 | ✓ | | | |
| E37 物流 delivered | ✓*(completed 時) | | ✓ ecpay_status(中間) | |
| E38 客戶確認收貨 | | | ✓ order_completed_by_customer | ✓ |
| E39 送達 5 天提醒 | ✓(僅一次) | ✓ | ✓ shipment_overdue | ✓ |
| E41 退款受理 | ✓ | | | |
| E42 退款完成 | ✓(含確認連結) | | | |
| E42-B 客戶確認收到 | | | | |

`*` 表有條件(如不在對話頁、不在後台等)

---

**版本**:v1.0(含 ROUND 1~8 全部決議)
**最後更新**:2026-04
**權威來源**:各 md 模組規格(schema.md、admin_orders.md 等)為權威;本表為交叉索引
