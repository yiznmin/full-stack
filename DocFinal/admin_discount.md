# 管理者端：折扣券管理模組

---

## 4.1 設計原則

- **類型固定在後端**：每種券的觸發邏輯以程式碼實作，不透過介面建立
- **參數可在後台調整**：折扣值、門檻、有效天數等可設定，不需改程式碼
- **後台介面職責**：管理各類型參數、啟用/停用、手動發放、查看使用記錄
- **擴充方式**：後端加觸發邏輯 + 後台加參數設定頁面

---

## 4.2 券類型定義

| 類型代號 | 名稱 | 觸發時機 | 日期控制 |
|---------|------|---------|---------|
| `new_user` | 新用戶歡迎券 | 用戶完成 email 驗證後自動發放 | valid_days |
| `spend_reward` | 滿額回饋券 | 訂單狀態變為 completed + 金額 >= 門檻 → 自動發放 | valid_days |
| `returning_loyal` | 回頭客忠誠券 | 訂單 completed + 金額 >= NT$1000 + 用戶有歷史完成訂單 → 自動發放 | valid_days |
| `public_code` | 公開促銷碼 | 結帳時手動輸入代碼 | start_at / end_at |
| `manual` | 手動發放 | 管理員指定用戶發放 | 管理員設定到期日 |
| `auto_checkout` | 結帳自動促銷 | 結帳時 subtotal 達門檻自動套用，無需輸入代碼 | start_at / end_at |

---

## 4.3 每種類型的可設定參數

### new_user（新用戶歡迎券）
- discount_type：percentage / fixed
- discount_value：折扣值
- min_purchase：最低消費門檻
- valid_days：發放後幾天有效
- is_active：是否啟用

### spend_reward（滿額回饋券）
- trigger_threshold：觸發發放的訂單金額門檻（如 NT$1000）
- discount_type：percentage / fixed
- discount_value：折扣值
- min_purchase：使用時的最低消費門檻
- valid_days：發放後幾天有效
- is_active：是否啟用

### returning_loyal（回頭客忠誠券）
- trigger_threshold：NT$1000（固定，未來可調整）
- discount_type：percentage / fixed
- discount_value：折扣值
- min_purchase：使用時的最低消費門檻
- valid_days：發放後幾天有效
- is_active：是否啟用

### public_code（公開促銷碼）
- code：唯一代碼（如 SALE2026）
- discount_type：percentage / fixed
- discount_value：折扣值
- min_purchase：最低消費門檻
- start_at：活動開始日期
- end_at：活動結束日期
- max_total_uses：總使用上限（null = 無限制）
- max_per_user：每人上限（通常為 1）
- is_active：是否啟用

### manual（手動發放）
- 不預設參數，每次發放時由管理員指定：
  - discount_type / discount_value
  - min_purchase
  - expires_at（直接指定到期日）
  - 發放對象（單一用戶或批量）

### auto_checkout（結帳自動促銷）
- trigger_threshold：觸發門檻（如 NT$1000）
- discount_type：percentage / fixed
- discount_value：折扣值（如 NT$100）
- start_at：活動開始日期
- end_at：活動結束日期
- is_active：是否啟用

---

## 4.4 後端觸發邏輯

```
new_user
  → 監聽：users.is_email_verified 從 false 變為 true
  → 條件：無（驗證完成時 is_active 本來就是 true，不需額外檢查）
  → 動作：建立 user_coupon 記錄（快照 coupon_configs.new_user 當下參數）

**spend_reward / returning_loyal 觸發邏輯（偽碼）**

訂單狀態變為 `completed` 時執行：

```
if (用戶除此筆外有其他 completed 訂單) 
   AND (returning_loyal.is_active = true)
   AND (order.total >= returning_loyal.trigger_threshold):
    發放 returning_loyal 券（INSERT user_coupons, source_order_id = 此訂單）
    
elif (spend_reward.is_active = true)
     AND (order.total >= spend_reward.trigger_threshold):
    發放 spend_reward 券（INSERT user_coupons, source_order_id = 此訂單）

