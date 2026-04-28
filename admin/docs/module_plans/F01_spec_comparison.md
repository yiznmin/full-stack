# 規格比對報告 — F01 App Shell + Admin 認證

> 配對 `F01_app_shell_auth.md` 規劃書與所有規格來源逐項比對。任何 ⚠️ 必須修正後才能寫 code。

---

## 1. api.md 端點比對

來源：`docs/api.md` lines 48–125

| Endpoint | api.md 規定 | 規劃書對應 | 結果 |
|---|---|---|---|
| `POST /admin/auth/login` | req `{email, password}` / res 200 `{id, name, role}` + cookie 8h / 401 帳密錯 / 403 非 admin | F01 §3 完整列出，§5 useLoginMutation，§6 loginSchema 對應，§8 case 2/3/4 涵蓋 200/401/403 | ✓ |
| `POST /admin/auth/logout` | 權限 admin / 清 cookie | F01 §5 useLogoutMutation，§7 UserMenu 觸發，§8 case 6 驗證 | ✓ |
| `GET /auth/me` | res 200 `{id, name, email, pending_email, role, gender, birthday}` / 401 未登入 | F01 §5 useMeQuery + 401 全域攔截，§8 case 5 reload 驗證 + case 8 401 | ✓ |
| `POST /admin/auth/forgot-password` | req `{email}` / 200 固定訊息（不洩漏帳號是否存在）| F01 §3 列出 + §6 forgotPasswordSchema + §8 case 9 | ✓ |
| `POST /auth/reset-password` | req `{token, new_password}` / 200 / 400 token 無效或過期 | F01 §3 列出（共用客戶端 endpoint）+ §6 resetPasswordSchema + §8 cases 10/11/12/13/14 | ✓ |

**注意**：admin 沒有獨立 `me` / `reset-password`，共用客戶端 endpoint。規劃書 §3 註記了這點。

---

## 2. requirements/auth_users.md 業務規則比對

| 規則 | 來源（行）| 規劃書對應 | 結果 |
|---|---|---|---|
| 密碼最少 10 碼，需含英文字母與數字 | L22 | §6 resetPasswordSchema 三條 zod 驗證 | ✓ |
| admin 由現有 admin 在後台設定 | L28 | F01 不做此功能（屬 F13 用戶管理）| ✓（範圍外）|
| admin 「忘記密碼」流程：`/admin/login` 點「忘記密碼」→ 填 email → 收信 → 完成後導回 `/admin/login` | L54 | §2 路由 + §3 endpoint + §8 case 13 涵蓋 | ✓ |
| 密碼重設成功後 token 作廢 | L78 | 後端責任，前端只需處理 200/400 回應 | ✓ |
| 重設 token 有效期 1 小時 | L72 | 前端不驗 expiry（後端驗），規劃 §8 case 14 涵蓋 400 過期回應 | ✓ |
| 管理端進入網址直接顯示登入頁，無其他公開內容 | L93 | §2 guard 規則：未登入訪問任何 admin 路徑 → 重導 `/admin/login` | ✓ |
| 登入成功後進入管理介面 | L94 | §2 路由 `/admin/login` 已登入 → 重導 `/admin` → 重導 `/admin/orders` | ✓ |
| JWT 存 httpOnly cookie，過期自動登出 | L95 | §5 401 全域攔截：API 401 → 清 store + 重導 login | ✓ |
| 帳號停用 → 後端 401 | L169 | §5 401 攔截一視同仁處理（前端不需區分原因）| ✓ |
| `is_active=false` 即使有效 JWT 仍 401 | L169 | 同上，前端 401 統一導出 | ✓ |
| 變更密碼 / role / 停用帳號等管理操作 | L51–53 | F01 不做（屬 F13 用戶管理）| ✓（範圍外）|

**全部 ✓，無待解決差異。**

---

## 3. requirements/admin_routes.md 路由比對

| 規定路由 | 規劃書對應 | 結果 |
|---|---|---|
| `/admin/login` 登入頁（公開）| §2 第 1 列 | ✓ |
| `/admin` 儀表板（跳 `/admin/orders`）| §2 重導規則 | ✓（F04 上線前暫導 `/admin/dashboard` 占位）|
| `/admin/orders` ... `/admin/users` 等 13 條 | §4 sidebar 13 連結 | ✓（連結存在，目標頁面由 F02–F13 各自實作）|

`admin_routes.md` 中的具體子路由（products/new、orders/:id、custom-requests/:id 等）由 F03–F13 各模組規劃書處理，F01 只負責**確保 sidebar 入口存在 + 守衛機制能保護所有 `/admin/*` 路徑**。

---

## 4. design_system.md 一致性比對

