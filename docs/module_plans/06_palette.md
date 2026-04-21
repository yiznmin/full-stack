# Module 6：調色板對應（Palette）實作規劃

> 對照規格：`requirements/admin_color.md`、`schema.md`（palette_color_mappings）、`api.md`（模組九）
> 撰寫日期：2026-04-20
> 注意：此模組為 Color 模組（Module 5）的延伸，與 `05_color.md` 合稱「顏色管理」。

---

## 一、要建立的檔案

```
backend/
├── palette/
│   ├── __init__.py
│   ├── router.py             # /admin/production/jobs/{id}/palette-mappings/*
│   ├── service.py
│   ├── models.py             # PaletteColorMapping
│   └── schemas/
│       ├── __init__.py
│       ├── request.py
│       └── response.py
└── tests/
    └── palette/
        ├── __init__.py
        └── test_palette.py
```

---

## 二、DB 模型

### PaletteColorMapping（palette_color_mappings）

| 欄位 | 型別 | 限制 |
|------|------|------|
| id | UUID | PK, default uuid4 |
| production_job_id | UUID | NOT NULL, FK → production_jobs.id |
| template_id | INTEGER | NOT NULL |
| algorithm_rgb | ARRAY(Integer) | NOT NULL（[R, G, B]）|
| physical_color_id | UUID | NOT NULL, FK → physical_colors.id |
| required_ml | NUMERIC(8,4) | nullable |
| mapped_by | ENUM('system','manual') | NOT NULL, DEFAULT 'system' |
| created_at | TIMESTAMP | NOT NULL, server_default now() |
| updated_at | TIMESTAMP | NOT NULL, server_default now() |

**Unique constraint：** (production_job_id, template_id)

---

## 三、Endpoints（palette/router.py）

前綴：`/admin/production/jobs/{job_id}/palette-mappings`

### GET /

**流程：** job 不存在 → 404；若 mappings 為空 → 自動 LAB 對應並建立；回傳所有 mappings（含 color_code, color_name）

### PUT /{template_id}

**Request：** `{ "physical_color_id": uuid }`
**流程：** 驗證 physical_color 存在、template_id 存在；更新 mapped_by='manual', required_ml=null

### POST /copy-from/{source_job_id}

**流程：** source job 不存在 → 404；source 無 mappings → 400；按 template_id 複製，mapped_by='manual', required_ml=null

### POST /complete

**流程：** 驗證所有 template_id 已對應；計算 required_ml；掃描庫存；回傳 all_stocked + shortage_colors

**required_ml 公式：**
```
area = canvas_w_cm × canvas_h_cm
required = max(area × percent × paint_ml_per_cm2 × paint_buffer_ratio, paint_min_ml)
```

---

## 四、LAB 自動對應邏輯

- 使用 `color.service.lab_distance()` 計算距離
- 優先選有庫存（stock_ml > 0）者；全無庫存則選最近似者
- 建立 PaletteColorMapping，mapped_by='system'

---

## 五、測試覆蓋

| 情境 | 預期 |
|------|------|
| GET（空）→ 自動建立 | 200，mappings 數量 = palette_json 顏色數 |
| GET（已存在）→ 不重複建立 | 200 |
| GET palette_json 為空 | 200，[] |
| PUT 更新 mapping | 200，mapped_by=manual，required_ml=null |
| PUT color 不存在 | 404 |
| PUT template_id 不存在 | 404 |
| POST copy-from 有資料 | 200 |
| POST copy-from 無 mappings | 400 |
| POST copy-from 覆寫現有 | 200，正確覆寫 |
| POST copy-from source 不存在 | 404 |
| POST complete 全部有庫存 | 200，all_stocked=true |
| POST complete 有缺貨 | 200，all_stocked=false，shortage_colors 非空 |
| POST complete 無 mappings | 400 |
| POST complete job 不存在 | 404 |
| 所有 endpoints 非 admin | 403 |
| 所有 endpoints 未登入 | 401 |