else:
    不發放
```

**說明：**
- 兩者**二選一**，returning_loyal 優先（回頭客獎勵優先於一般滿額獎勵）
- `source_order_id` 記錄觸發訂單，退款時依此判斷是否撤銷（見 §4.8）
- is_active 的檢查是 `coupon_configs.is_active`（非 users.is_active）

public_code
  → 監聽：結帳時用戶輸入代碼
  → 條件：代碼存在 + is_active + 在 start_at~end_at 內
          + total_used < max_total_uses
          + 該用戶對此 promo_code 的 user_coupons 記錄數 < max_per_user
          + order.subtotal >= min_purchase
  → 動作：
    1. 在同一 transaction 內：
       - INSERT user_coupons(is_used=true, used_at=now(), used_in_order_id=此訂單)
       - UPDATE promo_codes.total_used += 1（原子遞增）
    2. user_coupons 記錄**永久保留作為使用紀錄**，不刪除
    3. 退款時於同一 transaction 內：
       - user_coupons.is_used = false，清空 used_at / used_in_order_id
       - promo_codes.total_used -= 1（原子遞減）

manual
  → 監聽：管理員操作
  → 動作：直接建立 user_coupon 記錄

auto_checkout
  → 監聽：結帳時自動計算
  → 條件：is_active + 在 start_at~end_at 內
          + order.subtotal >= trigger_threshold
  → 動作：直接套用折扣（不建立 user_coupon，記錄於 orders.auto_discount_amount）
```

**折扣套用規則**

結帳時依以下優先順序決定折扣，同一筆訂單只套用一種折扣：

1. **客戶主動輸入 `public_code`** → 以 public_code 為準，不套 auto_checkout，不與其他折扣比較。`total_used` 正常遞增，`user_coupon` 正常建立並標記已使用。
2. **客戶使用持有券（user_coupon）** → 套用該券折扣，不套 auto_checkout。
3. **無輸入折扣碼、無持有券** → 系統自動套用符合條件的 auto_checkout（取折扣金額最高者）。

多個 auto_checkout 同時符合條件時（例如滿 500 折 30 與滿 800 折 50），系統只套用折扣金額最高的一張，不疊加。

```
# 只有第 3 種情境才走此邏輯
best_auto_checkout = 所有符合條件的 auto_checkout 中，折扣金額最高者
```

---

## 4.5 後台介面操作

| 操作 | 說明 |
|------|------|
| 查看各類型設定 | 列出所有券類型及目前參數 |
| 啟用 / 停用 | 隨時暫停某類型的自動發放或使用 |
| 編輯參數 | 修改折扣值、門檻、有效天數等 |
| 手動發放 | 從用戶列表多選目標用戶 → 設定折扣與到期日 → 批量發放 |
| 查看 user_coupons | 篩選用戶、券類型、使用狀態 |
| 使用統計 | 各類型使用次數、折扣總金額 |

---

## 4.6 資料庫欄位

**券類型設定表（coupon_configs）**

`public_code` 類型獨立存於 `promo_codes` 表（見下方），其餘類型每種一筆記錄於此表。

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| coupon_type | new_user / spend_reward / returning_loyal / manual / auto_checkout |
| discount_type | percentage / fixed（共用）|
| discount_value | 折扣值（共用）|
| min_purchase | 最低消費門檻（共用）|
| is_active | 是否啟用（共用）|
| params | JSONB，存類型專屬參數（見下方）|
| updated_at | 最後修改時間 |

**各類型 params 內容**

```json
// new_user
{ "valid_days": 30 }

// spend_reward
{ "trigger_threshold": 1000, "valid_days": 30 }

// returning_loyal
{ "trigger_threshold": 1000, "valid_days": 30 }

// manual
{}

// auto_checkout
{
  "trigger_threshold": 1000,
  "start_at": "2026-05-01",
  "end_at": "2026-05-31"
}
```

