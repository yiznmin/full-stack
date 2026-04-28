# Admin Frontend 模組總覽

> 12 個前端模組，鏡映後端 15 個模組之中與 admin 相關者。每個模組都走 `frontend_sop.md` 的完整流程：規劃書 → 規格比對 → 實作 → 回頭驗收 → reviewer → commit。

---

## 模組順序與相依關係

```
F01 app_shell_auth   ── 所有後續模組的入口（layout、guard、認證）
   │
   ├─ F02 dashboard          ── 進入點，可暫時放靜態 hello
   ├─ F03 products           ── CRUD 重，先做累積經驗
   ├─ F04 orders             ── 最重的工作流程，奠定列表+詳情範本
   │  └─ 沿用範本：
   │     F05 custom_requests
   │     F06 production
   │     F08 discounts
   │     F09 notifications
   │     F12 print_batches
   │
   ├─ F07 colors_palette     ── 設計亮點（colors 是 60 色色票主角）
   ├─ F10 content            ── markdown editor 整合
   └─ F11 reports            ── echarts 圖表整合
```

實作順序（建議）：F01 → F02 → F03 → F04 → F05 → F06 → F07 → F08 → F09 → F10 → F11 → F12

---

## 模組清單

| 編號 | 名稱 | 涵蓋範圍 | 對應後端模組 | 對應 admin_routes |
|---|---|---|---|---|
| **F01** | App Shell + Admin Auth | 登入 / 登出 / 忘記密碼 / 重設密碼 / 路由守衛 / 認證後 layout（sidebar + header + main） | auth, admin | `/admin/login`、`/admin`、`/admin/forgot-password`、`/admin/reset-password` |
| **F02** | Dashboard | 後台首頁，簡單統計卡片 + 快速入口 | reports（取部分） | `/admin` (重導 `/admin/orders`) |
| **F03** | 商品管理 | products CRUD、variants、images、series、tags | product | `/admin/products`、`/admin/products/new`、`/admin/products/:id` |
| **F04** | 訂單管理 | 列表 + 篩選 + 詳情 + 狀態流 + 退款 + 出貨 | orders | `/admin/orders`、`/admin/orders/:id` |
| **F05** | 客製訂單管理 | 列表 + 篩選 + 詳情（含對話訊息流、報價操作） | custom | `/admin/custom-requests`、`/admin/custom-requests/:id` |
| **F06** | 製作系統 | image 上傳 + job CRUD + 參數調整 + 後處理流程 + 結果預覽 | production | `/admin/production`、`/admin/production/:jobId` |
| **F07** | 顏色 + 調色盤 | 60 色實體色管理 + RGB 校正 + 版本控制 + 預購缺貨儀表板 + 顏色對應工作台 | color, palette | `/admin/colors`、`/admin/colors/mapping/:jobId` |
| **F08** | 折扣管理 | CouponConfig CRUD + PromoCode CRUD + UserCoupon list + 批次發放 | discount | `/admin/discounts` |
| **F09** | 通知中心 | 三頁籤（未處理 / 處理中 / 已完成）+ 篩選 + 狀態變更 | notifications | `/admin/notifications` |
| **F10** | 內容管理 | static_pages + system_settings + custom_cases + case_categories + photo_prices + photo_surcharges（含 markdown 編輯器） | content | `/admin/content` |
| **F11** | 銷售報表 | 日期範圍 + 圖表 + 主要指標卡片 | reports | `/admin/reports` |
| **F12** | 列印批次 | 三步驟 wizard：選 jobs → preview 成本 → finalize PDF | print_batch | `/admin/print-batches`（待補入 admin_routes.md） |
| **F13** | 用戶管理 | 客戶列表 + 詳情 + 操作 | admin | `/admin/users` |

---

## 命名與位置慣例

```
admin/src/features/<module>/
├── pages/              # 路由級頁面元件
├── components/         # 該模組專用元件
├── api.ts              # openapi-fetch 封裝
├── store.ts            # Pinia（若需要 global state）
├── queries.ts          # TanStack Query hooks
└── schemas.ts          # zod 表單 schema
```

模組目錄名稱必須對應後端 `backend/<name>/`（例如 `features/orders/` ↔ `backend/orders/`），方便上下游對照。

---

## 共用層

```
admin/src/shared/
├── layouts/            # AdminLayout, AuthLayout
├── components/         # PageHeader, AppSidebar, AppHeader, UserMenu, AppDataTable, AppEmptyState, ...
├── ui/                 # shadcn-vue copy 後的 primitives（Button, Input, Dialog, ...）
├── composables/        # usePagination, useDebouncedRef, ...
└── lib/                # date, money, zh-TW formatters
```

`shared/` 的元件**不允許 import 任何 features/**，避免循環相依。
