# F06 製作系統 模組規劃書

> 對應後端 Module 04 (production) + Module 04b (upload)、admin_routes 製作系統區、admin_production.md。
> 規格來源見章節末「規格定位」。本規劃書遵循 `admin/docs/frontend_sop.md`。

---

## 0. 範圍切分（重要）

F06 是 admin 端最大的模組（10+ endpoints、SAM 遮罩繪製、後處理工具、PDF 匯出、批次組合）。一次寫到位風險過高，**本規劃書切兩階段**：

### F06-A（本次目標 — 先讓「核心 90% 場景」可用）
- **建立任務頁** — 上傳圖片 / 從客製申請挑、選預設參數組合（粗 / 標準 / 細緻 / 高級 × 入門 / 初級 / 中級 / 進階）、批次組合表、`mode = standard`（不含 SAM）
- **任務列表** — 分頁、狀態 / batch_id / approved 篩選
- **結果頁** — filled_template 預覽、SVG 簽章下載、調色盤列表、num_colors_used、approve / unapprove、PDF 匯出
- **不做**：SAM 遮罩繪製（sam_refine / sam_weighted）、合併色塊 / 消邊界 / 輪廓平滑 後處理工具
- 呼叫客製 PATH (custom_request_id) 走得通，但建立 job 後不主動跳到 F05 報價頁

### F06-B（後續迭代）
- SAM 遮罩繪製工具（含 polygon 繪圖、sam_points 標記、re-build mask）
- 後處理工具（合併色塊 / 消邊界 / 輪廓平滑） — 需要 click-to-pick 互動 + canvas 操作
- 進階參數覆蓋面板（blur/prune/min_ratio_multiplier 等手動調參）

---

## 1. 路由清單

| 路由 | 頁面元件 | guard | 說明 |
|---|---|---|---|
| `/admin/production` | `ProductionListPage.vue` | requireAdmin | 任務列表 + 篩選 |
| `/admin/production/new` | `ProductionNewPage.vue` | requireAdmin | 建立任務（上傳 + 參數 + 批次） |
| `/admin/production/:jobId` | `ProductionJobDetailPage.vue` | requireAdmin | 結果頁（預覽 / approve / PDF）|

sidebar 已有「製作系統」入口 → `/admin/production`。

---

## 2. 後端 API 對應表

| Endpoint | Method | F06-A | F06-B | 用途 |
|---|---|---|---|---|
| /admin/images | POST | ✓ | | 上傳原圖 metadata（搭配 /upload/production-image 拿 signed URL）|
| /upload/production-image | POST | ✓ | | 拿 Firebase signed URL（前端直傳）|
| /admin/production/jobs | GET | ✓ | | 列表 |
| /admin/production/jobs | POST | ✓ | | 建立任務（單筆或批次）|
| /admin/production/jobs/{id} | GET | ✓ | | 詳情 |
| /admin/production/jobs/{id}/signed-url | GET | ✓ | | 拿 SVG / snapped_rgb 簽章 URL |
| /admin/production/jobs/{id}/approve | POST | ✓ | | 確認儲存 |
| /admin/production/jobs/{id}/unapprove | POST | ✓ | | 撤銷審核 |
| /admin/production/jobs/{id}/export-pdf | GET | ✓ | | 即時產出 PDF |
| /admin/production/jobs/{id}/sam-mask | POST | | ✓ | 編輯 SAM 遮罩 |
| /admin/production/jobs/{id}/post-process/merge-color | POST | | ✓ | 合併色塊 |
| /admin/production/jobs/{id}/post-process/eliminate-border | POST | | ✓ | 消邊界 |
| /admin/production/jobs/{id}/post-process/smooth-contour | POST | | ✓ | 輪廓平滑 |
| /admin/canvas-sizes | GET | ✓ | | 拉可選畫布尺寸（系統推薦用）|

---

## 3. 元件樹（F06-A）

