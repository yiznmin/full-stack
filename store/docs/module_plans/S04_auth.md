# S04 — 會員認證

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #17–21、後端 [backend/auth/router.py](../../../backend/auth/router.py)
>
> **追溯規劃書**：本模組已先實作（commits `e574618` 之前），事後補寫對齊 SOP。

---

## 1. 範圍

5 個頁面：

| Brief # | 頁面 | URL |
|---|---|---|
| #17 | 註冊 | `/register` |
| #18 | 登入 | `/login` |
| #19 | 忘記密碼（送 email） | `/forgot-password` |
| #20 | 重設密碼（token-based） | `/reset-password/:token` |
| #21 | Email 驗證（token） | `/verify-email/:token` |

---

## 2. 檔案清單

```
store/src/features/auth/
├── api.ts                    # fetch /auth/* endpoints
├── store.ts                  # Pinia: useAuthStore（user / isLoggedIn / refresh）
├── guards.ts                 # router.beforeEach 守衛 guestOnly / requiresAuth
└── pages/
    ├── RegisterPage.vue
    ├── LoginPage.vue
    ├── ForgotPasswordPage.vue
    ├── ResetPasswordPage.vue
    └── VerifyEmailPage.vue
```

---

## 3. API

| Endpoint | Method | 說明 |
|---|---|---|
| `/api/v1/auth/register` | POST | name + email + password → 寄驗證信 |
| `/api/v1/auth/login` | POST | email + password → set httpOnly cookie |
| `/api/v1/auth/logout` | POST | 清 cookie |
| `/api/v1/auth/me` | GET | 回登入用戶（用於 store hydration） |
| `/api/v1/auth/forgot-password` | POST | 寄重設信 |
| `/api/v1/auth/reset-password` | POST | token + new_password |
| `/api/v1/auth/verify-email` | POST | token |
| `/api/v1/auth/resend-verification` | POST | 重寄驗證信 |

全部支援 **JWT in httpOnly cookie**（`SameSite=lax + Secure`）+ **rate limiting**（commit `5061985` 之後）。

---

## 4. 安全設計

- bcrypt 密碼雜湊
- token rotation：reset / verify token 用過即廢
- account enumeration 防護：login「帳號或密碼錯誤」、forgot「若帳號存在」、resend「若此 email 已登記...」
- rate limiting：login 10/15min/IP、register 5/60min/IP、forgot 3/60min/IP

---

## 5. 事後修正項

| 項目 | 處理 commit |
|---|---|
| login / register 缺 rate limit | rate_limit.py + auth/router.py（`5061985` 之前的 security 批次） |
| resend-email-change TOCTOU race | pg_advisory_xact_lock（reviewer fix） |
| display_consent 欄位（custom 模組相關） | `e2a44dc` |

---

## 6. 手動驗收（追溯）

- [x] 14 頁 e2e console 0 error / 0 warn
- [x] type-check pass
- [x] backend 30 auth tests pass
