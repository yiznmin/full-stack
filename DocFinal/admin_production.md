# 管理者端：製作模組

## 1.1 圖片上傳

- 支援 JPG / PNG
- 上傳後存至 Firebase Storage，顯示縮圖預覽
- 同一張圖可多次重跑，每次為獨立處理記錄

**從客製申請帶入照片**

管理員可選擇「從客製申請選取」，直接帶入該申請的 `photo_url`，不需重新上傳：
- 下拉選單顯示狀態為 `negotiating` 或 `quote_pending` 的 `custom_photo` 申請
- 選取後照片從 Firebase Storage 直接載入
- production_job 建立後自動關聯至該 custom_request（`custom_request_id` 欄位）

---

## 1.2 參數設定

使用者先選預設組合，不滿意再手動覆蓋細節參數。

**細緻度**（控制 blur / prune / min_ratio，影響格子多寡）

| 選項 | blur_ksize | blur_sigma_color | blur_sigma_space | prune_iterations | bg_extra_blur | min_ratio_multiplier |
|------|-----------|-----------------|-----------------|-----------------|--------------|---------------------|
| 粗糙 | 31 | 51 | 51 | 10 | 21 | 2.0 |
| 標準 | 21 | 21 | 14 | 6  | 21 | 1.0 |
| 細緻 | 13 | 13 | 9  | 3  | 9  | 0.6 |
| 高級 | 7  | 7  | 5  | 1  | 0  | 0.3 |

**難易度**（控制色數，影響上色複雜度）

| 選項 | num_colors | pruning_threshold | refine_extra_colors |
|------|-----------|------------------|-------------------|
| 入門 | 18 | 8e-4    | 8  |
| 初級 | 24 | 2e-4    | 12 |
| 中級 | 35 | 6.25e-5 | 18 |
| 進階 | 50 | 1.5e-5  | 25 |

**進階覆蓋**（可手動調整個別參數，覆蓋預設值）

- blur_ksize、blur_sigma_color、blur_sigma_space
- prune_iterations、pruning_threshold
- num_colors（上限）
- min_ratio_multiplier
- bg_extra_blur

**處理模式**

| 模式 | 說明 | 額外參數 |
|------|------|---------|
| standard | 全圖直接轉換，不需遮罩 | — |
| sam_refine | 選取區額外加色（細化），需遮罩 | extra_colors |
| sam_weighted | 選取區佔色數比重較高，非選取區更簡化，需遮罩 | weight_ratio (0.5~0.8，預設 0.65) |

**組合批次送出**

管理員在送出前可自由組合多筆任務，每筆任務為獨立一組（尺寸 + 細緻度 + 難易度 + 模式），介面顯示組合清單可新增 / 刪除列：

```
組合 1│ 30×40 │ 標準 │ 入門 │ standard
組合 2│ 40×50 │ 標準 │ 入門 │ standard
組合 3│ 30×40 │ 細緻 │ 中級 │ standard
                        [+ 新增組合] [送出全部]
```

- 送出後每個組合各自建立一筆 `production_job`
- 同批送出的 job 共用同一個 `batch_id`，處理記錄頁可依批次分組查看
- 每筆 job 各自審查、各自進入顏色對應與上架流程
- **執行順序**：批次 job 依序進入 Celery 佇列，一次只執行一個，不並發（避免 SAM 模型同時載入多份佔用過多記憶體）
- **批次失敗處理**：若批次中任一 job 失敗，後續尚未執行的 job 全部取消（status = `cancelled`），整批標記失敗，管理員需重新送出整批
- **客戶通知原則**：失敗全部**只進後台 admin_notifications**（type=production_failed），**不自動通知客戶**（不寄 email、不在 custom_request_messages 插入系統訊息）。若管理員判斷需要告知客戶，透過正常客服對話手動告知。
- **設計理由**：客戶不需要知道技術細節（重試、失敗），自動系統訊息會造成不必要的焦慮；管理員有狀況時走正常對話流程比較合適。

**畫布尺寸**

- 從 `canvas_sizes` 表（is_active=true）中選擇
- 系統根據圖片比例自動推薦最接近的 3 個尺寸，置於選單最上方
- **不支援非標準尺寸**；若有特殊尺寸需求，管理員需先於「內容管理 > 畫布尺寸」新增該尺寸，並在 pricing_formula 的基礎成本表補上該尺寸的計算依據

