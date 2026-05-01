# 04c. Production — SAM 模式完整實作（補完既有 production 模組的 SAM 路徑）

> 補強 [04_production.md](04_production.md)、[04_production_engine_integration.md](04_production_engine_integration.md) 的 SAM 部分。
> 規格依據：[admin_production.md §1.3](../requirements/admin_production.md)、[api.md `POST /sam-mask`](../api.md)、[schema.md production_jobs](../schema.md)、[EVENT_MATRIX.md E26-E29](../EVENT_MATRIX.md)。

---

## 一、現況盤點（為什麼要寫這份計畫）

| 層 | 已做 | 未做 |
|---|---|---|
| 規格文件 | admin_production.md §1.3 / api.md / schema.md / EVENT_MATRIX 完整 | — |
| pbn_gen 核心引擎 | `refine_region` / `apply_weighted_region` 已支援 | — |
| 後端 endpoint | `POST /admin/production/jobs/{id}/sam-mask`（polygons 路徑） | 純 sam_points 推論路徑（mask_url 永遠 null） |
| 後端 Celery worker | standard mode 完整 | sam_refine / sam_weighted **直接 fail**（`tasks.py:196-201` 明文 Phase 2-B） |
| 後端 engine wrapper | `generate_standard()` | `generate_sam_refine()` / `generate_sam_weighted()`（不存在） |
| 後端 SAM 模型載入 | — | 懶載入 + 常駐記憶體（admin_production.md §1.3） |
| admin 前端 | `Mode` 型別存在、API 包好 | 完全沒有 SAM UI（畫布互動、即時預覽、入口、串接） |

---

## 二、範圍切分（三個獨立 milestone）

依「能獨立交付、能獨立測試」切。每個 milestone 完成走一次完整 SOP（規格比對 → 實作 → 測試 → quality gates → reviewer → commit → 回頭驗收）。

### Phase A — 後端：Celery worker 整合 sam_refine / sam_weighted（吃既有 mask_url）
- 不需要 SAM 模型，純走 polygons 路徑（已能產 mask_url）
- 引擎 wrapper 加 `generate_sam_refine` / `generate_sam_weighted`
- worker 解開 Phase 2-B 鎖、依 mode 選對的 wrapper

### Phase B — 後端：SAM 推論（純 sam_points → mask）
- 懶載入 segment_anything（vit_b 模型）
- update_sam_mask 服務在 polygons 為空時走 SAM 推論並產 mask PNG
- 模型常駐記憶體（單例）

### Phase C — 前端：Mask 編輯 UI（畫布互動 + 串接）
- 新頁 `/admin/production/jobs/:id/mask`
- HTMLCanvas 互動：左鍵前景點 / 右鍵背景點 / 多邊形（左鍵新增 / 右鍵閉合）
- 即時把座標送 `POST /sam-mask`，後端回 mask_url 後 overlay 半透明綠色
- ProductionNewPage 選 sam_refine / sam_weighted 後，建立 job → 自動跳到 mask 編輯頁
- 撤銷 / 清除 / 確認

---

## 三、Phase A 詳細規劃

### A.0 規格比對報告決議（2026-05-01）

- **sam_* 單筆也分配 batch_id**：service.py `create_jobs` 行為從「N>1 才給 batch_id」改為「N>1 或任一筆 mode!=standard 都給」；schema response 仍 nullable，僅單筆 standard 為 null
- **batch start 缺 mask_url 時走 200 部分成功**：response `{enqueued: N, skipped: [{job_id, reason}]}`；admin 可逐筆補編後重點，已 enqueue 的不重跑
- **api.md 需補 `POST /admin/production/batches/{batch_id}/start` 規格**：A.4 開工前先補

### A.0.1 已知 limitation（reviewer 第二輪）

- **start_batch concurrent race**：用 `pg_advisory_xact_lock` 序列化同 batch_id 的並發呼叫；但 lock 釋放至 worker pick up 之間仍有極小 race window（admin 在毫秒級內連點同 batch 的「送出全批」）。worst case 是同一 sam_* job 被 worker 重複跑（資源浪費，非資料 corruption — 兩次 upload 用不同 token、最終 DB 寫回後者為主）。徹底防重複需新增 `production_jobs.dispatched_at TIMESTAMP` 欄位（schema 變更），列為 **未來改善項**，非 Phase A 範圍。

