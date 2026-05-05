# Dev DB 操作記錄

> 開發過程中對 Railway production DB 做的手動操作（seed / patch / cleanup）一律記在這裡。
> 規則：[memory `feedback_no_fake_data.md`](../../C:/Users/yizhen/.claude/projects/d--website-PaintLearn/memory/feedback_no_fake_data.md) — 前端禁止寫死假資料；DB 沒資料時可手動 seed 真實資料，但必須記錄到本檔。

---

## 模板

每筆記錄包含：

```markdown
### YYYY-MM-DD HH:MM — <簡短描述>

**目的**：為什麼要做（哪個 stage / 哪個 page 需要這份資料）
**方式**：SQL / admin API / 後端 script
**影響的表**：themes / products / users / ...
**操作內容**：
\`\`\`sql
INSERT INTO themes (id, name, ...) VALUES (...);
\`\`\`
或
\`\`\`bash
curl -X POST http://localhost:8001/api/v1/admin/themes ...
\`\`\`
**回滾方式**：如何刪除這份資料（DELETE FROM ... WHERE id = ...）
```

---

## 操作記錄

（按日期由新到舊）

### 2026-05-05 — 初始檔案建立

尚無實際操作。S01 階段如果發現 Railway DB 主題 / 商品 / 客製案例為空、影響 mega-menu / 列表頁顯示「建設中」狀態，會在此補真實 seed 操作。

---

### 2026-05-05 16:30 — Series Featured Epic：修補 production DB schema migration

**目的**：BE-Featured 部署後 admin 新增系列回 500「伺服器內部錯誤」。診斷發現 production `start_web.sh` 跑 `init_db.py` → `alembic stamp head`（只更新版本表、不執行 ALTER TABLE），`product_series` 表從沒被真實 migrate，導致 ORM `SELECT product_series.is_featured` 報 `column does not exist`。

**方式**：alembic CLI（透過 Railway public proxy）

**影響的表**：`product_series`（加 `is_featured BOOLEAN NOT NULL DEFAULT false` 欄位）、`alembic_version`（推到 k1f2g3h4i5j6）

**操作內容**：

```powershell
# 1. 連 production DB（透過 Railway public proxy）
$env:DATABASE_URL = "postgresql+asyncpg://postgres:***@switchyard.proxy.rlwy.net:25293/railway"

# 2. stamp 退回上一版（alembic_version 表先前被 init_db.py 誤標到 head 但沒 ALTER）
python -m alembic stamp 76e1a6c1267e

# 3. real upgrade（這次會真的執行 ALTER TABLE）
python -m alembic upgrade head
# → Running upgrade 76e1a6c1267e -> k1f2g3h4i5j6, add product_series.is_featured
```

**驗證**：
- `GET /api/v1/series` → 200
- `GET /api/v1/admin/series` → 200
- `POST /api/v1/admin/series` 帶 `is_featured: false` → 201 + response 含 `is_featured`

**回滾方式**：
```sql
ALTER TABLE product_series DROP COLUMN is_featured;
UPDATE alembic_version SET version_num = '76e1a6c1267e';
```

**測試殘留資料清理**：建立測試系列 id=27ecdb72-55e8-4d4d-b6be-73253beacfbe（name=TEST_AFTER_FIX_8824）→ 已 DELETE 清除。

**長期問題與後續行動**：
- `start_web.sh` 的 TODO（[start_web.sh:11](../../backend/scripts/start_web.sh#L11)）「補 alembic upgrade head」應該補上，否則未來新 migration 會重複此問題。
- 建議改成：先跑 `alembic upgrade head`（套用 migration） → 再跑 `init_db.py`（safety net create_all + stamp）。

---

### 2026-05-05 17:30 — 為 S02 M1 HomePage 視覺驗收 seed 主題/系列/標籤

**目的**：S02 HomePage 已實作完成，但 production DB 主題/系列/標籤幾乎空（user 只建過 1 個系列「貓咪日常」），無法驗證主題瀏覽 section / 精選系列 chips / 商品 mega-menu 三欄篩選等視覺效果。Products 需要 paint-by-number engine 處理真實圖片，必須由 user 在 admin 後台流程建（上傳圖 → production_job approve → 建商品 → 加 variants），這次 seed 不含 products。

**方式**：admin API（`POST /api/v1/admin/themes` / `/admin/series` / `/admin/tags`），透過 admin login session（yizn.min@gmail.com）

**影響的表**：`themes` / `product_series` / `tags`

**操作內容**：

```
[theme] 風景      -> 219ec985-42a7-414f-b7df-6be9cbb7be1d
[theme] 萌寵      -> febef0e1-80c1-41a3-ad58-b8826da9be22
[theme] 藝術畫    -> 109c52d7-8127-42d7-89a9-09110dfaeebf
[theme] 人物      -> 858056fa-5fee-4a9d-a606-13f23d189294

[series] 京都四季 (featured=True, 風景)   -> 6d3a0dc1-6083-4187-b1ee-7ab640d80a58
[series] 海岸印象 (風景)                  -> 9605b792-a7d9-445e-88d5-34ca6ac36358
[series] 浪犬與牠 (featured=True, 萌寵)   -> 38ff8d67-5bba-43fa-a493-03ae9de46fca
[series] 印象派經典 (featured=True, 藝術畫) -> 03feca0f-6604-4571-b69f-122550107bca
[series] 親愛的家人 (人物)                -> fb26a790-8d67-4233-9d4a-bee77c440b1d

[tag] 療癒         -> cb0ea2c7-3403-4e52-83cf-11d896b0b882
[tag] 送禮首選     -> 23854b49-f7e9-4de3-92af-697452e790cc
[tag] 節慶限定     -> 68f627af-9e60-45d3-bb02-f6edc2daab69
[tag] 新手友善     -> 10b26967-189f-4707-87c0-ca5debb43052
[tag] 大師之作     -> e8987625-e773-4c0d-ae48-976d0176f425
[tag] 居家裝飾     -> eb1a5f36-2bd2-4a87-8e1b-b83eda2d7e24
[tag] 紀念珍藏     -> cec9205d-325e-49e5-81be-b35af63e9d45
[tag] 動物題材     -> 55124bb8-f6f8-4743-8b56-8b63419197a4
```

**驗證**：
- store HomePage：主題瀏覽 4 卡片、精選系列 chips（京都四季 / 浪犬與牠 / 印象派經典 / 貓咪日常）
- 商品 mega-menu：依系列 5 個（含 user 既有「貓咪日常」共 6）/ 依標籤 8 個 / 依難易度 4 個
- 主題 mega-menu：4 主題

**回滾方式**（admin 後台「刪除」按鈕逐一刪，或 SQL）：
```sql
DELETE FROM tags WHERE name IN ('療癒','送禮首選','節慶限定','新手友善','大師之作','居家裝飾','紀念珍藏','動物題材');
DELETE FROM product_series WHERE name IN ('京都四季','海岸印象','浪犬與牠','印象派經典','親愛的家人');
DELETE FROM themes WHERE name IN ('風景','萌寵','藝術畫','人物');
```

**Products 由 user 自建**：cover_image_url + variants 都需要實際 paint-by-number engine 跑過的真資料，不能 SQL 直接 INSERT。User 在 admin 後台建商品流程：
1. 上傳原圖 → admin/production/jobs（PBN engine 處理）
2. Job approved 後 → POST /admin/products
3. 商品建好 → 加 variants（從 approved jobs 選對應的）
