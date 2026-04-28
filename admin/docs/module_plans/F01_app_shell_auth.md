# F01 — App Shell + Admin 認證

> 後端對應：`backend/auth/`、`backend/admin/`
> 規格來源：`docs/api.md`（模組一）、`docs/requirements/auth_users.md`、`docs/requirements/admin_routes.md`
> 設計依據：`admin/docs/design_system.md`

---

## 1. 範圍

### 本模組做
- `/admin/login`：管理員登入頁
- `/admin/forgot-password`：忘記密碼頁
- `/admin/reset-password`：重設密碼頁（從 email 連結進來，URL 帶 `?token=...`）
- `/admin/logout`：登出（不是路由，是按鈕觸發 + 重導 `/admin/login`）
- 路由守衛：未認證 → 重導 `/admin/login`、非 admin role → 重導 `/admin/login` + 顯示提示
- 認證後 layout：左側欄（13 個模組導覽）+ 頂部 header（user menu、breadcrumb）+ 主內容區
- 401 全域攔截：任何 API 回 401 → 清 store + 重導 `/admin/login`

### 本模組不做
- Dashboard 內容（屬 F02）
- 任何模組頁面內容（屬 F02–F12）
- 暗色模式（design_system §10 已決議 v1 不做）
- 「Remember me」勾選（後端 cookie 已 8h，認為夠）
- 兩階段認證（OTP / TOTP）
- 帳號鎖定（後端目前無此邏輯）

---

## 2. 路由清單

| Path | Component | Layout | Guard | Redirect |
|---|---|---|---|---|
| `/admin/login` | `LoginPage` | `AuthLayout` | 已登入 → `/admin` | — |
| `/admin/forgot-password` | `ForgotPasswordPage` | `AuthLayout` | — | — |
| `/admin/reset-password` | `ResetPasswordPage` | `AuthLayout` | — | URL 缺 `token` → `/admin/login` |
| `/admin` | （重導） | — | 未登入 → `/admin/login` | → `/admin/orders`（F04 上線前暫導 `/admin/dashboard` 占位） |
| `/admin/dashboard` | `DashboardHome`（占位，F02 補完） | `AdminLayout` | 必須 admin | — |
| `*`（未匹配）| `NotFoundPage` | 視情況 | — | — |

### Guard 規則（`features/auth/guards.ts`）
1. 路由 meta 標 `requiresAuth: true` 的，未登入 → 重導 `/admin/login?next=<原路徑>`
2. 已登入但 `role !== 'admin'` → 強制呼叫 logout API 清 cookie + 重導 `/admin/login` + flash「此帳號非管理員」
3. 已登入訪問 `/admin/login` / `/admin/forgot-password` → 重導 `/admin`

---

## 3. 後端 API 對應

逐條從 `docs/api.md` 引：

| Endpoint | 用於頁面 / 動作 | Request | Response 200 | Response 4xx |
|---|---|---|---|---|
| `POST /api/v1/admin/auth/login` | LoginPage 提交 | `{email, password}` | `{id, name, role: "admin"}` + 設 cookie | 401 帳密錯 / 403 非 admin |
| `POST /api/v1/admin/auth/logout` | UserMenu 登出按鈕 | （無）| `{message}` + 清 cookie | — |
| `GET /api/v1/auth/me` | App boot + guard 觸發 | — | `{id, name, email, pending_email, role, gender, birthday}` | 401 未登入 |
| `POST /api/v1/admin/auth/forgot-password` | ForgotPasswordPage 提交 | `{email}` | `{message: "若帳號存在，重設連結已寄出"}` | 422 email 格式錯 |
| `POST /api/v1/auth/reset-password` | ResetPasswordPage 提交 | `{token, new_password}` | `{message: "密碼已更新"}` | 400 token 無效 / 過期 |

> 注意：admin 沒有獨立的 `me` endpoint，共用 `/auth/me`；`reset-password` 也共用客戶版（admin 信件中的連結會帶 admin frontend 的 `/admin/reset-password?token=...`）。

---

## 4. 元件樹

### Pages

```
features/auth/pages/
├── LoginPage.vue                # 登入表單
├── ForgotPasswordPage.vue       # 寄送重設信
└── ResetPasswordPage.vue        # 設定新密碼（讀取 URL ?token=）
```

### 元件

```
features/auth/components/
├── LoginForm.vue                # 表單本體（pages 包裝外層）
├── ForgotPasswordForm.vue
└── ResetPasswordForm.vue
```

### Shared layouts & components（本模組建置）

