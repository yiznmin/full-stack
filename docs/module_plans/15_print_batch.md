# Module 15 - 列印批次（print_batch）

> Admin 把多張畫合併送印給廠商，避免單張畫被 200/100 元最低消費浪費。系統算最划算的補單組合、產出送印 PDF。

---

## 1. 商業背景

廠商計費：
- 一才 = 長(cm) × 寬(cm) ÷ 900
- 列印單價 35 元/才，最低 200 元
- 裁切單價 5 元/才，最低 100 元
- 每張畫四周留白 5cm（含邊；兩張並排時相鄰邊各 5cm 共 10cm 間距）

「不浪費」門檻：
- 列印 → 200/35 = **5.71 才**
- 裁切 → 100/5 = **20 才**
- 整單 ≥ 20 才才能讓兩個下限都被「真實才數」蓋住，每塊錢都對應實際印製面積

合併送印的目的：把好幾張小畫攤到 ≥ 20 才，讓基本費被分攤掉。

---

## 2. 檔案清單

新建：
- `backend/print_batch/__init__.py`
- `backend/print_batch/models.py` — `PrintBatch`、`PrintBatchItem`
- `backend/print_batch/router.py`
- `backend/print_batch/service.py` — 計費、補單演算、PDF 生成
- `backend/print_batch/schemas/__init__.py`
- `backend/print_batch/schemas/request.py`
- `backend/print_batch/schemas/response.py`
- `backend/migrations/versions/i9d0e1f2g3h4_create_print_batch.py`
- `backend/tests/print_batch/__init__.py`
- `backend/tests/print_batch/test_print_batch.py`

修改：
- `backend/main.py`（註冊 router）
- `backend/migrations/env.py`、`scripts/{reset,drop}_test_db.py`、`tests/conftest.py`（import 新 models）
- `backend/requirements.txt`：新增 `svglib`、`reportlab`、`Pillow`、`cairosvg`（PDF 與 SVG 處理）

---

## 3. DB 模型

### print_batches

| 欄位 | 型別 | 限制 |
|---|---|---|
| id | UUID | PK |
| status | Enum('draft','finalized') | NOT NULL DEFAULT 'draft' |
| total_inch_count | NUMERIC(10,2) | NOT NULL — 整單實際才數（ceil 後）|
| billable_inch_count | NUMERIC(10,2) | NOT NULL — 套用下限後計費才數 |
| print_cost | NUMERIC(10,2) | NOT NULL |
| cut_cost | NUMERIC(10,2) | NOT NULL |
| total_cost | NUMERIC(10,2) | NOT NULL |
| pdf_url | VARCHAR | nullable（finalize 後才有）|
| admin_notes | TEXT | nullable |
| created_by_user_id | UUID FK→users.id | nullable ON DELETE SET NULL |
| created_at | TIMESTAMP | NOT NULL DEFAULT now() |
| finalized_at | TIMESTAMP | nullable |

### print_batch_items

| 欄位 | 型別 | 限制 |
|---|---|---|
| id | UUID | PK |
| print_batch_id | UUID FK→print_batches.id ON DELETE CASCADE | NOT NULL |
| source_type | Enum('order_item','standalone') | NOT NULL |
| source_order_item_id | UUID FK→order_items.id ON DELETE SET NULL | nullable（若 source_type=order_item）|
| production_job_id | UUID FK→production_jobs.id | NOT NULL |
| quantity | INTEGER | NOT NULL CHECK >= 1 |
| inch_per_unit | NUMERIC(10,4) | NOT NULL — 單張展開後才數（含留白）|
| canvas_w_cm | NUMERIC(6,1) | NOT NULL — 快照避免後續 production_job 變動影響（與 production_jobs 同精度，允許 30.5cm 等小數） |
| canvas_h_cm | NUMERIC(6,1) | NOT NULL |

---

## 4. 計費演算

