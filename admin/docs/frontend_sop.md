# Admin Frontend 開發 SOP

> 後端有完整 SOP（CLAUDE.md「後端實作規則」章節），前端 admin/ 沿用相同精神：
> **規劃 → 對照規格 → 收問題 → 確認無衝突 → 才寫 code**。
> 每個模組（一塊功能）走完整循環。

---

## 1. 模組開始前：必須先寫規劃書（Module Plan）

**在寫任何前端程式碼之前**，必須先在 `admin/docs/module_plans/` 建立規劃書：

```
admin/docs/module_plans/
├── 00_overview.md          # 12 個前端模組總覽與順序
├── F01_app_shell_auth.md
├── F02_dashboard.md
└── FXX_<module_name>.md    # 新模組前必須建立
```

### 命名規則
`FXX_<module_name>.md`，編號 F01–F12 對應 `00_overview.md` 的順序。檔名要能直接對應到 `admin/src/features/<name>/` 目錄。

### 規劃書必須包含

1. **路由清單** — `path → page component`，含 redirect、guard 規則
2. **後端 API 對應表** — 每頁要呼叫哪些 endpoint，直接引 `docs/api.md`
3. **元件樹** — Page → 區塊 (sections) → 共用元件 (shared) → primitives
4. **狀態 / Query 設計**
   - Pinia stores（global）：例：useAuthStore
   - TanStack Query keys：例：`['admin', 'orders', 'list', { page, status }]`
5. **表單 schema** — zod schema（對應後端 request schema），列出每欄位的型別 / 限制 / 顯示文字
6. **設計決策** — 引用 `docs/admin_design_system.md`（一旦建立後）的設計風格、色票、字體；本模組是否有特殊處理（例：dashboard 有資料密度需求所以用更小行高）
7. **手動驗收清單** — 用 chrome-devtools 跑過的 case，含 happy path + 錯誤情境
8. **待確認事項** — 有疑問才列，無則省略

---

## 2. 規劃書完成後：必須產出規格比對報告，才能寫任何程式碼

規劃書寫完後，**禁止直接開始實作**。必須先逐一比對所有規格來源，並貼出以下格式的報告，使用者確認後才能繼續：

```
## 規格比對報告 — F0X <模組名稱>

### 1. api.md 端點比對
| Endpoint | api.md 規定（request/response/status code） | 規劃書對應頁面與處理 | 結果 |
|----------|------------------------------------|-------------------|------|
| ...      | ...                                | ...               | ✓ / ⚠️ |

### 2. requirements/*.md 業務規則比對
| 規則描述 | 來源（檔案:行）| 規劃書對應 UX 行為 | 結果 |
|---------|--------------|-----------------|------|
| ...     | ...          | ...             | ✓ / ⚠️ |

### 3. requirements/admin_routes.md 路由比對
| 規定路由 | 規劃書對應 | 結果 |
|---------|-----------|------|
| ...     | ...       | ✓ / ⚠️ |

### 4. 手動測試覆蓋表
| Case 描述 | 預期結果 | 驗證手段 |
|----------|---------|---------|
| ...      | ...     | screenshot / console / network |

### 5. 差異與待確認
（列出所有 ⚠️，無差異則寫「無」）
```

**此報告未產出、或報告中有未解決的 ⚠️ → 禁止開始寫任何程式碼。**

---

## 3. 分段節奏：每個 page 一個循環

不要一次實作整個模組。每個 route / 主要互動拆成獨立循環：

```
規劃 → 對照規格 → 寫一個 page → 手動驗證 → 通過才繼續下一個 page
```

開始每個階段前，明確說明：
1. 這個階段只做什麼
2. 不做什麼
3. 完成標準是什麼

---

## 4.「完成」的定義（Definition of Done）

一個模組不算完成，直到：

