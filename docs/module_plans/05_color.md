# Module 5：顏色管理（Color）實作規劃

> 對照規格：`requirements/admin_color.md`、`schema.md`（physical_colors、palette_color_mappings、system_settings）、`api.md`（模組八、模組九）
> 撰寫日期：2026-04-20

---

## 一、要建立的檔案

```
backend/
├── color/
│   ├── __init__.py
│   ├── router.py             # 模組八：/admin/colors/*
│   ├── service.py
│   ├── models.py             # PhysicalColor、SystemSetting
│   └── schemas/
│       ├── __init__.py
│       ├── request.py
│       └── response.py
├── palette/
│   ├── __init__.py
│   ├── router.py             # 模組九：/admin/production/jobs/{id}/palette-mappings/*
│   ├── service.py
│   ├── models.py             # PaletteColorMapping
│   └── schemas/
│       ├── __init__.py
│       ├── request.py
│       └── response.py
└── tests/
    ├── color/
    │   ├── __init__.py
    │   └── test_color.py
    └── palette/
        ├── __init__.py
        └── test_palette.py
migrations/versions/
    ├── XXXX_create_physical_colors.py
    ├── XXXX_create_system_settings.py
    └── XXXX_create_palette_color_mappings.py
```

---

## 二、DB 模型

### PhysicalColor（physical_colors）

| 欄位 | 型別 | 限制 |
|------|------|------|
| id | UUID | PK, default uuid4 |
| code | VARCHAR | NOT NULL, UNIQUE |
| name | VARCHAR | NOT NULL |
| color_family | VARCHAR | nullable |
| brand | VARCHAR | nullable |
| rgb | JSONB | NOT NULL（`{"rgb_r":int, "rgb_g":int, "rgb_b":int}`）|
| stock_ml | NUMERIC(10,2) | NOT NULL, DEFAULT 0 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true |
| created_at | TIMESTAMP | NOT NULL, server_default now() |
| updated_at | TIMESTAMP | NOT NULL, server_default now(), onupdate now() |

### SystemSetting（system_settings）

| 欄位 | 型別 | 限制 |
|------|------|------|
| key | VARCHAR | PK |
| value | TEXT | NOT NULL |
| updated_at | TIMESTAMP | NOT NULL, server_default now() |

### PaletteColorMapping（palette_color_mappings）

| 欄位 | 型別 | 限制 |
|------|------|------|
| id | UUID | PK, default uuid4 |
| production_job_id | UUID | NOT NULL, FK → production_jobs.id |
| template_id | INTEGER | NOT NULL |
| algorithm_rgb | ARRAY(Integer) | NOT NULL（長度 3：[R, G, B]）|
| physical_color_id | UUID | NOT NULL, FK → physical_colors.id |
| required_ml | NUMERIC(8,4) | nullable |
| mapped_by | ENUM('system','manual') | NOT NULL, DEFAULT 'system' |
| created_at | TIMESTAMP | NOT NULL, server_default now() |
| updated_at | TIMESTAMP | NOT NULL, server_default now() |

**Unique constraint：** (production_job_id, template_id)

---

## 三、模組八 Endpoints（color/router.py）

### GET /admin/colors

**Query：** `color_family`, `is_active`, `search`（code 或 name 關鍵字）

**Response 200：** `{ "items": [PhysicalColorResponse] }`（無分頁，色庫通常 < 200 筆）

---

### POST /admin/colors

**Request：** `{ "code", "name", "color_family"|null, "brand"|null, "rgb": {rgb_r, rgb_g, rgb_b}, "stock_ml": 0 }`

**驗證：** code 不可重複（409），rgb 各值 0–255，stock_ml >= 0

**Response 201：** PhysicalColorResponse

---

### PUT /admin/colors/{id}

**Request：** 同 POST（全量更新）

**驗證：** code 不可與其他 color 重複（排除自身）

**Response 200：** PhysicalColorResponse

---

### PATCH /admin/colors/{id}/toggle-active

**流程：** 切換 `is_active`（true↔false）

**Response 200：** PhysicalColorResponse

---

### PATCH /admin/colors/{id}/stock

**Request：** `{ "add_ml": float }` （> 0）

**流程（Phase stub）：**
1. `stock_ml += add_ml`
2. 預購掃描留空（Orders 模組建完後補）
3. 回傳 `{ "new_stock_ml": float, "fulfilled_orders": 0 }`

**Response 200：** `{ "new_stock_ml": float, "fulfilled_orders": int }`

---

### GET /admin/colors/shortage-dashboard