```
ProductionListPage
├─ PageHeader（含「新增任務」CTA）
├─ FilterBar
│  ├─ StatusSelect（pending/processing/completed/failed/cancelled）
│  ├─ ApprovedSelect（all/approved/pending_review）
│  └─ BatchIdInput（option，貼批次 UUID 篩同批）
├─ AppDataTable
│  └─ row：縮圖（filled_template）/ id 短碼 / 來源（image / custom_request 連結）/ status badge / approved / canvas / 細緻 / 難易 / 建立時間
└─ AppPagination

ProductionNewPage
├─ PageHeader
├─ Section：來源
│  ├─ 上傳圖片（呼叫 /upload/production-image → Firebase 直傳 → POST /admin/images）
│  └─ 從客製申請選（dropdown 列 status ∈ {quote_pending, negotiating, draft_revision} 的申請）
├─ Section：批次組合表
│  ├─ ComboRow: canvas_size / detail / difficulty / mode（先只開 standard）
│  ├─ + 新增組合
│  └─ 摘要：N 組將以同 batch_id 送出
└─ Footer：[送出批次]

ProductionJobDetailPage
├─ Breadcrumb（工坊 / 製作 / #...）
├─ Header
│  ├─ id 短碼 + StatusBadge + ApprovedBadge
│  ├─ HeaderActions（依 status 浮現）：審核 / 撤銷審核 / 匯出 PDF
├─ Grid 兩欄
│  ├─ Main 欄
│  │  ├─ FilledTemplateCard（filled_template_url 直接 <img> — 公開）
│  │  ├─ SVGPreviewCard（簽章 URL，<img> 顯示但不下載）+ 「下載 PDF」按鈕
│  │  └─ PaletteListCard（調色盤色號 / RGB / HEX / 佔比）
│  └─ Side 欄
│     ├─ JobInfoCard（canvas、detail、difficulty、mode、num_colors_used）
│     ├─ TimelineCard（建立 / 完成 / 審核時間）
│     └─ NotesCard（admin notes）
└─ ApproveDialog（簡易確認框）
```

---

## 4. 狀態 / Query 設計

```ts
const PJ_KEYS = {
  list:   (params) => ['admin','production','list', params] as const,
  detail: (id)     => ['admin','production','detail', id] as const,
  canvasSizes:        ['admin','canvas-sizes'] as const,
  customCandidates:   ['admin','custom-requests','candidates'] as const,
}
```

- 列表 staleTime 30s
- 詳情 staleTime 10s — 並開啟 `refetchOnWindowFocus: true`，因 Celery 跑完不會主動推（F09 前無 SSE）
- mutation 後 invalidate
- pending / processing 的 detail 頁 → 5 秒輪詢一次（短時間內期望 Celery 推進）

---

## 5. zod 表單 schema（admin/src/features/production/schemas.ts）

```ts
const detail     = z.enum(['rough','standard','detailed','premium'])
const difficulty = z.enum(['beginner','elementary','intermediate','advanced'])
const mode       = z.enum(['standard','sam_refine','sam_weighted'])

const comboItem = z.object({
  detail,
  difficulty,
  mode: z.literal('standard'),  // F06-A 暫只開 standard
  canvas_w_cm: z.coerce.number().positive(),
  canvas_h_cm: z.coerce.number().positive(),
  min_brush_diam_cm: z.coerce.number().positive().default(1.0),
  num_colors: z.coerce.number().int().positive().optional(),  // null=用 difficulty 預設
})

const newJobSchema = z.object({
  source: z.enum(['image','custom_request']),
  image_id: z.string().uuid().optional().nullable(),
  custom_request_id: z.string().uuid().optional().nullable(),
  combos: z.array(comboItem).min(1, '至少一筆組合'),
}).superRefine((v, ctx) => {
  if (v.source === 'image' && !v.image_id) ctx.addIssue({ code: 'custom', path: ['image_id'], message: '請先上傳圖片' })
  if (v.source === 'custom_request' && !v.custom_request_id) ctx.addIssue({ code: 'custom', path: ['custom_request_id'], message: '請選一筆客製申請' })
})

const approveSchema = z.object({
  notes: z.string().max(2000).optional().nullable(),
})
```

---

## 6. 設計決策

| 項目 | 決策 |
|---|---|
| 任務 status 色票 | pending=warning、processing=info（pulsing dot）、completed=success、failed=danger、cancelled=muted |
| approved badge | 已審核=accent / 待審核=line outline |
| filled_template 預覽 | 直接 `<img :src="filled_template_url">`（後端是 Firebase download URL，公開讀）|
| SVG 預覽 | 詳情載入時打 `?file=svg` 拿簽章 URL → `<img>` 顯示；不提供右鍵下載（only PDF）|
| SVG 過大 | aspect-ratio 容器 + object-contain，顯示 max 800px 寬 |
| PDF 匯出 | 按下後 backend 直接 stream，前端用 `fetch + blob + link.click` 觸發下載（轉換 5–15 秒，期間按鈕 disable）|
| 上傳流程 | 1) POST /upload/production-image 拿 `upload_url + public_url` 2) 前端 PUT 直傳到 GCS 3) PUT 完 POST /admin/images 落地 metadata |
| 從客製申請選 | dropdown 用 `useCustomRequestsQuery` 但 status 限制：quote_pending / negotiating / draft_revision |
| 批次組合表 | 預設 1 列，可 +/-；以 array 管理；提交時打單筆 POST 帶 `jobs: [...]` |
| Polling | 詳情頁若 status ∈ {pending, processing} → `refetchInterval: 5000` |
| PDF 下載期間 | 按鈕變「轉換中...（最多 15 秒）」+ Loader |

