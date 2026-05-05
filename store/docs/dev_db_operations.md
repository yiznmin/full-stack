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