> params 欄位的結構由後端按 coupon_type 負責驗證，不依賴資料庫層級約束。

**公開促銷碼表（promo_codes）**

`public_code` 類型獨立一表，支援同時存在多個不同促銷碼。

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| code | 促銷碼（唯一，如 `SALE2026`）|
| discount_type | percentage / fixed |
| discount_value | 折扣值 |
| min_purchase | 最低消費門檻 |
| start_at | 活動開始時間 |
| end_at | 活動結束時間 |
| max_total_uses | 總使用上限（null = 無限制）|
| max_per_user | 每人使用上限（通常為 1）|
| total_used | 已使用次數（原子遞增）|
| is_active | 是否啟用 |
| created_at | 建立時間 |
| updated_at | 最後修改時間 |

> 結帳時用戶輸入代碼 → 後端查此表驗證條件（is_active、時間範圍、使用次數、最低消費）。
> 並發保護：扣減 `total_used` 使用 `UPDATE promo_codes SET total_used = total_used + 1 WHERE id = ? AND total_used < max_total_uses`，利用資料庫原子更新確保不超額，更新失敗（影響列數為 0）時回傳「促銷碼已達使用上限」。

**用戶持有券（user_coupons）**

| 欄位 | 說明 |
|------|------|
| id | 主鍵 |
| user_id | FK → users.id |
| coupon_config_id | FK → coupon_configs.id（nullable，public_code 使用時為 null）|
| promo_code_id | FK → promo_codes.id（nullable，非 public_code 為 null）|
| discount_type | 快照（發放當時的設定）|
| discount_value | 快照 |
| min_purchase | 快照 |
| expires_at | 到期時間 |
| is_used | 是否已使用 |
| used_at | 使用時間 |
| used_in_order_id | FK → orders.id（nullable）|
| source_order_id | FK → orders.id（nullable，`spend_reward` / `returning_loyal` 記錄觸發來源訂單，用於退款撤回）|
| created_at | 發放時間 |

> 快照欄位確保即使之後管理員修改了參數，已發放的券仍按當時條件計算。

---

## 4.7 結帳限制

- 同一筆訂單只能使用一張折扣券
- 不可與其他折扣疊加（後續活動折扣另行擴充）
- 購物車與結帳均需登入才能使用

## 4.8 退款 / 取消後的券處理

**全額退款 / 取消（status = cancelled / refunded / payment_expired）**

訂單狀態變為 `cancelled`、`refunded` 或 `payment_expired` 時，若該訂單有使用折扣券（`user_coupons.used_in_order_id` 對應此訂單），系統自動：

1. 將 `user_coupon.is_used` 改回 `false`
2. 清空 `user_coupon.used_at` 與 `used_in_order_id`
3. 客戶折扣券錢包中該券恢復為「可用」狀態

> `public_code` 類型券：除了恢復 `user_coupon`，還需將 `promo_codes.total_used` 減 1（原子遞減）。

**部分退款（status = partially_refunded）**

訂單仍有部分成立，折扣券**不回補**：

- `user_coupon.is_used` **維持 true**
- `promo_codes.total_used` **維持不變**
- 客戶錢包中該券狀態不改變

**回饋券撤回**

訂單狀態變為 `refunded` 或 `partially_refunded` 時，系統查找因此訂單觸發發放的回饋券（`spend_reward` / `returning_loyal`），條件：`user_coupons.source_order_id = 此訂單 id`。

- **全額退款（refunded）**
  - 券**未使用**（`is_used = false`）→ `expires_at = now()` 立即作廢
  - 券**已使用**（`is_used = true`）→ 不處理
- **部分退款（partially_refunded）**
  - 計算剩餘有效金額：`remaining = order.total - refund_amount`
  - 若 `remaining ≥ 當時的 trigger_threshold` → **不撤銷**，券照常有效
  - 若 `remaining < 當時的 trigger_threshold` → 同全額退款邏輯處理（未使用者立即作廢）
