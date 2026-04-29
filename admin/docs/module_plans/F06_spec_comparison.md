# 規格比對報告 — F06 製作系統（F06-A 範圍）

針對 `F06_production.md` 規劃書，逐項比對 `docs/api.md`、`docs/requirements/admin_production.md`、`docs/EVENT_MATRIX.md`、`docs/requirements/admin_routes.md`，並用 OpenAPI 真實 dump 驗證。

---

## 1. api.md vs OpenAPI 端點實況

| F06-A 規劃用到的 endpoint | api.md / 規格列出 | 後端 OpenAPI 真實有 | 結果 |
|---|---|---|---|
| POST /admin/images | ✓ | ✓ | ✓ |
| POST /upload/production-image | ✓ | ✓ | ✓ |
| GET /admin/production/jobs | ✓ | ✓ | ✓ |
| POST /admin/production/jobs | ✓ | ✓ | ✓ |
| GET /admin/production/jobs/{id} | ✓ | ✓ | ✓ |
| GET /admin/production/jobs/{id}/signed-url | ✓ | ✓ | ✓ |
| POST /admin/production/jobs/{id}/approve | ✓ | ✓ | ✓ |
| POST /admin/production/jobs/{id}/unapprove | ✓ | ✓ | ✓ |
| **GET /admin/production/jobs/{id}/export-pdf** | ✓（spec / api.md）| **❌ 後端沒有** | ⚠️1 |
| **GET /admin/canvas-sizes** | ❓（spec 提及但未明確列）| **❌ 後端沒有** | ⚠️2 |

額外 F06-B 用得到、目前後端都已存在：
- POST /admin/production/jobs/{id}/post-process/{merge-color, eliminate-border, smooth-contour} ✓
- 缺：POST /admin/production/jobs/{id}/sam-mask ⚠️（後端尚未實作）

---

## 2. admin_production.md 業務規則比對（F06-A 範圍）

| 規則 | 來源 | 規劃對應 | 結果 |
|---|---|---|---|
| 上傳 JPG/PNG 透過 Firebase signed URL 直傳 | admin_production.md / api.md | ProductionNewPage 上傳 → /upload/production-image → PUT GCS → POST /admin/images | ✓ |
| 從客製申請帶入照片時，image_id=null + custom_request_id 非 null | admin_production.md + EVENT E26 | source toggle + dropdown | ✓ |
| 自動連動：客製 quote_pending → negotiating | EVENT E26 | 後端做，前端只需 invalidate 客製查詢 | ✓ |
| 批次共用 batch_id；Celery 序列執行不並發 | admin_production.md | 前端不感知，純後端；UI 只在列表顯示同 batch | ✓ |
| 預設組合（細緻 / 難易）影響 blur/prune/num_colors | admin_production.md §細緻度 / §難易度表格 | F06-A 只開 4 enum，後端套預設值 | ✓ |
| 結果頁顯示 filled_template / SVG / palette / num_colors_used | admin_production.md §6 | FilledTemplateCard + SVGPreviewCard + PaletteListCard | ✓ |
| filled_template 公開 / SVG 私有需簽章 | admin_production.md + api.md | filled 直接 `<img>`；SVG 透過 /signed-url?file=svg 取連結餵 `<img>` | ✓ |
| approved 預設 false，須管理員審核 | EVENT E28 | 詳情顯示「待審核」+ 「確認儲存」按鈕 | ✓ |
| approve 後可進入顏色對應或建立 variant | EVENT E30 | 詳情頁顯示 hint「可進入顏色對應」（連結指 F07，本版本停留在 hint）| ✓ |
| 後處理會把 approved 退回 false | EVENT E31 | F06-B 處理 | 延後 |
| SAM 遮罩鎖定（status=processing 後不可改）| admin_production.md §10 | F06-B 處理 | 延後 |
| Celery 失敗自動清理 + 同批次 cancelled | EVENT E29 | 後端做，前端只顯示 status=failed/cancelled | ✓ |
| 批次完成 admin_notification | EVENT E28-B | F09 通知中心統一處理；本模組詳情頁靠 polling 看狀態 | ✓ |
| **PDF 匯出（即時 SVG → Inkscape）** | admin_production.md §6 + api.md | 規劃寫了，但**後端目前沒此 endpoint** | ⚠️1 |

