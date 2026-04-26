# 管理者端：填色色號對應實體色管理模組

---

## 2.1 實體色庫管理

管理所有可用的實體顏料資料，是顏色對應的基礎資料表。

**色庫欄位**

| 欄位 | 說明 |
|------|------|
| 色號（標號） | 如 `201`、`601`、`955` |
| 顏色名稱 | 如 `SKIN TONE`、`RAW SIENNA` |
| 色系 | 如紅系、藍系、膚色系、中性灰...（供篩選用） |
| 來源 / 品牌 | 供應商資訊（之後補充） |
| RGB 近似值 | 用於系統自動預設對應計算（LAB 距離） |
| 庫存數量 | 管理員手動更新 |

**操作**

- 新增 / 編輯 / 停用實體色條目（停用後視同庫存為 0，對應商品自動顯示預購狀態）
- 更新庫存數量
- 按色系篩選瀏覽

**進貨操作流程**

**輸入單位：統一為 ml**

初期管理員進貨時，後台輸入 `stock_ml` 的新增量（ml 為單位），管理員自行依實際購買的顏料規格換算。

- 範例：購買 5 罐 × 30 ml → 輸入 150
- 未來視需求可擴充「支數 × 每支 ml」的輸入介面，後端仍儲存為 ml

管理員在色庫頁面找到色號 → 點「更新庫存」→ 輸入新增量（ml）→ 確認。
系統執行：
1. `stock_ml` 增加輸入量
2. 掃描所有使用此顏色、仍有 `preorder_qty > 0` 的待出貨訂單，依訂單建立時間排序
3. 逐一判斷現有庫存是否足夠（能備就備，跳過庫存不足的訂單，繼續嘗試下一筆）
4. 庫存足夠的訂單（全自動，無需管理員確認）：
   - 扣減 `stock_ml`（`required_ml × preorder_qty`）
   - 將 `order_items.fulfilled_qty += preorder_qty`，`preorder_qty = 0`
   - 若該訂單所有 item 的 `preorder_qty` 均已歸零，且訂單 `shipping_preference = 'separate'` 或原本就無預購分批，系統自動建立出貨任務（`production_progress` 推進到備貨流程）
   - 發 email 通知客戶「預購商品已可備貨，即將進入出貨流程」
   - 觸發管理員通知（admin_notifications）告知有預購訂單已自動升單

**預購缺貨儀表板**

色庫管理頁顯示庫存不足警示表，讓管理員進貨前一眼掌握各色缺口：

| 欄位 | 說明 |
|------|------|
| 色號 | 實體色代號 |
| 顏色名稱 | 顏色名稱 |
| 現有庫存（ml）| 目前 `stock_ml` |
| 待備量（ml）| 所有預購訂單的 `required_ml × preorder_qty` 加總 |
| 缺口（ml）| 待備量 − 現有庫存（僅顯示缺口 > 0 的顏色）|
| 等待訂單數 | 尚未備貨的預購訂單筆數，可點開查看明細 |

> 缺口為 0 或負數（庫存充足）的顏色不顯示於此表。

---

## 2.2 調色盤對應工作台

**入口（兩種）**

- 選擇「已通過審核、尚未完成顏色對應」的製作結果
- 選擇「已完成對應、想要修改」的製作結果

**從其他 job 複製對應**

同一批次（共用 `batch_id`）或同一原始圖片的多個 job，調色盤顏色通常相同。工作台提供「複製對應」功能避免重複作業：

1. 點選「從其他 job 複製對應」
2. 系統列出同批次或同圖片中已完成顏色對應的 job 供選擇
3. 選取來源 job → 系統將其 `palette_color_mappings` 按 `template_id` 複製至目前 job
4. 管理員確認預覽（可在複製後逐一修改個別顏色）→ 套用

> 複製後仍需管理員點「完成對應」確認，不自動標記完成。

**介面佈局**

```
左側：系統調色盤
      template_id + RGB 色卡 + 目前對應狀態

中央：即時預覽圖
      可切換「演算法原色」vs「實體色預覽」

右側：當前選中顏色的對應操作區
```

---

## 2.3 系統自動預設對應

進入工作台時，系統自動為所有未對應的演算法顏色找出最近似的實體色：

- 計算方式：演算法 RGB 與實體色庫 RGB 在 **LAB 色彩空間**的歐氏距離，取最小值
- 距離相同時取 `physical_colors.id` 最小者（最早建立）
- 若最近似色庫存為 0，自動找下一個有庫存的最近似色
- 管理者可逐一確認或修改

---

## 2.4 修改對應（選色方式）

點選某個調色盤色卡進行修改時，提供三種選色方式：

**方式 A：查過往紀錄**

- 列出這個演算法 RGB（或相近 RGB）在歷史對應中曾使用過的實體色
- 顯示使用次數與對應的圖片類型，供參考

**方式 B：按色系瀏覽**

- 選擇色系（如膚色系、暖棕系、中性灰...）
- 列出該色系所有實體色供點選

**方式 C：直接搜尋**

- 輸入色號或顏色名稱關鍵字直接搜尋

---

## 2.5 即時預覽

- 每次修改一個顏色的對應，中央預覽圖立即以實體色 RGB 重新渲染
- 可切換「演算法原色」/ 「實體色預覽」對比查看效果
- 渲染方式：前端直接用 canvas 替換色值，不需呼叫後端

---

## 2.6 庫存警示