```
shared/layouts/
├── AuthLayout.vue               # 置中卡片，無 sidebar，logo 上方
└── AdminLayout.vue              # sidebar + header + <RouterView />

shared/components/
├── AppSidebar.vue               # 13 模組導覽
├── AppHeader.vue                # 上方列：breadcrumb + UserMenu
├── UserMenu.vue                 # 頭像 + 名字 + 下拉登出
├── PageHeader.vue               # 每個內頁頂部：標題 + 麵包屑 + 主操作 slot
├── AppLogo.vue                  # 整站 logo（暫用文字 PaintLearn）
└── FlashMessage.vue             # 從 sessionStorage 讀「此帳號非管理員」這類提示

shared/ui/                        # 從 shadcn-vue 複製
├── Button.vue
├── Input.vue
├── Label.vue
├── FormField.vue
└── Card.vue
```

### 元件關係圖

```
App.vue
└── RouterView
    ├── AuthLayout
    │   ├── AppLogo
    │   └── <RouterView>
    │       ├── LoginPage → LoginForm
    │       ├── ForgotPasswordPage → ForgotPasswordForm
    │       └── ResetPasswordPage → ResetPasswordForm
    │
    └── AdminLayout
        ├── AppSidebar
        ├── AppHeader → UserMenu
        └── <main> <RouterView /> </main>
            └── DashboardHome（F02 才補真實內容）
```

---

## 5. 狀態 / Query 設計

### Pinia Store（`features/auth/store.ts`）

```ts
useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as MeResponse | null,
  }),
  getters: {
    isAuthenticated: (s) => s.user !== null,
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    setUser, clear, async fetchMe(), async login(email, pw), async logout()
  }
})
```

> 不把 user 存 localStorage——cookie 是 source of truth，每次 app boot 用 GET /auth/me 取 user。

### TanStack Query（`features/auth/queries.ts`）

| Query / Mutation | Key | 觸發 |
|---|---|---|
| `useMeQuery()` | `['auth', 'me']` | App boot + 401 invalidate |
| `useLoginMutation()` | — | LoginForm submit |
| `useLogoutMutation()` | — | UserMenu logout |
| `useForgotPasswordMutation()` | — | ForgotPasswordForm submit |
| `useResetPasswordMutation()` | — | ResetPasswordForm submit |

成功後：login → router.push next/'/admin'；logout → invalidate `['auth', 'me']` + push `/admin/login`。

### 401 全域攔截（`api/client.ts`）

openapi-fetch middleware：

```ts
api.use({
  async onResponse({ response }) {
    if (response.status === 401) {
      useAuthStore().clear()
      queryClient.clear()
      router.push('/admin/login')
    }
  }
})
```

---

## 6. 表單 schema（zod）

`features/auth/schemas.ts`

```ts
import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('請輸入有效的 email'),
  password: z.string().min(1, '請輸入密碼'),
})

export const forgotPasswordSchema = z.object({
  email: z.string().email('請輸入有效的 email'),
})

export const resetPasswordSchema = z.object({
  new_password: z
    .string()
    .min(10, '密碼至少 10 個字元')
    .regex(/[A-Za-z]/, '密碼需含英文字母')
    .regex(/[0-9]/, '密碼需含數字'),
  confirm_password: z.string(),
}).refine((d) => d.new_password === d.confirm_password, {
  message: '兩次輸入的密碼不一致',
  path: ['confirm_password'],
})
```

> 後端密碼規則：`min10, 英數混合`（api.md 模組一），上行的 zod 與之對齊。

---

## 7. 設計決策

> 全部沿用 `admin/docs/design_system.md`，本模組例外列在下方。

### AuthLayout 細節
- 置中 `Card`（max-width 400px），垂直置中 100vh
- 卡片上方 80px 處放 `AppLogo`（文字 logo，Newsreader 32/40 + tracking -0.01em）
- 背景 `--bg-canvas`，無陰影、無漸層
- 表單欄位垂直 stack，間距 16px
- 主 CTA 寬度填滿卡片

### AdminLayout 細節
- Sidebar：寬 240px，固定左側，背景 `--bg-surface`
  - 上方 logo 區 64px
  - 13 個模組導覽 item，每 item：左側 8px 模組色圓點 + 圖示 + 文字
  - active 狀態：背景 `--bg-subtle` + 左 2px `--accent` 直條
  - hover：背景 `--bg-subtle`
- Header：高 64px，固定頂部右側（不蓋 sidebar），背景 `--bg-surface`，下方 1px `--border-hairline`
  - 左：麵包屑（`text-meta`）
  - 右：UserMenu
- main：背景 `--bg-canvas`，左外距 240px（讓開 sidebar），上外距 64px（讓開 header），內距 32px

### UserMenu
- 頭像（暫用文字縮寫圓圈）+ 名字 + chevron-down
- 點開出現：`{name}` + `{email}`（meta）+ 分隔線 + `登出` 按鈕
- 寬 240px，從觸發點右下方開出

### 模組例外
- LoginForm 提交按鈕標籤：「登入」（不是「Login」），用 `--accent` 主色
- 登入失敗錯誤訊息**inline**顯示在表單上方（不要 toast、不要 modal）
- ResetPasswordPage 顯示密碼強度規則（min 10 + 英數）作為輸入框下方 helper text

---