### A.1 要建立 / 修改的檔案

| 動作 | 檔案 | 說明 |
|---|---|---|
| 修改 | `backend/production/engine.py` | 新增 `generate_sam_refine()`、`generate_sam_weighted()`，內部沿用 paint-by-number/src/run.py:run_single_level 的 sam 分支邏輯（**不修改 paint-by-number/src/**） |
| 修改 | `backend/production/tasks.py` | 移除 `if job.mode != "standard"` 早 fail 區塊；加 `_resolve_engine_for_mode(job)` dispatcher；下載 `mask_url` 至 tmp 檔傳給 wrapper |
| 修改 | `backend/production/service.py` | `_resolve_params(job)` 補 `extra_colors` / `weight_ratio` / `mask_path`；`create_jobs` 在 `mode != standard` 時建 job 但**跳過 Celery enqueue**（等 batch start endpoint 觸發） |
| 修改 | `backend/production/router.py` | 新增 `POST /admin/production/batches/{batch_id}/start`：把 batch 內 mode!=standard 且 mask_url!=null 的 pending job 一次性 enqueue；缺 mask_url 的 job 列在 400 錯誤訊息中 |
| 修改 | `backend/production/schemas/response.py` | `BatchStartResponse {enqueued: int, skipped: list[{job_id, reason}]}`（暫定） |
| 新增 | `backend/tests/production/test_tasks_sam.py` | sam_refine / sam_weighted 完整成功、缺 mask_url、缺 extra_colors / weight_ratio、引擎拋例外的回滾、create_jobs 對 sam_* 不 enqueue、batch start endpoint 各情境 |

### A.2 Worker 業務流程（修改後）

```
load job
↓
job.mode == standard → 沿用既有路徑
job.mode == sam_refine → 需 mask_url + extra_colors > 0；下載 mask 至 tmp；engine.generate_sam_refine(...)
job.mode == sam_weighted → 需 mask_url + 0.5 ≤ weight_ratio ≤ 0.8；下載 mask；engine.generate_sam_weighted(...)
↓
sam_refine / sam_weighted 缺 mask_url → status=failed, notes="mode=X 但缺 mask_url（請先在製作系統編輯遮罩）"
↓
其餘流程（Firebase 上傳 / DB 寫回 / on_failure 清理）與 standard 完全一致
```

### A.3 generate_sam_refine / generate_sam_weighted 設計

兩者皆接受相同前置參數 + 一個額外 `mask_path: str`（PNG 灰階檔，0/255）。

`generate_sam_refine` 在 `set_final_pbn` 之後 + `merge_tiny_colors` 之前呼叫 `pbn.refine_region(mask, extra_colors=...)`；`merge_tiny_colors` 的 `exclude_mask` 傳入 mask（避免細化區小色塊被合併）。

`generate_sam_weighted` 改走 `pbn.apply_weighted_region(mask, total_colors, weight_ratio, bg_extra_blur)`，**不走** `set_final_pbn`；之後 `pruneClustersSimple` + 輸出。

兩者 mask 都需先 crop 成畫布比例（沿用 `_crop_to_canvas_ratio`，且 mask 與圖片用同一個 crop 偏移）。

### A.4 EVENT_MATRIX 對照（Phase A）

| Event | 副作用 | 規劃對應 |
|---|---|---|
| E26 製作 job 開始 | status pending→processing；遮罩鎖定 | 沿用既有路徑（worker 進入時 commit processing） |
| E27 製作 job 完成 | status processing→completed；寫 svg/filled/snapped/palette/num_colors_used；approved=false | sam_refine / sam_weighted 完成後寫法與 standard 一致 |
| E29 製作 job 失敗 | status→failed；INSERT admin_notifications(type=production_failed) | **目前 standard 路徑也沒插 admin_notifications** — 屬既有缺口，Phase A 不修，但於計畫書「待確認事項」列出 |

### A.5 測試覆蓋（Phase A）

| Case | 預期 | 測試函數 |
|---|---|---|
| sam_refine 完整成功（mask_url 存在 + extra_colors=10） | status=completed、palette_json 包含 refine_extra_colors | test_run_job_sam_refine_ok |
| sam_weighted 完整成功 | status=completed、weight_ratio 正確套用 | test_run_job_sam_weighted_ok |
| sam_refine 缺 mask_url | status=failed、notes 含「缺 mask_url」 | test_run_job_sam_refine_missing_mask |
| sam_weighted 缺 weight_ratio（理論不應發生，建立時應拒絕） | status=failed、notes 明示原因 | test_run_job_sam_weighted_missing_ratio |
| sam_refine 引擎拋例外 → on_failure 清 blob | status=failed、Firebase 已上傳的 blob 全刪 | test_run_job_sam_refine_engine_failure_cleanup |
| sam_refine 但 image 找不到 | status=failed | test_run_job_sam_refine_image_missing |
| create_jobs mode=sam_refine | job 建立、status=pending、Celery 未被 enqueue | test_create_jobs_sam_skips_enqueue |
| create_jobs mode=standard | 沿用既有：enqueue | test_create_jobs_standard_enqueues（既有不變，補一個 explicit 驗證） |
| batch start：所有 sam_* job 都有 mask_url | 200，全部 enqueue | test_batch_start_all_ready |
| batch start：部分 job 缺 mask_url | 400，error 列出缺的 job_id | test_batch_start_partial_missing_mask |
| batch start：batch 內含 standard job | 跳過 standard，只 enqueue sam_*（standard 已在建立時 enqueued） | test_batch_start_skips_standard |
| batch start：batch_id 不存在 | 404 | test_batch_start_not_found |
| batch start 非 admin | 403 | test_batch_start_non_admin |

---

## 四、Phase B 詳細規劃

### B.1 要建立 / 修改的檔案

| 動作 | 檔案 | 說明 |
|---|---|---|
| 新增 | `backend/production/sam_runtime.py` | `get_sam_predictor()` 單例懶載入；`predict_mask(predictor, image_url, points)` |
| 修改 | `backend/production/service.py` | `update_sam_mask` 在 polygons 為空、sam_points 不空時走 SAM 推論產 mask PNG 上傳 + 寫 mask_url + 寫 mask_coverage |
| 新增 | `backend/tests/production/test_sam_runtime.py` | mock segment_anything；驗證單例、point→mask 推論、mask_coverage 計算 |
| 修改 | `backend/requirements.txt` | 加 `segment-anything`（依 admin_production.md §1.3 註明走 vit_b） |
| 新增 | `backend/scripts/download_sam_model.py` | 下載 `sam_vit_b.pth`（部署初始化用；本地放 `paint-by-number/models/sam_vit_b.pth`） |

### B.2 SAM 模型部署策略（admin_production.md §1.3）

- 與 FastAPI 同進程；服務啟動時不載入
- 第一次有請求才載入（5-10 秒冷啟動），常駐記憶體
- `get_sam_predictor()` 用模組級變數實作單例（thread-safe lock）

### B.3 update_sam_mask 服務修改後流程

```
請求進來
↓
驗證 status=pending、mode 一致性（既有）
↓
if polygons 不空 → 既有 PIL 路徑（不變）
elif sam_points 不空 → 走 SAM：
    - 下載 image.original_url 至記憶體
    - get_sam_predictor() 載入並 set_image
    - predict_mask(points) → np.ndarray (H, W) bool
    - 計 mask_coverage = white / total
    - 編 PNG bytes → 上傳 Firebase → 寫 mask_url
↓
if sam_points 與 polygons 都不空 → 聯集（同 paint-by-number/src/sam_select.py:merge_masks）
↓
寫回 sam_points / polygons / mask_url / mask_coverage / approved=false
```

### B.4 EVENT_MATRIX 對照（Phase B）

無新增 Event；update_sam_mask 副作用本身在 admin_production.md §1.3 的「mask_url 更新邏輯」涵蓋（屬於 sam_points/polygons 編輯動作的延伸，不對應 EVENT_MATRIX 的 E0X）。approved 退回 false 與既有「合併色塊 / 消邊界」一致（E28 反向）。

### B.5 測試覆蓋（Phase B）

| Case | 預期 | 測試函數 |
|---|---|---|
| 純 sam_points（mock predictor 回固定 mask） | mask_url 非 null、mask_coverage 與 mock 一致 | test_update_sam_mask_points_only |
| sam_points + polygons → 聯集 | mask_coverage 約等於兩者聯集面積 | test_update_sam_mask_union |
| 第二次呼叫 → predictor 不重複載入 | get_sam_predictor() 只被建構 1 次 | test_sam_predictor_singleton |
| segment_anything 未安裝 | BadRequestError「SAM 未安裝」 | test_sam_runtime_missing_dependency |
| Firebase 上傳失敗 | mask_url=null、不丟例外 | test_update_sam_mask_upload_fail |

---

## 五、Phase C 詳細規劃

### C.1 要建立 / 修改的檔案

| 動作 | 檔案 | 說明 |
|---|---|---|
| 新增 | `admin/src/features/production/pages/MaskEditPage.vue` | 新路由 `/admin/production/jobs/:id/mask`；畫布互動主頁 |
| 新增 | `admin/src/features/production/components/MaskCanvas.vue` | 包 HTMLCanvas + 滑鼠事件處理（左鍵前景 / 右鍵背景 / 多邊形） |
| 新增 | `admin/src/features/production/components/MaskToolbar.vue` | 撤銷 / 清除 / 確認 / 切換 SAM↔多邊形模式 |
| 修改 | `admin/src/features/production/api.ts` | 加 `updateSamMask(jobId, body)`、移除「F06-B 未實作」註解 |
| 修改 | `admin/src/features/production/queries.ts` | `useSamMaskMutation` |
| 修改 | `admin/src/features/production/pages/ProductionNewPage.vue` | mode 下拉選 sam_refine / sam_weighted 時，建立 job 後 router.push 到 MaskEditPage |
| 修改 | `admin/src/features/production/pages/ProductionJobDetailPage.vue` | status=pending 且 mode!=standard 時，在「結果預覽」上方顯示「編輯遮罩」按鈕 |
| 修改 | `admin/src/router.ts`（或對應檔） | 新增路由 |

### C.2 Canvas 互動規格（admin_production.md §1.3）

```
SAM 模式（預設）：
  左鍵 → push sam_points {x, y, label: 1} (前景，綠點)
  右鍵 → push sam_points {x, y, label: 0} (背景，紅點)

多邊形模式：
  左鍵 → 當前 polygon 加頂點
  右鍵 → 若當前 polygon ≥ 3 點 → push 進 polygons，開新的；否則忽略

通用：
  撤銷 → 移除最後一筆動作（依時間軸 stack）
  清除 → 重置 sam_points / polygons / current_polygon
  確認 → 不再呼叫 API（編輯期間每次點擊已 debounce 送出）；只關閉頁面跳回任務詳情

每次點擊（debounce 300ms）→ 送 POST /sam-mask → 後端回 mask_url + mask_coverage → 重畫 overlay
```

### C.3 ProductionNewPage 行為變更

```
原流程：選圖 + 設定 + mode=standard → POST /jobs → 跳列表
新流程：
  mode=standard → 沿用（沒變）
  mode=sam_refine / sam_weighted →
    - 「組合 N」面板額外要求 extra_colors（sam_refine）或 weight_ratio（sam_weighted）
    - 一批送出時若任何 job 為 sam_*，建立完直接 router.push 到「批次遮罩編輯」流程
    - 由於批次可能含多個 sam_* job（每筆 image_id 不同），先做「**單筆**送出時跳 mask 編輯」；批次先擋 sam_* + standard 混用 → 待確認事項列出
```

### C.4 EVENT_MATRIX 對照（Phase C）

無新 Event；前端只是觸發 update_sam_mask（既有 service 副作用，Phase A/B 已涵蓋）。

### C.5 測試覆蓋（Phase C）

前端用既有 admin 測試風格（vitest + Vue Test Utils）。實際 e2e 在瀏覽器手動驗收。

| Case | 預期 | 測試函數 |
|---|---|---|
| MaskCanvas 左鍵 → emit add_sam_point label=1 | emit 包含 {x, y, label: 1} | test_canvas_left_click_foreground |
| MaskCanvas 右鍵 → emit add_sam_point label=0 | label=0 | test_canvas_right_click_background |
| 多邊形模式右鍵 < 3 點 | 不 emit close_polygon | test_polygon_close_requires_3_points |
| 撤銷 SAM 點 | sam_points 長度 -1 | test_undo_pops_last_action |
| ProductionNewPage 選 sam_refine 沒填 extra_colors | 提交按鈕 disabled | test_new_page_sam_refine_validation |

---

## 六、規格 / api.md / schema.md 一致性確認

### Schema.md 涉及欄位

| 欄位 | schema 規定 | Phase 對應 | 狀態 |
|---|---|---|---|
| production_jobs.mode | enum standard/sam_refine/sam_weighted | A worker dispatch | 既有 |
| production_jobs.extra_colors | int? | A 引擎參數 | 既有（驗證已存在） |
| production_jobs.weight_ratio | numeric(3,2)?, 0.5~0.8 | A 引擎參數 | 既有 |
| production_jobs.sam_points | jsonb? `[{x,y,label}]` | B 推論輸入 | 既有 |
| production_jobs.polygons | jsonb? `[[[x,y],...]]` | A mask 來源 | 既有 |
| production_jobs.mask_url | string? Firebase 路徑 | A 輸入 / B 輸出 | 既有 |
| production_jobs.mask_coverage | numeric(6,2)?, 0~1 | B 計算 | 既有（PIL 路徑已寫；SAM 路徑空缺） |

### api.md 涉及 endpoints

| Endpoint | api.md 規定 | Phase 對應 | 狀態 |
|---|---|---|---|
| `POST /admin/production/jobs/{id}/sam-mask` | request {sam_points, polygons, mode}；response {mask_url, mask_coverage} | B 補完純 sam_points 路徑 | endpoint 既有，B 補實作 |
| `POST /admin/production/jobs`（建立 job） | mode=sam_refine 需 extra_colors；mode=sam_weighted 需 weight_ratio | A 不變、validator 既有 | 既有 |

---

## 七、待確認事項（必須先回答才能開工）

1. ~~**Phase A 起跑前是否補 admin_notifications(type=production_failed) 缺口**？~~ **[已決議：選項 C]**
   - 決議 (2026-05-01)：Phase A **不一併補**，但 Phase A 結束 commit 後**立即**接著做為獨立 commit。
   - 範圍：sam_refine / sam_weighted 與既有 standard 路徑**全部**補 INSERT admin_notifications(type=production_failed)。
   - 提醒：見 §九「立即後續 follow-up」。

2. ~~**Phase A 是否需要拓展現有測試 fixture**？~~ **[已決議：選項 B]**
   - 決議 (2026-05-01)：**另寫** `backend/tests/production/test_tasks_sam.py`，與既有 `test_tasks.py` 並列。
   - 範圍：Phase A 內 sam_refine / sam_weighted 全部測試 case 寫在新檔；既有 test_tasks.py 不動。
   - 重複的 helper（_make_sam_job、mock engine setup）就接受重複；未來 Phase B/C 若有需要再抽到 conftest.py。

3. ~~**Phase B 模型檔放哪**？~~ **[已決議：選項 A — Docker image 內含]**
   - 決議 (2026-05-01)：模型檔走 **Docker image 內含**（與 Inkscape 同策略）。
   - **程式碼層**：Phase B 走環境變數 `SAM_MODEL_PATH` 抽象，本地預設 `paint-by-number/models/sam_vit_b.pth`，部署環境會由 ENV 注入。
   - **部署層**（待 Railway 部署計畫書）：未來 Dockerfile 加
     ```dockerfile
     RUN curl -L https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth \
         -o /app/models/sam_vit_b.pth
     ENV SAM_MODEL_PATH=/app/models/sam_vit_b.pth
     ```
   - 理由：與 Inkscape 一致；不依賴 persistent volume；redeploy 命中 layer cache 不重下載。
   - 用戶確認 Railway Pro plan（24 GB RAM / 100 GB Shared Disk），375MB image 增量可接受。

4. ~~**Phase C ProductionNewPage 批次混合 sam_* / standard**？~~ **[已決議：擋混用 + 支援純 sam_* 批次]**
   - 決議 (2026-05-01)：
     - **不允許** standard + sam_* 在同一批次混用（前端 validation 擋；後端可選擇加同樣 validation）
     - **允許** 純 sam_*（同 mode）批次（多筆同 mode 同 image 不同尺寸/難度）
     - Phase C 範圍**包含**純 sam_* 批次的逐筆 mask 編輯 wizard 流程
   - **建立 / 觸發流程拆分**（Phase A 範圍順帶要動）：
     - mode=standard：`POST /admin/production/jobs` **沿用既有** — 建 job + 立即 enqueue Celery
     - mode=sam_*：`POST /admin/production/jobs` **僅建 job（status=pending）不 enqueue**；等 admin 編完所有 batch 的 mask 後呼叫 `POST /admin/production/batches/{batch_id}/start` 一次性 enqueue 整批
   - 需新增 endpoint：`POST /admin/production/batches/{batch_id}/start`
     - 行為：把 batch 內所有 status=pending 且 mode!=standard 且 mask_url!=null 的 job enqueue Celery；任何一筆缺 mask_url → 400 錯誤訊息列出哪幾筆未編輯
     - 權限：admin
   - **Phase A 因此擴張**：加上「create_jobs 在 mode!=standard 時跳過 enqueue」+ 新增 batch start endpoint + 對應測試。
   - **Phase C wizard UX**：建 N 筆 → router.push `/admin/production/batches/:batch_id/mask?step=1` → 第 i 筆完成跳第 i+1 筆 → 全部編完顯示「送出全批處理」按鈕 → 觸發 batch start endpoint。

5. ~~**Phase C 即時預覽的後端壓力**？~~ **[已決議：選項 A — 立即疊點 + 後續覆蓋 mask]**
   - 決議 (2026-05-01)：
     - 點擊**立即**在前端 canvas 疊「臨時點」（左鍵綠圓 / 右鍵紅圓），不等 API
     - 同時送 `POST /sam-mask`（debounce 300ms — 短時間內多次點擊只送最後一次）
     - 後端回 mask_url 後，半透明綠 overlay 蓋在點上方
     - 處理 race：每次送出帶遞增 `request_seq`；只用 `response_seq == latest_request_seq` 的回應；舊的 stale response 直接丟
   - 沿用 paint-by-number/src/sam_select.py 桌面版設計（先畫點再 overlay）。
   - 不選 B（loading spinner）：會讓 admin 連點導致後端炸。
   - 不選 C（disable 滑鼠）：體感差。

---

## 八、執行節奏（Definition of Done）

依 CLAUDE.md「分段節奏」，三個 Phase 各走一輪完整 SOP：

1. **Phase A**：規格比對報告 → 程式碼 → 測試 → quality_check.py → /reviewer → 回頭驗收 → commit
2. **Phase B**：同上
3. **Phase C**：因為純前端，沒有 backend quality_check.py 規範；走 lint + 手動瀏覽器驗收（重新建 sam_refine job → 編輯遮罩 → 送出 → worker 跑通 → 預覽圖正確）

每個 Phase 結束後才開始下一個。

---

## 九、立即後續 follow-up（Phase A 結束 commit 後立刻做，不可遺漏）

**補 admin_notifications(type=production_failed) 缺口**

- 規格依據：[EVENT_MATRIX.md E29](../EVENT_MATRIX.md)
- 範圍：production worker（standard + sam_refine + sam_weighted）所有失敗路徑（_mark_job_failed、引擎/上傳失敗、最終 commit 失敗、缺欄位失敗）
- 修改點：`backend/production/tasks.py` 的所有 `job.status = JobStatusEnum.failed` 後面緊接 INSERT admin_notifications
- 測試：每個失敗路徑各加一個「同時驗證 admin_notifications 有被寫入」assertion
- commit message：`fix(production): worker 失敗時補插 admin_notifications(production_failed) — EVENT_MATRIX E29 既有缺口`
- **觸發時機**：Phase A reviewer pass + git commit 完成的下一個動作。不得進入 Phase B 之前。