---

## 7. 手動測試覆蓋表（F06-A）

| Case | 預期 | 驗證 |
|---|---|---|
| 列表預設載入 | 200 + 分頁 | screenshot |
| 篩 status / approved | URL 同步 | reload 仍保留 |
| 點 row 進詳情 | 200 + 預覽載入 | screenshot |
| 「新增任務」CTA | 切到 /admin/production/new | screenshot |
| 上傳圖片：JPEG 5MB | 直傳成功、image_id 寫入 form | screenshot |
| 上傳圖片：> 20MB | 前端阻擋 + toast | manual |
| 上傳圖片：非 JPEG/PNG | 前端阻擋 | manual |
| 從客製申請選 | dropdown 顯示候選；選後 form 帶入 | screenshot |
| 加 3 組合送出 | 200 + 列表立刻看到 3 筆同 batch_id | screenshot |
| pending detail polling | 5 秒輪詢；Celery 完成後自動更新 | mock or 等待 |
| completed detail | filled / svg / palette 都顯示 | screenshot |
| approve happy | POST 200 → badge 變「已審核」 | screenshot |
| unapprove | POST 200 → badge 退回 | screenshot |
| 匯出 PDF | 下載觸發、檔案非空 | manual |
| 401 / 403 / 404 | 友善錯誤 | mock |
| 失敗 job 詳情 | 顯示錯誤狀態 + 不可 approve | seed |
| F5 reload 詳情 | 正常重 fetch | screenshot |
| < 768px 寬 | 不爆版 | resize |

---

## 8. 規格定位

| 規格 | 來源檔案 |
|---|---|
| 路由 | `docs/requirements/admin_routes.md` |
| 製作流程 / 預設組合 | `docs/requirements/admin_production.md` |
| 5 種 status + approved | `docs/requirements/admin_production.md` + `docs/schema.md` production_jobs |
| API request/response | `docs/api.md` 模組四 |
| EVENT E26-E30 | `docs/EVENT_MATRIX.md` |
| 客製申請帶入 | `docs/EVENT_MATRIX.md` E26 + `admin_orders.md` §5.1 |
| 顏色對應銜接 | F07 規劃（本模組只標示「可進入顏色對應」連結，工作台屬 F07）|

---

## 9. 不在本模組範圍

- SAM 遮罩繪製 / sam_refine / sam_weighted 模式 → F06-B
- 後處理工具（合併 / 消邊界 / 平滑）→ F06-B
- 顏色對應工作台 → F07
- 批次失敗連動的 cancelled 推送 → F09 通知中心
- Celery 失敗清理 → 後端

---

## 10. 待確認事項

1. **F06-A 範圍是否能接受**：暫不做 SAM 與後處理。產品流程上：
   - 入門 / 初級 / 中級 用預設組合的 standard 模式可以解 80%+ 場景
   - SAM 是「想要選取局部細化」的進階場景；後處理是「對結果不滿意微調」
   - 現實上你還沒有任何 production_job 可以測，先確保 standard happy path 走得通最務實
   - **問**：同意 F06-A / F06-B 切分？

2. **PDF 匯出流程**：規格說 backend 即時用 Inkscape 轉 SVG → PDF，5–15 秒。前端可能 timeout。要不要做：
   - A. 維持同步下載（fetch + 顯示 loading 15 秒）
   - B. 改成「下載任務」非同步（multistep — 觸發後輪詢狀態 → 完成後給連結）— 後端要改

3. **canvas-sizes 端點**：規格沒明確列 `GET /admin/canvas-sizes`，但 admin_production.md 說「從 canvas_sizes 表選」。後端是否有此 endpoint？沒有則前端先 hardcode 9 種常用尺寸（20×20 / 30×30 / 30×40 / 40×50 / 50×70 / 60×60 等），等 F10 內容管理時補。

4. **建立任務後立刻跳轉**：建立完跳到列表還是首個 jobId 的詳情頁？批次有多筆時無法跳 detail，只能跳列表。**傾向：跳列表，URL query 帶 `?batch_id=...` 過濾此批**。