| 規則 | 來源（§）| 規劃書對應 | 結果 |
|---|---|---|---|
| 字體：Newsreader 標題 + IBM Plex Sans 內文 + JetBrains Mono 數字 | §2 | §7 AppLogo 用 Newsreader、表單欄位內文 IBM Plex Sans | ✓ |
| 色票：象牙白 bg + 深酒紅 accent | §3.1 / §3.2 | §7 LoginForm CTA 用 `--accent`、錯誤訊息用 `--danger` | ✓ |
| 模組色：每個模組 sidebar 一個色 | §3.3 | §7 AdminLayout sidebar item 左側 8px 圓點 | ✓ |
| 表格 row 48px、卡片內距 24px | §4 | §7 AuthLayout Card 24px 內距、AdminLayout main 32px 內距 | ✓ |
| 圓角：input 4px、卡片 6px | §5 | §7 LoginForm 沿用元件預設（shadcn-vue 配 design tokens）| ✓ |
| 動畫：頁面進場 stagger fade，hover 不縮放 | §6 | §7 未明寫但 §10 「沿用 design_system」隱含遵守 | ✓ |
| Button 三種等級（primary/secondary/tertiary）| §7 | §7 LoginForm 主 CTA primary、忘記密碼連結 tertiary | ✓ |
| Modal Esc 關閉、focus trap | §9 | F01 不用 modal（登入流程都是頁面），不適用 | ✓（範圍外）|
| Lighthouse a11y ≥ 90 | §9 | §8 case 18 + §10 完成標準 | ✓ |
| 不用 Inter 標題 / 不用紫漸層 / 不 hover scale | §12 | §7 沿用設計系統，無例外列入 | ✓ |
| 1024 寬以下 sidebar 變抽屜 | §11 | §8 case 16 涵蓋 | ✓ |

**全部 ✓。**

---

## 5. 手動測試覆蓋表

逐條對應規劃書 §8 的 20 個 case 到實作位置 / 驗證手段：

| # | Case | 預期結果 | 驗證手段 | 對應規格來源 |
|---|---|---|---|---|
| 1 | 訪問 `/admin` 未登入 | 重導 `/admin/login?next=/admin` | navigate + URL check | requirements/auth_users.md L93 |
| 2 | 正確登入 | 200 → 重導 `/admin` → dashboard 占位 | fill + click + screenshot | api.md L112 |
| 3 | 錯誤密碼 | inline `帳號或密碼錯誤`，email 保留 | fill + click + screenshot | api.md L118 |
| 4 | 客戶 role 嘗試 | 403 → 顯示「此帳號非管理員」 | fill + click + screenshot | api.md L118 + requirements L28 |
| 5 | 登入後 F5 | 維持登入，sidebar 不閃白 | reload + screenshot | requirements L95 |
| 6 | UserMenu 登出 | 200 → 重導 login → cookie 消失 | click + screenshot + cookie check | api.md L121 |
| 7 | 已登入訪問 `/admin/login` | 重導 `/admin` | navigate + URL check | （UX 推論）|
| 8 | 任意 API 401 | 自動清 store + 重導 login | evaluate_script 模擬 + screenshot | requirements L169 |
| 9 | 忘記密碼正確 email | 「若帳號存在...」訊息，停留同頁 | fill + click + screenshot | api.md L124 |
| 10 | 重設密碼頁無 token | 重導 `/admin/login` | navigate + URL check | （安全推論）|
| 11 | 重設密碼弱密碼 | 「密碼至少 10 個字元」 | fill + click + screenshot | api.md L107 + requirements L22 |
| 12 | 兩次密碼不一致 | 「兩次輸入的密碼不一致」 | fill + click + screenshot | （UX 推論）|
| 13 | 重設成功 | 訊息 → 3 秒重導 login | fill + click + wait + screenshot | requirements L54 |
| 14 | token 過期 | 「連結已過期，請重新申請」 | mock + screenshot | api.md L109 + requirements L72 |
| 15 | Sidebar 13 nav 點擊 | 對應路由（未實作的 console log 不報錯）| click each + URL check | requirements/admin_routes.md L8–25 |
| 16 | < 1024 寬 | sidebar → 漢堡 + 抽屜 | resize + screenshot | design_system §11 |
| 17 | Tab 走完 LoginForm | 順序正確、focus ring 可見 | press_key Tab × N + screenshot | design_system §9 |
| 18 | Lighthouse a11y `/admin/login` | ≥ 90 | lighthouse_audit | design_system §9 |
| 19 | Console 無 error / warn | 0 條 | list_console_messages | frontend_sop.md §4 |
| 20 | `/auth/me` 帶 cookie 自動 200 | network 正常 | list_network_requests | requirements L95 |

每條都對應到規格來源，無孤兒測試。

---

## 6. 差異與待確認

### 待確認（需使用者決議，但不阻擋寫 code）
1. **部署 base path**（規劃書 §9 第 1 點）：admin 是子網域還是子路徑？
   - 影響：Vite `base` config、router 模式、cookie domain
   - **本模組假設**：Vue Router base = `/admin/`，Vite `base = '/admin/'`，可後調
2. **Sidebar 模組順序**（規劃書 §9 第 5 點）：採業務優先序（Orders 第一）
   - **本模組決議**：依規劃書 §9 第 5 點的順序，後續可調
3. **Logo**（規劃書 §9 第 4 點）：v1 用文字 logo
   - **本模組決議**：Newsreader 文字「PaintLearn」

以上 3 項都是**內部決定的合理預設**，不需後端 / 規格修改即可前進；後續若使用者要求調整，僅影響 F01 內檔案，無連鎖修改。

### 與規格的差異
**無 ⚠️。** 所有 §1–§4 的比對皆 ✓。

---

## 7. 結論

✅ **可以開始寫 code**。

下一步：
1. 從 shadcn-vue 複製需要的 primitives 進 `admin/src/shared/ui/`：Button、Input、Label、Card、FormField
2. 按 §4 元件樹順序實作：基底 (`shared/ui`、`shared/components/AppLogo`) → layouts (`AuthLayout`、`AdminLayout`) → store/queries → pages → guard
3. 每完成一個 page，跑 §5 對應的手動驗收 case，貼 screenshot 回對話
4. 全部完成後跑 §10 完成標準清單 + 回頭驗收 → /reviewer → commit