```python
def inch_per_unit(w: int, h: int) -> Decimal:
    """單張展開含留白後的才數（小數，整單加總後才 ceil）。"""
    return Decimal((w + 10) * (h + 10)) / Decimal(900)

def total_billing(items) -> dict:
    raw = sum(item.inch_per_unit * item.quantity for item in items)
    billable = ceil(raw)                              # 整單向上取整
    print_cost = max(billable * 35, 200)
    cut_cost = max(billable * 5, 100)
    return {
        "total_inch_count": raw,
        "billable_inch_count": billable,
        "print_cost": print_cost,
        "cut_cost": cut_cost,
        "total_cost": print_cost + cut_cost,
    }
```

---

## 5. 補單建議演算

目標：必印才數 + 候選 ≥ **20 才**（脫離兩個下限），且總才數**最接近 20**（不浪費）。

```python
def suggest_combos(required_inch, candidates) -> list[dict]:
    """產 3 組建議：
    - (1) 單一品項補滿（只挑 1 種畫，數量最少能達門檻）
    - (2) 大尺寸貪心（從大到小裝直到 ≥ 20）
    - (3) 小尺寸貪心（從小到大裝直到 ≥ 20）
    每組附 [{job_id, qty}]、總才、浪費才、總費用。
    """
```

不做完整 subset-sum DP（候選 < 200 種、每次組合不會多，貪心夠用）。

---

## 6. Endpoints

```
POST /admin/print-batches/preview
  body: { required: [{prod_job_id, qty}], candidates?: [{prod_job_id, qty}] }
  response: {
    required_inch_count, billable_inch_count,
    waste_inch,  # max(0, 20 - billable)
    cost_breakdown: {print, cut, total},
    suggestions: [...3 種建議組合],
    available_candidates: [{prod_job_id, product_title, w, h, inch_per_unit}, ...]
  }

GET /admin/print-batches/candidates
  response: { items: [{prod_job_id, product_title, w, h, inch_per_unit}, ...] }

POST /admin/print-batches  
  body: { required, candidates?, admin_notes? }
  status_code: 201
  response: PrintBatchDetailResponse  # status='draft', pdf_url=null

POST /admin/print-batches/{id}/finalize
  response: PrintBatchDetailResponse  # status='finalized', pdf_url=<url>
  - 從 production_jobs.svg_url 抓每張 SVG
  - 用 svglib + reportlab 拼到一份 PDF（含 5cm 留白、相鄰共享 10cm）
  - 上傳到 Firebase Storage（stub 模式 → mock URL，與 Module 14 上傳一致）
  - 寫 pdf_url + finalized_at
  - **不**寄 email、**不**動 production_progress

GET /admin/print-batches  
  query: ?status=&page=&page_size=
  response: { items, total, page, page_size }

GET /admin/print-batches/{id}
  response: PrintBatchDetailResponse
```

---

## 7. PDF 生成

工具：`svglib`（SVG → ReportLab Drawing）+ `reportlab`（PDF canvas）+ `Pillow`（必要時 raster fallback）+ `httpx`（從 Firebase Storage 下載 SVG）。

策略：
1. 對每個 print_batch_item，下載 svg_url（async httpx）
2. 用 svglib 把 SVG 轉成 reportlab Drawing
3. 計算 layout：簡單橫式排版（左→右滿了換行）
   - 每張 cell 大小 = (w + 10) × (h + 10) cm
   - 紙張無上限，整份 PDF 為單頁
4. 把每張畫貼到對應位置
5. 輸出 BytesIO → Firebase Storage（stub）→ 回 URL

Fallback：若 svglib 無法解析某 SVG，用 CairoSVG 將 SVG → PNG 後貼上（向量變點陣，可接受）。

---

## 8. 資料來源

- **必印**：admin 從 UI 勾選
  - (a) 待備貨訂單的 OrderItem（即 `order.status IN [paid, processing]` 且 `OrderItem.fulfilled_qty > 0` 但 progress 仍在 pending/in_production 階段）
  - (b) admin 手選 production_job + 數量（不綁訂單，純囤印）
- **候選池**：所有「目前架上」的款式
  - `Product.status='on_sale'` AND `ProductVariant.is_active=True` 對應的 production_job
  - 不去重、不排除（依使用者決議）

---

## 9. 不做的事

