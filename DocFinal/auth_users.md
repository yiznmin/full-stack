# 使用者系統需求規格

---

## 1. 使用者資料表（users）

| 欄位 | 型別 | 規則 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | string | min=4 | 顯示名稱 |
| email | string | 驗證格式, unique | 登入帳號 |
| password_hash | string | — | bcrypt 雜湊，不存明文 |
| gender | enum | nullable | 女 / 男 / 其他 |
| birthday | date | nullable | 前端使用日期選擇器 |
| role | enum | 後端自動填入 | `admin` / `customer` |
| is_active | boolean | 預設 true | 停用帳號用，不實際刪除資料 |
| is_email_verified | boolean | 預設 false | Email 驗證完成後改為 true |
| pending_email | string | nullable | 客戶申請更換的新 email（驗證完成後覆蓋 email 欄位，驗證前暫存於此）|
| created_at | timestamp | — | 建立時間 |
| updated_at | timestamp | — | 最後更新時間 |

**密碼格式規則**：最少 10 碼，需同時包含英文字母與數字

**名稱規則**：`name` 最少 4 個字元（UTF-8），一個中文字算 1 個字元

**role 規則**：
- 用戶自行註冊 → 後端固定填入 `customer`，前端無此欄位
- 管理員由現有 admin 在後台手動設定角色為 `admin`
- 現階段所有 admin 權限相同，之後視需求再拆分

**第一個管理員建立方式**

系統初次部署時無任何 admin，第一個管理員帳號透過後端 CLI 指令建立，不走前台註冊流程：

```bash
python scripts/create_admin.py --email admin@paintlearn.com --password <password>
```

執行後直接在資料庫建立 `role=admin`、`is_email_verified=true` 的帳號。之後的管理員由此帳號在後台設定。

---

## 2. 操作權限

### 管理者角度（admin 平台）

| 操作 | 說明 |
|------|------|
| 登入 | email + 密碼驗證，通過後進入管理介面 |
| 查看使用者列表 | 可搜尋、篩選（角色、建立日期） |
| 修改任何使用者資料 | 除 role 欄位以外都可修改（含密碼：管理員可直接重設客戶密碼）|
| 變更角色 | 可將 customer 升為 admin，或 admin 降為 customer |
| 停用帳號 | 標記 is_active=false，使帳號無法登入（不實際刪除）。**禁止停用自己的帳號**，後端驗證操作者 user_id 不等於目標 user_id，否則回傳錯誤。|
| 忘記密碼 | 在 `/admin/login` 頁面點「忘記密碼」→ 填寫 email → 收重設連結 → 重設完成後導回 `/admin/login` |

### 用戶角度（商店端）

| 操作 | 說明 |
|------|------|
| 註冊 | 填寫 name / email / password，即時格式驗證；送出後寄驗證信，點連結完成驗證後帳號啟用 |
| 登入 | email + 密碼驗證；未驗證 email 的帳號無法登入 |
| 修改個人資料 | 除 role 以外都可修改（name、密碼、性別、生日）；**Email 修改需重新驗證**：送出時後端立即檢查新 email 是否已存在於 `users.email` 或 `users.pending_email`，有衝突直接回錯誤不發信；通過檢查後新 email 暫存於 `pending_email`，系統發驗證信，點連結後正式更新 `email` 欄位。**驗證前舊 email 仍可登入**；**驗證完成當下舊 email 立即失效，不可再登入** |
| 忘記密碼 | 填寫 email → 系統發送驗證信 → 點連結重設密碼 |

---

## 3. 密碼重設流程

```
使用者填寫 email
    ↓
後端確認 email 存在 → 產生限時 token（1 小時有效）
    ↓
發送含重設連結的 email
    ↓
使用者點連結 → 填寫新密碼（需符合格式規則）
    ↓
後端驗證 token 有效 → 更新 password_hash → token 作廢
```

---

## 4. 前端 UX

### 商店端

- 頁面右上角顯示「註冊 / 登入」按鈕（未登入時）
- 登入後顯示用戶名稱，點選進入個人檔案頁面
- 個人檔案頁包含：編輯基本資料、收件資料管理、訂單記錄

### 管理端

- 進入網址直接顯示登入頁面，無其他公開內容
- 登入成功後進入管理介面
- JWT token 存於 httpOnly cookie，過期自動登出

---

## 5. 客戶收件資料表（shipping_profiles）