**流程：** 查所有 is_active=true 顏色，計算各顏色的預購待備量（來自 palette_color_mappings + 未出貨訂單）。Orders 未建前回傳空 waiting_orders=0。

**Response 200：** `{ "items": [ShortageItem] }`（僅顯示 shortage_ml > 0）

---

## 四、模組九 Endpoints（palette/router.py）

### GET /admin/production/jobs/{id}/palette-mappings

**流程：**
1. job 不存在 → 404
2. 若 palette_color_mappings 為空 → 自動執行 LAB 自動對應（建立記錄）
3. 回傳所有 mappings 含 physical_color 完整資訊

**LAB 自動對應邏輯：**
- 讀取 job.palette_json 的每個 template_id 與 RGB
- 對所有 is_active=true 的 physical_colors 計算 LAB 距離
- 取距離最小且 stock_ml > 0 者；若全無庫存則取距離最小者
- 建立 PaletteColorMapping 記錄（mapped_by='system'）

**Response 200：** `{ "mappings": [PaletteMappingResponse] }`

---

### PUT /admin/production/jobs/{id}/palette-mappings/{template_id}

**Request：** `{ "physical_color_id": "uuid" }`

**驗證：** physical_color 存在（404），template_id 存在於此 job（404）

**流程：** 更新 physical_color_id，mapped_by='manual'，清空 required_ml

**Response 200：** PaletteMappingResponse

---

### POST /admin/production/jobs/{id}/palette-mappings/copy-from/{source_job_id}

**流程：**
1. source_job 不存在 → 404
2. source_job 無 mappings → 400
3. 按 template_id 複製（目前 job 有相同 template_id 者覆寫）
4. mapped_by='manual'，required_ml=null（未重新計算）

**Response 200：** `{ "mappings": [PaletteMappingResponse] }`

---

### POST /admin/production/jobs/{id}/palette-mappings/complete

**前置條件：** 所有 template_id 均已對應（若有缺失 → 400）

**流程：**
1. 讀取 system_settings: paint_ml_per_cm2, paint_min_ml, paint_buffer_ratio
2. 對每個 mapping 計算 required_ml
3. 掃描所有 physical_color 庫存：
   - 全部有庫存 → `all_stocked: true`
   - 有缺 → `all_stocked: false`，回傳 shortage_colors 列表

**required_ml 公式：**
```
area = job.canvas_w_cm × job.canvas_h_cm
percent = palette_json 中 template_id 的 percent
required_ml = max(area × percent × paint_ml_per_cm2 × paint_buffer_ratio, paint_min_ml)
```

**Response 200：** `{ "all_stocked": bool, "shortage_colors": [{ "template_id", "physical_color_id", "code", "name" }] }`

---

## 五、LAB 色彩轉換（color/service.py）

```python
def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    # sRGB → linear → XYZ → LAB
    # D65 白點，使用標準公式，不需外部 library

def _lab_distance(lab1, lab2) -> float:
    # 歐氏距離

def auto_map_colors(palette_json, physical_colors) -> list[dict]:
    # 對每個 template_id 找最近似有庫存的實體色
```

---

## 六、測試覆蓋

### 模組八（test_color.py）

| 情境 | 預期 |
|------|------|
| GET 色庫（有資料）| 200，正確回傳 |
| GET 按 color_family 篩選 | 200，只回傳指定色系 |
| GET 按 is_active 篩選 | 200，只回傳啟用/停用 |
| POST 建立色條目 | 201 |
| POST code 重複 | 409 |
| POST rgb 值超範圍 | 422 |
| PUT 全量更新 | 200 |
| PATCH toggle-active | 200，is_active 切換 |
| PATCH stock add_ml=500 | 200，stock_ml 增加，fulfilled_orders=0（stub）|
| PATCH stock add_ml<=0 | 422 |
| GET shortage-dashboard | 200 |
| 所有 endpoints 非 admin | 403 |
| 所有 endpoints 未登入 | 401 |

### 模組九（test_palette.py）

| 情境 | 預期 |
|------|------|
| GET mappings（空）→ 自動建立 | 200，mappings 數量 = palette_json 顏色數 |
| GET mappings（已存在）→ 不重複建立 | 200 |
| PUT 更新單一 mapping | 200，mapped_by=manual |
| PUT physical_color 不存在 | 404 |
| PUT template_id 不存在 | 404 |
| POST copy-from source 有 mappings | 200，目前 job mappings 被覆寫 |
| POST copy-from source 無 mappings | 400 |
| POST complete（全部對應）| 200，required_ml 計算正確 |
| POST complete（有缺對應）| 400 |
| 所有 endpoints 非 admin | 403 |
| 所有 endpoints 未登入 | 401 |