**min_brush_diam_cm**（最小筆觸直徑，預設 1.0cm）

---

## 1.3 SAM 遮罩（sam_refine / sam_weighted 模式才需要）

在網頁介面上直接選取區域，後端呼叫 SAM 模型推論，每次點選即時更新遮罩預覽。

**SAM 模型部署策略**

SAM 與 FastAPI 部署於同一 Railway 服務（同進程）。採懶載入：服務啟動時不載入模型，第一次有請求用到 SAM 時才載入並常駐記憶體，後續請求直接使用已載入的模型實例，不重複初始化。第一次呼叫約需 5~10 秒冷啟動，之後推論速度正常。

**兩種選取模式（可混用，最後合併為聯集）**

| 模式 | 操作 | 說明 |
|------|------|------|
| SAM 智慧點選 | 左鍵＝前景點（綠）/ 右鍵＝背景點（紅） | SAM 模型自動推論邊界 |
| 多邊形框選 | 左鍵逐點新增頂點 → 右鍵閉合，可繼續畫下一個 | 手動描邊，支援多個多邊形 |

**即時預覽**

- 每次新增/移除點或頂點，立即送後端推論，回傳遮罩疊加預覽圖
- 遮罩以半透明綠色覆蓋在圖片上顯示選取範圍

**其他操作**

- 撤銷：移除最後一個點或頂點
- 清除：重新開始選取
- 確認：儲存遮罩與選取記錄

**遮罩編輯時機限制**

遮罩**僅能在 production_job 進入 processing 之前編輯**：

- `production_job.status = pending` → 可自由編輯 sam_points、polygons、mask_url
- `production_job.status = processing` → 鎖定，不得編輯
- `production_job.status = completed / failed / cancelled` → 鎖定

**mask_url 更新邏輯**
- 每次新增/移除 sam_points 或 polygons 時，後端即時重新計算聯集 PNG 並**覆蓋** mask_url
- sam_points、polygons 作為「可編輯狀態的原始資料」永久保留（不隨 mask_url 覆蓋而丟失）
- 未來若要「重建當時的遮罩」→ 從 sam_points + polygons 重新計算

**需要儲存到資料庫的資料（供未來分析）**

| 欄位 | 說明 |
|------|------|
| sam_points | SAM 前景/背景點座標與標籤 [{x, y, label}] |
| polygons | 多邊形頂點列表 [[[x,y], ...]] |
| mask_url | Firebase Storage 遮罩 PNG 路徑 |
| mask_coverage | 遮罩佔圖片面積比例（%）|

未來可分析：常被細化的部位、點選數量與結果品質的關聯、不同圖片類型的選取模式差異。

---

## 1.4 觸發處理

- 送出參數 → 後端建立 Celery 任務
- 介面即時顯示任務狀態：等待中 / 處理中 / 完成 / 失敗
- 失敗時顯示錯誤訊息，可重新送出
- 從客製申請帶入的照片（`photo_url` 為 Firebase 私有檔案）：後端以 Firebase Admin SDK 下載至暫存目錄，傳給 Celery 任務使用，任務完成或失敗後自動刪除暫存檔

**Celery 失敗清理機制**

任務執行期間，Worker 將每次成功上傳至 Firebase 的路徑記錄於任務上下文（uploaded_paths 清單）。
若任務在任何步驟失敗，`on_failure` 回呼自動逐一刪除 uploaded_paths 中的所有 Firebase 檔案，避免殘留孤兒檔案佔用空間。
`production_job.status` 同步更新為 `failed`，不寫入任何檔案路徑欄位。

---

## 1.5 結果預覽

處理完成後可查看：

- `filled_template.png`：上色完成效果預覽圖
- `template.svg`：數字模板（可縮放檢視）
- 調色盤列表：色號、RGB、HEX、佔比（%）
- 定價建議（系統根據畫布尺寸 × 難易度 × 細緻度計算公式建議售價）

---

## 1.6 後處理調整

結果出來後，在預覽介面上進行微調，不需重跑完整流程。

每次調整後自動重新產生 SVG + filled_template，兩者保持一致。

**操作 A：格子合併**