1. **TypeScript 0 錯**：`pnpm type-check` 通過
2. **ESLint 0 錯**：`pnpm lint` 通過（待設定）
3. **Build 成功**：`pnpm build` 無 error / warning
4. **手動驗收**：規劃書中每條 happy path / 錯誤情境，都用 chrome-devtools 截圖驗證並貼回對話
5. **Console 乾淨**：`list_console_messages` 無 error / warn
6. **Network 正常**：登入 / 主要 API 200，無未預期 401 / 500
7. **設計風格一致**：截圖跨頁面比對，色票、間距、字體統一
8. **a11y 基本檢查**（重要頁面）：跑一次 lighthouse_audit，accessibility 分數 ≥ 90
9. **reviewer 審查**：呼叫 /reviewer，無「必須修正」項目

未達成以上前不得宣告完成、不得 commit、不得切下個模組。

**如果覺得某項「不重要」或「可以跳過」，停下來問使用者，不要自己決定。**

---

## 5. 一鍵執行 quality gates

```bash
cd admin && pnpm type-check && pnpm build
```

未來補上 lint / format / E2E（Playwright）後加入。

---

## 6. 對抗式自我審查（每個 page 完成前自問）

- 「使用者最容易在哪一步點壞？網路慢呢？」
- 「這頁 401 / 403 / 500 各會看到什麼？」
- 「F5 reload 會不會掉狀態？」
- 「直接從外部開分頁 paste URL 進來會不會壞？」
- 「鍵盤 Tab 走得通嗎？Esc 關 modal 嗎？」
- 「Mobile 寬度（< 768）爆版嗎？」
- 「設計上哪一處我自己最不確定？為什麼？」

---

## 7. 模組完成後：自動 git commit

reviewer pass 後立即 commit，格式：

```
feat(admin/<module>): 完成 FXX - <模組名稱>
```

例如：`feat(admin/auth): 完成 F01 - App Shell + Admin 認證`

不需等使用者指示，自動執行。

---

## 8. 模組完成後：必須執行回頭驗收（Backward Verification）

reviewer pass、git commit 之前，必須再執行一次回頭驗收，逐一查核：

```
## 回頭驗收報告 — F0X <模組名稱>

### 1. 規劃書路由清單 — 每條路由都實作了嗎？
| 路由 | 預期 | 實作位置 | 結果 |

### 2. api.md endpoint — 每個 API 都接了嗎？
| Endpoint | 規劃書對應 | 實作呼叫位置 | 結果 |

### 3. requirements/*.md 業務規則 — 每條規則都實作了嗎？
| 規則 | 來源 | 實作位置 | 結果 |

### 4. 手動測試覆蓋表 — 每條都驗證了嗎？
| Case | 驗證 screenshot 路徑 / 描述 | 結果 |

### 5. 差異清單
（所有 ⚠️ 必須全部修正後才能 reviewer / commit）
```

---

## 9. 設計風格紀律（frontend-design skill 觸發點）

第一個有實際 UI 的模組（F01）必須**先決定整站設計方向**並寫進 `admin/docs/design_system.md`：

- 整體 tone：極簡 / 編輯感 / 工業感 / 美術館感 / 復古⋯
- 主色票（CSS variable / Tailwind theme）
- 字體選擇（避免 Arial / Inter，挑有意圖的字體）
- 間距 scale（基準單位、layout 間距）
- 動畫哲學（哪些情境動 / 哪些不動）

之後每個模組沿用此設計系統，**不重新發明**。如有局部例外，在該模組規劃書「設計決策」段落明確記錄理由。

---

## 10. 禁止行為

- 寫完說「完成」但沒跑 quality gates
- TypeScript 有 error 卻繼續下個 page
- 只手測 happy path，忽略錯誤情境
- 自行決定跳過任何品質檢查
- 沒呼叫 /reviewer 就宣告模組完成
- reviewer pass 後忘記 git commit
- **規劃書完成後未產出規格比對報告就開始寫 code**
- **規格比對報告有未解決 ⚠️ 就開始寫 code**
- **手動測試覆蓋表未列就開始寫 code**
- **模組完成後未產出回頭驗收報告就呼叫 /reviewer**
- **回頭驗收報告有未修正 ⚠️ 就呼叫 /reviewer 或 git commit**
- **不沿用 design system，每個模組重發明色票 / 字體**