- 不寄客戶 email
- 不動 production_progress / order.status
- 不檢查「已在另一 draft batch 內」，admin 自己看著辦（可後續優化）
- 不做完整 2D 裝箱排版（紙張無上限，順序排即可）
- 不做 SAM mask、不動 paint-by-number/src/

---

## 10. EVENT_MATRIX

不觸發任何 Event。純內部計費 + PDF 生成。

---

## 11. 測試覆蓋

| Case | 預期 | 函數 |
|---|---|---|
| 計費公式 16 才 → 660 | 對應 | test_total_billing_below_floor |
| 計費 30 才 → 1050+150=1200 | 對應 | test_total_billing_above_floor |
| inch_per_unit 30×40 = 2.222 才 | 對應 | test_inch_per_unit |
| Preview required-only 算正確 | 對應 | test_preview_required_only |
| Preview required + candidates 算正確 | 對應 | test_preview_with_candidates |
| Suggest combos 大尺寸組合 | 對應 | test_suggest_largest_first |
| Suggest combos 不夠補滿時回空建議 | 對應 | test_suggest_no_feasible_combo |
| GET candidates 只列 on_sale + active | 對應 | test_candidates_filter |
| POST batch draft（不產 PDF）| 201 + status=draft | test_create_batch_draft |
| Finalize 產 PDF（stub Firebase）| pdf_url 被填 | test_finalize_creates_pdf |
| Finalize 不動 production_progress | progress 不變 | test_finalize_does_not_touch_progress |
| Finalize 不寄 email | email log 沒記錄 | test_finalize_no_email |
| Finalize draft 後再 finalize 拒絕 | 400 | test_finalize_already_finalized_rejected |
| 非 admin GET / POST 全部 | 401 / 403 | test_print_batch_admin_only |
| GET list 分頁 | 對應 | test_list_pagination |
| Candidates 空時 preview 仍可（純必印計算）| 對應 | test_preview_no_candidates |

---

## 12. ⚠️ 待確認項目

### A. PDF 生成 fallback 策略
若 production_jobs.svg_url 為 null（製作未完成）→ skip 該 item，回部分產出 + 警告？或拒絕 finalize？  
**預設**：拒絕 finalize，回 400 + code=`SVG_NOT_READY`。

### B. PDF 生成失敗（最保策略 — 永不阻擋 finalize）
網路抓 SVG 失敗、SVG 解析失敗 → 走三層 fallback，finalize 永遠成功；任一層觸發都會 `logger.warning`。  

**最終決策**：
- Layer 1（svglib 向量）→ Layer 2（cairosvg PNG）→ Layer 3（placeholder 黑框）
- 即使所有 SVG 都不可解析，仍輸出含黑框的 PDF（admin 可印出後手畫補救）
- 每張走 placeholder 都會記 `WARNING ⚠️ ... 走 placeholder 佔位框 — 列印品質受影響`
- finalize 不 rollback；admin 透過 logs 監控品質

理由：印刷批次以準時上機為優先，寧可印「不完美但能印」的 PDF 也不要因單張 SVG 異常卡整批；若品質不可接受，admin 從 logs 抓 svg_url 修圖後重新建一筆 batch。

### C. requirements.txt 新增依賴
- `svglib==1.5.1` (Apache 2.0) — 主路徑，輸出 reportlab Drawing（向量）
- `reportlab==4.2.5` (BSD) — PDF 拼版
- `Pillow==11.0.0` (HPND) — PNG 載入給 reportlab
- `cairosvg==2.7.1` (LGPL) — 第二層 fallback；svglib 解析失敗時 rasterize 為 PNG @ 300 DPI
- `httpx` (已有)

**最終決策**：採三層 fallback（最保策略）
1. svglib（向量、最佳品質）
2. cairosvg → PNG @ 300 DPI（救援複雜 SVG，需 cairo C 庫）
3. 佔位黑框（最後保險，至少能印）

部署面：Linux base image 通常 `apt-get install libcairo2`；Railway / Docker 已驗證。

---

確認 OK 我開始寫程式。或哪邊還要調整？