- 點選預覽圖上的某個色塊
- 選擇目標色號（或從調色盤下拉選擇）
- 後端：將該色塊的像素改為目標顏色（修改 snapped_rgb）→ 重跑 output_to_svg + output_filled_from_template
- 被合併的顏色從 `palette_json` 中移除，對應的 `palette_color_mappings` 記錄同步刪除
- `production_job.approved` 退回 `false`，需重新進入顏色對應確認流程

**操作 B：消除邊界線**

- 點選兩個色塊之間的邊界線
- 系統顯示邊界兩側各是哪個色號，讓使用者選擇哪個顏色存活（預設：面積較大者）
- 後端：將被吸收側的像素全部改為存活顏色（修改 snapped_rgb）→ 重跑 SVG + filled_template
- 被吸收的顏色從 `palette_json` 中移除，對應的 `palette_color_mappings` 記錄同步刪除
- `production_job.approved` 退回 `false`，需重新進入顏色對應確認流程

**操作 C：輪廓平滑**

- 點選某條輪廓邊界線
- 調整平滑強度（1~5 級，對應 Chaikin corner-cutting 迭代次數）
- 後端：對該 polygon 頂點套用平滑演算法 → 更新 SVG 中該路徑 → 重新產生 filled_template
- 注意：此操作只改 SVG polygon，不改 snapped_rgb；相鄰邊界微小誤差由 stroke 覆蓋

---

## 1.7 顏色對應狀態

製作模組審核通過後，調色盤中的每個 RGB 尚未對應實體色號。
實體色對應在「填色色號對應實體色管理模組」中人工完成，**全部對應完成才能進入商品上架流程。**

調色盤欄位（palette_json）只存演算法產出的原始 RGB，不存實體色資訊：
```json
[
  { "template_id": 1, "rgb": [247, 167, 132], "hex": "#F7A784", "pixels": 12400, "percent": 8.2 },
  ...
]
```

---

## 1.8 確認儲存

- 調整完成後，管理者點「確認儲存」
- 系統將本次處理的最終參數與結果存入資料庫
- 存入內容：所有參數、輸出檔案路徑（Firebase Storage URL）、調色盤
- `status = completed`（處理成功完成）且 `approved = true`（管理員審核通過），兩者同時成立才可進入顏色對應流程
- `status = completed` 但 `approved = false`：處理完成但尚未審核（或後處理後退回審核）
- `approved` 僅由管理員手動點「確認儲存」或後處理退回時變更
- 可加備註（notes）

**儲存格式說明**

| 檔案 | 儲存方式 | 說明 |
|------|---------|------|
| template.svg | Firebase Storage，存路徑（私有）| 來源檔，可隨時再修改或重新產生 PDF |
| filled_template.png | Firebase Storage，存路徑（公開）| 預覽圖，與 SVG 保持同步 |
| snapped_rgb | Firebase Storage，存路徑（私有）| 後處理用中間層 |
| template.pdf | **不儲存** | 按需從 SVG 轉換後直接下載，不寫回資料庫 |

**Firebase Storage 存取控制**

| 檔案 | 權限 | 原因 |
|------|------|------|
| `images.original_url`（管理員上傳原始圖片） | **私有** | 含原始照片，不需公開前台 |
| `custom_requests.photo_url`（客戶客製照片） | **私有** | 客戶隱私資料 |
| `production_jobs.svg_url`（template.svg） | **私有** | 含完整編號的向量模板，是核心商業資產；若洩漏可被第三方直接印製銷售 |
| `production_jobs.snapped_rgb_url` | **私有** | 後處理中間層，不對外 |
| `production_jobs.mask_url`（SAM 遮罩） | **私有** | 中間層，不對外 |
| `production_jobs.filled_template_url`（filled_template.png） | **公開** | 僅為預覽示意圖，客戶已能在商品詳情頁看到；不含可列印的向量資料，無保護價值 |
| `product_images.image_url`（商品圖） | **公開** | 商品封面、成品實拍 |
| `products.cover_image_url` | **公開** | 同上 |
| `custom_cases.image_url`（客製案例） | **公開** | 行銷用途 |

**私有檔案的存取方式**

後端用 Firebase Admin SDK（Service Account）產生**簽名 URL**，有效期限 15 分鐘：