---

## 3. EVENT_MATRIX 副作用比對

| Event | 動作 | 副作用 | 前端責任 | 結果 |
|---|---|---|---|---|
| E26 建立任務 | POST /jobs | INSERT production_jobs（pending）+ 客製狀態自動連動 | 送 request → 跳列表 | ✓ |
| E27 開始處理 | Celery（自動）| status: pending → processing | 詳情 polling 5s | ✓ |
| E28 完成 | Celery（自動）| status: completed + 寫 svg/filled/palette | 詳情 polling 取到結果 | ✓ |
| E28-B 批次完成 | Celery monitor | INSERT admin_notification | F09 處理 | ✓ |
| E29 失敗 | Celery（自動）| status: failed + 同批 cancelled | 詳情顯示錯誤 + 不可 approve | ✓ |
| E30 審核通過 | POST /approve | approved=true, approved_at | mutation → 重 fetch | ✓ |
| E31 後處理 | F06-B | — | 延後 | 延後 |

---

## 4. admin_routes.md 路由比對

| 規定路由 | 規劃對應 | 結果 |
|---|---|---|
| `/admin/production` | ProductionListPage | ✓ |
| `/admin/production/:jobId` | ProductionJobDetailPage | ✓ |
| 〈無明確路由，但需要建立任務頁〉 | `/admin/production/new` → ProductionNewPage | ✓（自加） |

sidebar 既有「製作系統」連到 `/admin/production` — 不需動。

---

## 5. 手動測試覆蓋表

對應 F06_production.md §7，含 16 個 case。

---

## 6. 差異與待確認

### ⚠️1 PDF 匯出 endpoint 後端尚未實作
- admin_production.md §6 與 api.md 模組四都寫了 `/export-pdf` 行為（SVG → Inkscape 轉換、5cm margin）
- OpenAPI 沒有此路徑 → 後端待補
- **選項**：
  - **A.** F06-A 不做「匯出 PDF」按鈕；後端補上後再加（簡單）
  - **B.** F06-A 做但按鈕 disabled + 標「敬請期待」
  - **C.** 我這次同步把後端 endpoint 補上（會超出本模組範圍，跨到 backend production 模組改動）
- **傾向 A** — 不影響核心 happy path

### ⚠️2 canvas-sizes endpoint 後端不存在
- 建立任務需要可選的畫布尺寸
- 規格說從 canvas_sizes 表抓，但後端沒 GET 列表 endpoint
- **選項**：
  - **A.** 前端 hardcode 9 種常用尺寸（20×20 / 30×30 / 30×40 / 30×50 / 40×50 / 40×60 / 50×70 / 60×60 / 60×80），等 F10 內容管理時改成 API
  - **B.** 我同步補後端 GET /admin/canvas-sizes endpoint
- **傾向 A** — 先 hardcode 跑通

### ⚠️3 SAM 與後處理是否本次完全不做
- 規劃書 §0 已切分 F06-A / F06-B
- F06-A 用 mode=standard 已能涵蓋多數場景
- **問**：同意切分？

### ⚠️4 從客製申請 dropdown 的候選範圍
- 規劃寫「status ∈ {quote_pending, negotiating, draft_revision} 才列入候選」
- 但 quote_sent / quote_confirmed 的客製可能也想再跑一次（重新製作）— 是否要全部 7 狀態都列、只 disabled 已 confirmed 的？
- **傾向**：只列「未送過報價」的（quote_pending + negotiating + draft_revision），其他用列表分流 — 簡單明瞭
- **問**：同意？

### 結論

- ⚠️1 → A（不做 PDF，後端補上後再加）
- ⚠️2 → A（hardcode 9 種尺寸）
- ⚠️3 → 切分 F06-A / F06-B
- ⚠️4 → 只列 3 種狀態

**有 ⚠️1、⚠️2、⚠️3、⚠️4 共 4 項待你拍板。我的傾向 = 全 A**。同意「全 A」就告訴我，直接開工 F06-A。
