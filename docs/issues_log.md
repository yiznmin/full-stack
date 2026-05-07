# 線上問題與解決紀錄

> 開發 / 上線過程踩到的所有 bug、現象、根因、解法。寫進這份檔的原則：
> - **不寫已解決且不會 regress 的瑣事**（typo、命名）
> - **寫所有「跨層級／隱藏關聯／文件不寫的行為」相關 bug**
> - 每筆按時間倒序，編號累積遞增（不重編）

---

## 索引

| # | 日期 | 模組 | 嚴重度 | 標題 |
|---|---|---|---|---|
| [001](#001) | 2026-05-07 | logistics | 🔴 阻塞 | ECpay CVS Map 「找不到加密金鑰」沙箱 2000132 不開 C2C |
| [002](#002) | 2026-05-07 | logistics | 🔴 阻塞 | CVS Map callback 沒送 CheckMacValue（與文件不符） |
| [003](#003) | 2026-05-07 | logistics | 🟡 嚴重 | Railway proxy 讓 ServerReplyURL 變 http 而非 https |
| [004](#004) | 2026-05-07 | orders | 🔴 阻塞 | 用戶端訂單狀態「跳回待付款」(實際是 stepper 對映 bug) |
| [005](#005) | 2026-05-07 | logistics | 🔴 阻塞 | create_shipment ImportError → 500「伺服器內部錯誤」 |
| [006](#006) | 2026-05-07 | orders | 🟢 顯示瑕疵 | 已出貨訂單顯示「⚠ 未確認」橘標誤導 |

---

<a id="001"></a>
## #001 ECpay CVS Map 「找不到加密金鑰」— 沙箱 2000132 沒開 C2C

**日期**：2026-05-07
**模組**：`backend/logistics/`
**現象**：用戶在結帳頁點「選擇門市」，跳出視窗顯示 `找不到加密金鑰，請確認是否有申請開通此物流方式!`

**錯誤訊息誤導**：訊息字面上看是「金鑰錯」，實際是「該 SubType 沒在你帳號開通」。ECpay 把兩種錯混合在同一個錯誤訊息裡。

**診斷流程**：
1. 用 curl 直接 POST 到 ECpay `/Express/map`（跳過所有前端層）
2. 用沙箱公開組 `2000132 / 5294y06JbISpM5x9 / v77hoKGq4kWxNNIS` + 各 SubType 各試一次
3. 結果：所有 C2C SubType（UNIMARTC2C, FAMIC2C, HILIFEC2C, OKMARTC2C）都報「找不到加密金鑰」
4. 但 B2C SubType（UNIMART, FAMI）正常回地圖 redirect HTML
5. 確認簽章演算法正確（B2C 通了）

**根因**：ECpay 沙箱帳號 `2000132` 只開通 B2C 物流，**未開通任何 C2C**。文件沒寫這個限制。

**解法**：
- 短期：picker 改用 B2C SubType (UNIMART/FAMI)
- 後來 user 申請了真正的 C2C → picker 改回 UNIMARTC2C/FAMIC2C
- 加 `/api/v1/logistics/probe-subtypes` 診斷端點，自動探測哪些 SubType 開通

**教訓**：
- ECpay 錯誤訊息字面意義跟實際根因常不一致
- 直接 curl 測 ECpay 比走前端 debug 快 10 倍
- 沙箱限制要實測，不能信文件

---

<a id="002"></a>
## #002 CVS Map callback 沒送 CheckMacValue（與 ECpay 文件不符）

**日期**：2026-05-07
**模組**：`backend/logistics/router.py:cvs_map_callback`
**現象**：用戶在 ECpay 地圖選店成功後，前端顯示「選店失敗或簽章驗證未通過，請再試一次」

**Railway log**：
```
[ecpay-callback] received params: {'MerchantID': '3497730', 'MerchantTradeNo': '...',
  'CVSStoreID': '237024', 'CVSStoreName': '新加昌門市', 'CVSAddress': '高雄市...',
  'CVSTelephone': '', 'CVSOutSide': '0', 'ExtraData': ''}
[ecpay-callback] MAC mismatch: received= expected=FB298C84A4157C0B34D94DB083B56C81
```

注意 `received=` 是空。

**根因**：ECpay 文件 [/8795/](https://developers.ecpay.com.tw/8795/) Response 表格列了 CheckMacValue 欄位，**但 CVS Map 實際 POST 回 callback 不附這欄位**。文件描述與實際行為不符。

**解法**：
- callback 改成「MAC 缺失 → 接受（log 警告）；MAC 存在 → 嚴格驗」
- 安全考量：popup 只能由我們的 cvs-map endpoint 開啟、攻擊面有限；真正寄件動作 (Day 2 /8809/) 會用 store_id 重新跟 ECpay 驗

**教訓**：
- ECpay 文件不可全信，關鍵欄位必須實測
- 加 raw body log 比解析後 dict log 更可靠（避免 parser 吞欄位的誤會）

---

<a id="003"></a>
## #003 Railway 反向代理讓 ServerReplyURL 變 http 而非 https

**日期**：2026-05-07
**模組**：`backend/logistics/router.py` + `backend/scripts/start_web.sh`
**現象**：debug-config 顯示 `computed_callback_url: http://paint-web-production.up.railway.app/...`

ECpay 在 production 強制要求 ServerReplyURL 必須是 https。

**根因**：
- Railway 反向代理層之間是 http
- FastAPI `request.base_url` 沒有採信 `X-Forwarded-Proto` header
- uvicorn 預設不啟用 proxy headers

**解法**：兩層修法
1. `start_web.sh` uvicorn 加 `--proxy-headers --forwarded-allow-ips='*'` (根因)
2. `_resolve_server_reply_url()` 對 `*.railway.app` 強制 https（雙保險）

**教訓**：用反向代理時要明確告訴 ASGI server 採信 forwarded headers，不然各種 URL 推導都會錯。

---

<a id="004"></a>
## #004 用戶端訂單狀態「跳回待付款」— 實際是 stepper 對映 bug + 多個 enum 不一致

**日期**：2026-05-07
**模組**：`store/src/features/orders/`
**現象**：admin 確認付款 + 開始製作 + 印製模板 → 用戶端訂單狀態**顯示「待付款」**而不是「製作中」。

**多重 bug（5 個）**：

1. **store 前端 OrderStatus enum 用過時值**
   - 前端：`pending_payment | paid | in_production | shipping | delivered | completed | cancelled | refunded`
   - backend `OrderStatusEnum`：`pending_payment | payment_expired | paid | processing | shipped | completed | cancelled | refund_processing | refunded | partially_refunded`
   - 結果：`STATUS_LABEL['processing']` = undefined → 顯示空白

2. **OrderDetailPage `PROGRESS_STEPS` findIndex on order.status**
   ```js
   const idx = PROGRESS_STEPS.findIndex((s) => s.key === order.value!.status)
   return idx === -1 ? 0 : idx
   ```
   - 後端 status='processing'，前端 PROGRESS_STEPS 沒這 key
   - findIndex 返回 -1 → fallback 0
   - **stepper 顯示 idx=0 = 待付款** ← 這是「跳回」的真正成因

3. **`update_production_progress` 不會推進 order.status**
   - admin 點「印製模板」只更新 ProductionProgress
   - Order.status 仍卡 `paid`
   - 修法：當 production progress 推進到 manufacturing/packaging/ready_to_ship 且 order.status 是 paid 時，自動推進到 processing

4. **`shipping_type` 型別不對齊**
   - store: `'home' | 'convenience'`
   - backend: `'home' | 'seven_eleven' | 'family_mart'`

5. **`shipping_preference` 值不對齊**
   - store: `'merge' | 'split'`
   - backend: `'together' | 'separate'`（Pydantic Literal 嚴格驗）
   - 結果：預購結帳時 422 fail

**解法**：
- 全面修齊前後端 status enum
- PROGRESS_STEPS 改用 idx-based + STATUS_TO_STEP_IDX 對映表
- 加 backend auto-advance 邏輯
- 修兩個 type 不對齊

**教訓**：
- 前後端 enum 名稱要嚴格對齊，不能各寫各的
- 前端 fallback to idx=0（pending_payment）是危險預設 — 一旦對映不到就會顯示「待付款」誤導用戶
- 每個 enum 改動要前後端一起改 + 對照表（`STATUS_LABEL`、`STATUS_TAB`、`STATUS_TO_STEP_IDX`）

---

<a id="005"></a>
## #005 create_shipment ImportError → 500「伺服器內部錯誤」

**日期**：2026-05-07
**模組**：`backend/logistics/service.py:get_sender_info`
**現象**：admin 點「出貨」按鈕→ 500「伺服器內部錯誤」（前端顯示 generic 錯誤，無具體訊息）

**診斷流程**：
1. 確認 `ECPAY_DRY_RUN=true`、env vars 正確
2. 確認寄件人資訊已在系統設定填好
3. 重現 500：admin 登入→ POST `/admin/orders/{id}/shipments` → 500
4. FastAPI 預設 500 handler 只回 `{"detail": "伺服器內部錯誤"}`，不暴露 traceback
5. 暫時加 debug endpoint `/debug-create-shipment/{id}` 把 traceback 回傳
6. 抓到完整 stack:
   ```
   File "/app/logistics/service.py", line 412, in get_sender_info
     from orders.models import SystemSetting
   ImportError: cannot import name 'SystemSetting' from 'orders.models'
   ```

**根因**：寫 `get_sender_info()` 時用了 `from orders.models import SystemSetting`，但 `SystemSetting` 模型實際定義在 `color/models.py`（跨模組共用該表的歷史包袱）。

**解法**：改成 `from color.models import SystemSetting`。

**教訓**：
- ImportError 在 endpoint 第一次被呼叫時才觸發（lazy import 在 function 裡），unit test 沒 cover 就不會發現
- 寫 `from XX import YY` 前要 `grep -rn "class YY" backend/` 確認 module 路徑
- 500 generic error handler 隱藏太多資訊；長期應該在 dev / staging 環境暴露 traceback，production 才隱藏
- 每次後端改完應該至少打一次該 endpoint 確認可呼叫（smoke test）

---

<a id="006"></a>
## #006 已出貨訂單顯示「⚠ 未確認」橘標誤導

**日期**：2026-05-07
**模組**：`admin/src/features/orders/pages/OrderDetailPage.vue` + `backend/orders/`
**現象**：admin 看已出貨的舊訂單，收件資訊區塊顯示「⚠ 未確認」橘標。User 詢問「是因為已經出貨了對嗎」。

**根因**：`shipping_locked` 是新加的 column，預設 `false`。舊訂單（包括已出貨的）都是 false → badge 顯示「未確認」。但對已出貨訂單來說這個 badge 沒意義 — 出貨已既成事實，再「確認」也改不了。

**解法**：
1. **後端 `create_shipment`**：建單成功時把 `order.shipping_locked = True`（雙保險，前置已檢查）
2. **`init_db.py` backfill SQL**：一次性把已有 Shipment 的舊訂單設為 locked
   ```sql
   UPDATE orders SET shipping_locked = TRUE
   WHERE id IN (SELECT DISTINCT order_id FROM shipments)
   ```
3. **admin UI**：badge 只在 `status in (paid, processing)` 顯示；`shipped` 之後階段隱藏

**教訓**：
- 加新 column 時要想清楚「對舊資料的預設語意是什麼」
- 純 boolean default false 對於已存在的「應該為 true」的記錄會造成 UI 誤導
- backfill SQL 應該跟 column 加入同步部署，不要等到 user 抱怨才補

---

## 模板（新增 issue 時複製此區塊）

```markdown
<a id="00X"></a>
## #00X <一句話標題>

**日期**：YYYY-MM-DD
**模組**：`<file path or feature area>`
**現象**：<user 看到什麼 / 系統呈現什麼>

**診斷流程**：
1. ...
2. ...

**根因**：<technical root cause>

**解法**：<what was changed>

**教訓**：<process / convention / lesson learned>
```
