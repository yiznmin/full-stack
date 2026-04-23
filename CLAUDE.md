# PaintLearn 專案說明（給 Claude Code）

## 專案概述
數字油畫（Paint by Number）平台，提供圖片轉數字油畫模板的製作工具，並透過電商平台販售。

## 技術選型

| 層 | 技術 | 部署 |
|---|---|---|
| 核心處理引擎 | Python（paint-by-number/src/） | Railway Worker |
| 後端 API | FastAPI + PostgreSQL | Railway |
| 任務佇列 | Celery + Redis | Railway |
| 圖片儲存 | Firebase Storage | Firebase |
| Email | Resend（Python SDK）| — |
| 前端（管理介面）| Vue 3 | Vercel |
| 前端（用戶商店）| Vue 3 | Vercel |
| 會員系統 | JWT 自建（httpOnly cookie）| — |

## 資料夾結構

```
PaintLearn/
├── CLAUDE.md
├── docs/
│   ├── requirements.md          # 需求索引
│   ├── requirements/            # 各模組需求細節
│   │   ├── auth_users.md
│   │   ├── pricing_formula.md
│   │   ├── admin_production.md
│   │   ├── admin_color.md
│   │   ├── admin_product.md
│   │   ├── admin_discount.md
│   │   ├── admin_orders.md
│   │   ├── admin_content.md
│   │   ├── admin_notifications.md
│   │   ├── admin_routes.md
│   │   ├── store_routes.md
│   │   └── store/
│   │       ├── store_browse.md
│   │       ├── store_auth.md
│   │       ├── store_orders.md
│   │       ├── store_custom.md
│   │       └── store_info.md
│   ├── schema.md                # 資料庫 schema
│   ├── api.md                   # API 規格（前後端契約）
│   ├── architecture.md          # 整體架構
│   └── backend_conventions.md   # 後端開發規範
├── paint-by-number/             # 核心處理引擎（勿動）
│   └── src/
│       ├── pbn_gen.py
│       └── run.py
├── backend/                     # FastAPI 後端
├── admin/                       # 管理介面（Vue）
└── store/                       # 用戶商店（Vue）
```

## 重要規則

- `paint-by-number/src/` 核心程式碼不隨意修改
- 功能需求索引見 [docs/requirements.md](docs/requirements.md)
- 資料表設計見 [docs/schema.md](docs/schema.md)
- API 規格（前後端契約）見 [docs/api.md](docs/api.md)
- 整體架構見 [docs/architecture.md](docs/architecture.md)
- 後端開發規範見 [docs/backend_conventions.md](docs/backend_conventions.md)

---

## 後端實作規則（強制，不可跳過）

### 模組開始前：必須先寫規劃書（Module Plan）

**在寫任何程式碼之前**，必須先在 `docs/module_plans/` 建立規劃書：

```
docs/module_plans/
├── 01_auth.md
├── 02_users_shipping.md
└── XX_<module_name>.md   ← 新模組前必須建立
```

規劃書命名規則：`XX_<module_name>.md`，檔名必須包含後端模組目錄名稱（例如 `users`、`auth`）。

規劃書必須包含：
1. 要建立的檔案清單
2. DB 模型（欄位、型別、限制）
3. 每個 endpoint 的 request / response / 業務流程
4. **EVENT_MATRIX 對照**：列出本模組涉及的所有 Event（E01、E02...），確認每個 Event 的副作用（DB 寫入、Email、通知、自動觸發）均已在業務流程中列出
5. 測試覆蓋範圍清單
6. 待確認事項（有疑問才列，無則省略）

**EVENT_MATRIX 規則**：寫規劃書前必須先讀 `docs/EVENT_MATRIX.md`，對照本模組觸發的 Event，確認所有副作用均已包含在規劃書中。漏寫副作用（Email、通知、狀態變更）等同規劃書不完整。

**quality_check.py Gate 5 會驗證**：每個有 `router.py` 的模組目錄，`docs/module_plans/` 裡必須存在包含該模組名稱的 `.md` 檔案。Gate 5 不通過等同 quality gate 失敗。

---

### 規劃書完成後：必須產出規格比對報告，才能寫任何程式碼

規劃書寫完後，**禁止直接開始實作**。必須先逐一比對所有規格來源，並在對話中貼出以下格式的完整報告，使用者確認後才能繼續：

```
## 規格比對報告 — Module XX <模組名稱>

### 1. schema.md 欄位比對
| 資料表 | 欄位 | schema 規定（型別/限制/預設） | 規劃書對應 | 結果 |
|--------|------|-------------------------------|-----------|------|
| ...    | ...  | ...                           | ...       | ✓ / ⚠️差異：... |

### 2. requirements/*.md 業務規則比對
| 規則描述 | 來源（檔案:行） | 規劃書對應邏輯 | 結果 |
|---------|--------------|--------------|------|
| ...     | ...          | ...          | ✓ / ⚠️差異：... |

### 3. api.md 格式比對
| Endpoint | api.md 規定（request/response） | 規劃書 schema | 結果 |
|----------|--------------------------------|--------------|------|
| ...      | ...                            | ...          | ✓ / ⚠️差異：... |

### 4. 測試 case 完整列表
（逐條列出 module plan 測試覆蓋表的每個 case，確認對應到將要撰寫的測試函數名稱）
| Case 描述 | 預期狀態碼 | 測試函數名稱 |
|----------|-----------|------------|
| ...      | ...       | ...        |

### 5. 差異與待確認
（列出所有 ⚠️ 項目，有疑問先問使用者，無差異則寫「無」）
```