1. 前端向後端請求臨時連結
2. 後端驗證 JWT 身份與權限（管理員一律可存取；客戶僅可存取自己的 custom_requests.photo_url）
3. 後端回傳簽名 URL
4. 前端用此 URL 直接從 Firebase 下載
5. 連結過期後自動失效，無法重複使用

**為什麼 `filled_template.png` 公開、`template.svg` 私有？**

兩者都是 production_job 的產出，但性質完全不同：

- **filled_template.png**：已填色的**點陣圖預覽**，用途是「讓客戶看到成品的樣子」。客戶在商品詳情頁本來就看得到，公開無風險。
- **template.svg**：含編號標記的**向量模板**，用途是「產出可列印的畫布」。若這個檔案外洩：
  - 任何人可以用它直接印製畫布
  - 等於繞過你的銷售流程直接拿到商品核心
  - 這是本事業最需要保護的資產

簡言之：看得到預覽沒關係，能拿到可印製的向量檔才有問題。

**匯出 PDF**

管理者在後台點「匯出 PDF」：
1. 後端從 Firebase 下載 SVG
2. 自動將 SVG viewBox 四周各擴展 5cm（裝訂用空白，固定行為）
3. 呼叫 Inkscape 轉換（文字轉路徑）
4. 直接回傳 PDF 下載，不上傳至 Firebase
5. 若 SVG 有更新，每次匯出都重新轉換，確保與最新 SVG 一致

> PDF 實際尺寸 = (畫布寬 + 10cm) × (畫布高 + 10cm)，與印刷廠所需尺寸一致。
> 前端在匯出進行中將按鈕設為 disabled，轉換完成或失敗後才恢復，避免重複觸發。

---

## 1.9 處理記錄

- 同一張原始圖片可有多筆處理記錄（不同參數組合），重新送出時舊 job 保留不動，新 job 獨立建立
- 列表顯示：建立時間、細緻度、難易度、模式、畫布尺寸、狀態（approved / pending / failed）
- 可查看任意一筆的結果與參數
- 只有 approved 的記錄可進入顏色對應流程

---

## 1.10 資料庫欄位

**原始圖片表（images）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| uploader_id | FK → users.id（上傳的管理員）|
| original_url | Firebase Storage 原始圖片路徑 |
| filename | 原始檔名 |
| width | 圖片寬度（px）|
| height | 圖片高度（px）|
| created_at | 上傳時間 |

> 同一張圖片可對應多筆 production_jobs（不同參數跑多次）。

**處理任務表（production_jobs）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| image_id | FK → images.id（管理員手動上傳時填入；從客製申請帶入照片時為 null，原始圖從 custom_request.photo_url 取得）|
| custom_request_id | FK → custom_requests.id（從客製申請帶入時關聯，nullable）|
| status | pending / processing / completed / failed |
| detail | 細緻度（粗糙/標準/細緻/高級） |
| difficulty | 難易度（入門/初級/中級/進階） |
| blur_ksize | 覆蓋值（若手動調整） |
| blur_sigma_color | 同上 |
| blur_sigma_space | 同上 |
| prune_iterations | 同上 |
| pruning_threshold | 同上 |
| num_colors | 同上 |
| min_ratio_multiplier | 同上 |
| bg_extra_blur | 同上 |
| mode | standard / sam_refine / sam_weighted |
| canvas_w_cm | 畫布寬度 |
| canvas_h_cm | 畫布高度 |
| extra_colors | sam_refine 額外色數 |
| weight_ratio | sam_weighted 比重 |
| min_brush_diam_cm | 最小筆觸直徑 |
| sam_points | SAM 前景/背景點 JSON [{x,y,label}]（nullable）|
| polygons | 多邊形頂點 JSON [[[x,y],...]]（nullable）|
| mask_url | Firebase Storage 遮罩 PNG 路徑（nullable）|
| mask_coverage | 遮罩佔圖片面積比例 %（nullable）|
| svg_url | Firebase Storage 路徑 |
| filled_template_url | Firebase Storage 路徑 |
| snapped_rgb_url | Firebase Storage 路徑（後處理用） |
| palette_json | 調色盤 JSON（純演算法 RGB，不含實體色） |
| num_colors_used | 實際使用色數 |
| approved | boolean |
| notes | 管理者備註 |
| batch_id | 批次識別碼（UUID，同批送出的 job 共用，單筆送出為 null）|
| created_at | 建立時間 |
| approved_at | 確認時間 |