## 8. 手動驗收清單（chrome-devtools 跑過）

| # | Case | 預期結果 | 驗證手段 |
|---|---|---|---|
| 1 | 訪問 `/admin` 未登入 | 重導 `/admin/login`，URL 包含 `?next=/admin` | navigate + URL check |
| 2 | 登入頁正確輸入 + submit | POST /admin/auth/login 200 → 重導 `/admin` → 顯示 dashboard 占位 | fill + click + screenshot |
| 3 | 登入頁錯誤密碼 + submit | inline 錯誤 `帳號或密碼錯誤`，email 欄保留值 | fill + click + screenshot |
| 4 | 客戶 role 嘗試登入 admin | 後端 403 → 顯示「此帳號非管理員」 | fill + click + screenshot |
| 5 | 登入後 F5 reload | 維持登入（GET /me 重新拉，sidebar 不閃白） | reload + screenshot |
| 6 | UserMenu 登出 | POST /admin/auth/logout → 重導 `/admin/login` → cookie 消失 | click + screenshot + cookie check |
| 7 | 登入後直接 paste `/admin/login` URL | 重導 `/admin` | navigate + URL check |
| 8 | 任意 API 回 401（手動模擬） | 自動清 store + 重導 `/admin/login` | evaluate_script 模擬 + screenshot |
| 9 | 忘記密碼頁正確 email | 顯示「若帳號存在...」訊息，停留同頁 | fill + click + screenshot |
| 10 | 重設密碼頁無 token | 重導 `/admin/login` | navigate + URL check |
| 11 | 重設密碼頁有 token + 弱密碼 | inline 顯示「密碼至少 10 個字元」 | fill + click + screenshot |
| 12 | 重設密碼頁有 token + 兩次不一致 | inline 顯示「兩次輸入的密碼不一致」 | fill + click + screenshot |
| 13 | 重設密碼成功 | 顯示成功訊息 → 3 秒後重導 `/admin/login` | fill + click + wait + screenshot |
| 14 | 重設密碼 token 過期 | 後端 400 → 顯示「連結已過期，請重新申請」 | mock + screenshot |
| 15 | Sidebar 13 個 nav 連結點擊 | 對應路由（未實作的暫先 console log 不報錯） | click each + URL check |
| 16 | 視窗縮到 < 1024 寬 | sidebar 變漢堡按鈕 + 抽屜 | resize + screenshot |
| 17 | Tab 鍵走完整 LoginForm | 順序：email → password → 登入按鈕 → 忘記密碼連結，focus ring 可見 | press_key Tab × N + screenshot |
| 18 | Lighthouse a11y on `/admin/login` | 分數 ≥ 90 | lighthouse_audit |
| 19 | Console 無 error / warn（任一頁） | 0 條 | list_console_messages |
| 20 | 登入後 Network panel | `/auth/me` 帶 cookie 自動 200 | list_network_requests |

---

## 9. 待確認問題

1. **部署 base path**：admin 是 `admin.paintlearn.com/login` 還是 `paintlearn.com/admin/login`？
   - 影響：Vite `base` 設定、router `createWebHistory(base)`、cookie domain
   - **預設**（待確認後修正）：用 `/admin/*` 路徑前綴，cookie domain 設 `.paintlearn.com`
2. **重設密碼成功後是否自動登入**：api.md 寫「導回 /admin/login」，本模組依此**不自動登入**，使用者手動再登一次
3. **「此帳號非管理員」flash 持續方式**：用 `sessionStorage` 跨重導讀寫，還是用 query string `?error=not_admin`？
   - **預設**：sessionStorage（避免 URL 髒，且只用一次後刪除）
4. **Logo**：v1 用文字 logo（Newsreader「PaintLearn」），未來再換 SVG。OK 嗎？
5. **Sidebar 模組順序**：採 `00_overview.md` 中的順序（F01–F13），還是與 `admin_routes.md` 一致（orders 第一）？
   - **預設**：sidebar 用業務優先序：Orders → Custom → Production → Products → Colors → Discounts → Notifications → Print Batches → Reports → Content → Users（user/auth 不在 sidebar，在 UserMenu 或單獨頁）

---

## 10. 完成標準（Definition of Done — 本模組）

- [ ] 規格比對報告（§11 格式）已產出，無未解決 ⚠️
- [ ] 上方手動驗收清單 20 條全部跑過並貼 screenshot / URL check
- [ ] `pnpm type-check` 0 error
- [ ] `pnpm build` 成功
- [ ] Lighthouse a11y ≥ 90（`/admin/login`）
- [ ] Console 無 error / warn
- [ ] 設計風格 5 個 random screenshot 比對 design_system.md，無偏離
- [ ] 回頭驗收報告（`frontend_sop.md` §8 格式）產出，無 ⚠️
- [ ] /reviewer 審查 pass
- [ ] git commit：`feat(admin/auth): 完成 F01 - App Shell + Admin 認證`