一個用戶可儲存多筆收件資料，並設定一筆為預設。支援三種取貨方式。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID | 主鍵 |
| user_id | UUID | FK → users.id |
| shipping_type | enum | `home` / `seven_eleven` / `family_mart` |
| recipient_name | string | 收件人姓名（送貨名稱，可與帳號名不同） |
| phone | string | 聯絡電話 |
| email | string | 物流通知 email（ECpay 寄送到貨 / 門市通知用，選填，可與帳號 email 不同；未填則使用帳號 email）|
| city | string | 縣市（shipping_type=home 時填寫，下拉選單，否則為 null） |
| district | string | 鄉鎮市區（shipping_type=home 時填寫，依縣市連動下拉，否則為 null） |
| address_detail | string | 詳細地址：路街號樓（shipping_type=home 時填寫，自由文字，否則為 null） |
| store_id | string | 門市代號（超商取件時填寫，否則為 null） |
| store_name | string | 門市名稱（超商取件時填寫，否則為 null） |
| is_default | boolean | 是否為預設收件資料 |
| created_at | timestamp | 建立時間 |

**取貨方式說明**

| shipping_type | 必填欄位 |
|---|---|
| home（宅配到府） | recipient_name、phone、city、district、address_detail |
| seven_eleven（7-11 店到店） | recipient_name、phone、store_id、store_name |
| family_mart（全家店到店） | recipient_name、phone、store_id、store_name |

**規則**：
- 同一用戶只能有一筆 `is_default=true`，設定新預設時自動取消舊的
- 可新增、編輯、刪除
- 超商門市選擇：前端串接門市查詢介面（7-11 / 全家各自提供）

---

## 6. Email 驗證 Token 表（email_verification_tokens）

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| user_id | FK → users.id |
| token | 隨機產生的安全 token（hashed）|
| token_type | `signup`（註冊驗證）/ `email_change`（換信箱驗證）|
| expires_at | 有效期限（產生後 24 小時）|
| used_at | 使用時間（nullable，驗證後填入，token 作廢）|
| created_at | 建立時間 |

> `email_change` 類型驗證成功後，將 `users.pending_email` 寫入 `users.email` 並清空 `pending_email`。不觸發 `new_user` 歡迎券。**舊 email 在驗證完成的同一 transaction 內立即失效,後續所有登入與 JWT 驗證皆以新 email 為準。**

> `signup` 類型驗證成功後設定 `users.is_email_verified = true`，並觸發 `new_user` 歡迎券發放。

---

## 7. 密碼重設 Token 表（password_reset_tokens）

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| user_id | FK → users.id |
| token | 隨機產生的安全 token（hashed）|
| expires_at | 有效期限（產生後 1 小時）|
| used_at | 使用時間（nullable，使用後填入，token 作廢）|
| created_at | 建立時間 |

> 用戶重新申請重設密碼時，系統自動將該用戶所有 `used_at IS NULL` 的舊 token 寫入 `used_at = now()` 使其作廢，確保同時只有一個有效 token。

---

## 8. 帳號停用保護

管理員將 `users.is_active = false` 後，即使用戶持有有效 JWT，每次 API 請求後端驗證 token 後仍需額外查詢 `users.is_active`，若為 false 回傳 401，前端依正常 token 過期流程跳轉登入頁。

---

## 9. JWT 驗證機制

- 登入成功 → 後端簽發 JWT（payload 含 user_id, role, exp）
- Token 存於 httpOnly cookie，前端無法直接讀取（防 XSS）
- 過期時間：一般用戶 7 天，管理員 8 小時
- 受保護路由依 role 區分：
  - `require_auth`：需登入（customer 或 admin）
  - `require_admin`：需 role=admin

**Token 過期處理**

**商店端（customer）**：前端統一攔截 API 回傳的 401 錯誤：
1. 跳出提示：「登入已逾期，請重新登入」
2. 記錄當前頁面 URL（`redirect` 參數）
3. 跳轉登入頁
4. 登入成功後導回原本頁面

> 表單填寫中的資料會丟失，但 7 天有效期下此情境極少發生。

**管理端（admin）**：前端攔截 401 錯誤：
1. 跳出提示：「登入已逾期，請重新登入」
2. 跳轉至管理員登入頁（`/admin/login`），不記錄 redirect
3. 登入成功後回到管理首頁