**此報告未產出、或報告中有未解決的 ⚠️差異 → 禁止開始寫任何程式碼。**

### 分段節奏：每個 endpoint 一個循環

不要一次實作整個模組。每個 endpoint 或功能點獨立循環：

```
實作一個 endpoint → 寫對應測試 → 跑 quality gates → 通過才繼續下一個
```

開始每個階段前，明確說明：
1. 這個階段只做什麼
2. 不做什麼
3. 完成標準是什麼

### 「完成」的定義（Definition of Done）

一個功能不算完成，直到：

1. **測試通過**：`pytest tests/{module}/ -v` 全部 PASSED
2. **測試涵蓋**：happy path、錯誤路徑、邊界情況各至少 1 個
3. **Lint 通過**：`ruff check .` 無錯誤
4. **安全掃描**：`bandit -c pyproject.toml -r .` 無 medium+ 問題
5. **手動驗收**：實際打過 Swagger UI 或 curl，貼出實際回應
6. **reviewer 審查**：呼叫 `/reviewer` sub-agent 審查，無「必須修正」項目

在滿足以上所有條件之前，不可以說「完成了」，不可以開始下一個功能。

**如果覺得某個測試「不重要」或某個檢查「可以跳過」，停下來問使用者，不要自己決定。**

### 一鍵執行所有 quality gates

```bash
cd backend && venv/Scripts/python scripts/quality_check.py
```

quality_check.py 包含四道閘門：
- Gate 1：Ruff（lint & style）
- Gate 2：Bandit（security scan）
- Gate 3：static_review.py（專案規則：response_model、AppError、測試目錄存在、token hashing）
- Gate 4：Pytest（所有測試）

**當 quality_check.py 輸出 "REQUIRED NEXT ACTION: /reviewer" 時，你必須立刻執行：**
```
/reviewer
```
這不是選項，是強制步驟。不得跳過，不得繼續下一個功能。

### 對抗式自我審查（每次完成前自問）

- 「這個 endpoint 最可能在什麼情況下壞掉？」
- 「惡意使用者可以怎麼利用這個 endpoint？」
- 「如果 DB 斷線，這段程式會發生什麼事？」
- 「我有沒有為了讓測試通過而簡化邏輯？」
- 「哪一行我自己最不確定？為什麼？」

### 模組完成後：自動 git commit

reviewer 呼叫 `clear_review.py pass` 後，立即執行 git commit，格式：

```
feat(<module>): 完成 Module XX - <模組名稱>（N tests passing）
```

例如：`feat(palette): 完成 Module 06 - 調色板對應（36 tests passing）`

不需等使用者指示，自動執行。

### 模組完成後：必須執行回頭驗收（Backward Verification）

reviewer pass、git commit 之前，必須再執行一次**回頭驗收**，確認已實作內容完全符合所有規格來源。逐一查核以下四層，並在對話中貼出結果：

```
## 回頭驗收報告 — Module XX <模組名稱>

### 1. schema.md — 每個欄位都實作了嗎？
（逐欄確認型別、限制、預設值、onupdate 等細節與程式碼一致）
| 資料表.欄位 | schema 規定 | 實際程式碼 | 結果 |
|------------|------------|-----------|------|
| ...        | ...        | ...       | ✓ / ⚠️ |

### 2. requirements/*.md — 每條業務規則都實作了嗎？
（逐條比對，包含錯誤情境、邊界條件、禁止行為）
| 規則 | 來源 | 實作位置 | 結果 |
|------|------|---------|------|
| ...  | ...  | ...     | ✓ / ⚠️ |

### 3. api.md — 每個 endpoint 的格式完全正確嗎？
（request 欄位、response 欄位、status code 逐一核對）
| Endpoint | api.md 規定 | 實作 | 結果 |
|----------|------------|------|------|
| ...      | ...        | ...  | ✓ / ⚠️ |

### 4. module_plan 測試覆蓋表 — 每個 case 都寫了測試嗎？
（逐條核對，包含 happy path、錯誤路徑、邊界情況）
| Case 描述 | 測試函數 | 結果 |
|----------|---------|------|
| ...      | ...     | ✓ / ⚠️ 缺漏 |

### 5. 差異清單
（所有 ⚠️ 項目，必須全部修正後才能進行 reviewer）
```

**此報告未產出、或有未修正的 ⚠️ → 禁止呼叫 /reviewer、禁止 git commit。**

---

### 禁止行為
- 寫完說「完成」但沒跑 quality gates
- 測試有 FAILED 卻繼續下一個功能
- 只測 happy path，忽略錯誤情境
- 自行決定跳過任何品質檢查
- 沒呼叫 `/reviewer` 就宣告模組完成
- reviewer pass 後忘記 git commit
- **規劃書完成後未產出規格比對報告就開始寫程式**
- **規格比對報告有未解決 ⚠️ 項目就開始寫程式**
- **測試覆蓋表未逐條對應測試函數名稱就開始寫測試**
- **模組完成後未產出回頭驗收報告就呼叫 /reviewer**
- **回頭驗收報告有未修正 ⚠️ 就呼叫 /reviewer 或 git commit**