- 選擇某個實體色時，若庫存為 0 → 顯示警示「此色號庫存不足」
- 允許選用庫存不足的顏色，但對應完成後商品標記為「顏料待補貨」
- 標記為「顏料待補貨」的商品可上架，顯示**預購**狀態，提示客戶等待時間較長

---

## 2.7 完成對應

- 所有演算法顏色均已對應實體色 → 對應狀態標記為完成
- 系統掃描所有對應的實體色庫存：
  - 全部有庫存 → 可進入商品上架流程
  - 有任一顏色庫存不足 → 商品標記「顏料待補貨」，以預購方式上架

---

## 2.8 資料庫欄位

**實體色庫（physical_colors）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| code | 色號（如 `201`） |
| name | 顏色名稱（如 `SKIN TONE`） |
| color_family | 色系 |
| brand | 品牌 / 來源（之後補充） |
| rgb | RGB 近似值，JSONB 陣列格式 `[R, G, B]`，例如 `[255, 165, 0]` |
| stock_ml | 庫存量（單位：ml）|
| is_active | 是否啟用 |
| created_at | 建立時間 |
| updated_at | 最後更新時間 |

**顏色對應記錄（palette_color_mappings）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| production_job_id | 關聯的製作記錄 |
| template_id | 調色盤色號（1, 2, 3...） |
| algorithm_rgb | 演算法產出的 RGB（JSONB 陣列 `[R, G, B]`）|
| physical_color_id | 對應的實體色 id |
| required_ml | 此規格每套所需顏料量（ml，顏色對應完成後計算儲存）|
| mapped_by | 人工指定 / 系統預設 |
| created_at | 建立時間 |
| updated_at | 最後修改時間 |

**required_ml 計算方式**

顏色對應完成後，系統依以下公式計算並儲存 `required_ml`：

```
required_ml = max(
  畫布面積(cm²) × 該色佔比(%) × paint_ml_per_cm2 × paint_buffer_ratio,
  paint_min_ml
)

畫布面積 = production_job.canvas_w_cm × production_job.canvas_h_cm
該色佔比 = palette_json 中對應 template_id 的 percent
```

> 計算係數（`paint_ml_per_cm2`、`paint_min_ml`、`paint_buffer_ratio`）存於 `system_settings`，管理員可調整。
> `paint_ml_per_cm2` 需實測後填入（測試方法：在已知面積塗色，量前後重量差）。

**歷史對應統計（供「查過往紀錄」使用，可從 palette_color_mappings 查詢）**

- 以 algorithm_rgb（或 LAB 距離相近的色群）為鍵，查詢歷史上對應到哪些 physical_color_id
- 記錄使用次數（從 palette_color_mappings 統計）

**庫存扣減時機與計算**

`physical_colors.stock_ml` 在**訂單建立時（status = `pending_payment`）** 立即扣減，不等付款確認。

```
扣減量 = required_ml × order_item.fulfilled_qty
```

- 使用 `SELECT FOR UPDATE` 鎖住相關 physical_colors 行，防止並發超賣
- 每個 order_item → production_job → palette_color_mappings，逐一對每個 physical_color 執行扣減
- 扣減後 `stock_ml` 立即反映真實可用庫存（已排除所有 pending_payment 中的訂單）
- `preorder_qty` 部分等到庫存補齊、正式備貨時才扣減

**管理員確認付款（→ paid）**

stock_ml 在下單時已扣減，付款確認不再執行扣減動作。

**庫存回補（取消 / 逾期 / 退款）**

以下情況系統回補 stock_ml：

| 情境 | 觸發條件 | 回補範圍 |
|------|---------|---------|
| 逾期未付 | status → `payment_expired`（Celery Beat 自動）| 所有 order_items 的 fulfilled_qty |
| 客戶取消 | status → `cancelled`（付款前，客戶主動）| 所有 order_items 的 fulfilled_qty |
| 管理員取消 | status → `cancelled`（管理員操作）| 所有 order_items 的 fulfilled_qty |
| 退款完成（全額）| status → `refunded` | 所有 order_items 的 fulfilled_qty |
| 退款完成（部分）| status → `partially_refunded` | **僅 is_returned = true** 的 order_items |

```
回補量 = required_ml × order_item.fulfilled_qty（當初扣減的量）
```

- `preorder_qty` 若尚未扣減（庫存還沒補齊），不需回補
- 回補後 `stock_ml` 增加，可能觸發預購等待訂單的庫存補齊通知

**變體可供件數計算**

前台商品頁「是否有現貨」、結帳「庫存拆單」都依此規則計算：

```
可供件數(variant) = min(
  floor(phys.stock_ml / mapping.required_ml)
  for each mapping in variant.production_job.palette_color_mappings
)
```

**說明：**
- 由於 `stock_ml` 在訂單建立（pending_payment）時已扣減，此公式讀到的值**已排除所有進行中訂單佔用的量**，等同「當下真正可用庫存」
- 因此不需要額外查詢 orders 表扣除已佔用量
- 若任一對應實體色 is_active=false（停用）→ 視同庫存 0，該變體一律標示預購

**前台商品狀態顯示：**
- `可供件數 > 0` → 顯示「現貨」
- `可供件數 = 0` → 顯示「預購」
- 所有對應實體色 is_active=false → 顯示「預購」

**結帳庫存拆單：**
- 客戶下單 quantity，若 quantity ≤ 可供件數 → fulfilled_qty = quantity，preorder_qty = 0
- 若 quantity > 可供件數 → fulfilled_qty = 可供件數，preorder_qty = quantity - 可供件數
