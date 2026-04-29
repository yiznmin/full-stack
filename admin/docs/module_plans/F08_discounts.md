# F08 折扣管理 模組規劃書

> 對應後端 Module 08 (discount)、admin_routes 折扣區、admin_discount.md。
> 規格來源見章節末「規格定位」。本規劃書遵循 `admin/docs/frontend_sop.md`。

---

## 1. 路由清單

| 路由 | 頁面元件 | guard | 說明 |
|---|---|---|---|
| `/admin/discounts` | `DiscountsPage.vue` | requireAdmin | 折扣管理首頁，含三個 tab |
| `/admin/discounts/configs/:id/stats` | `CouponConfigStatsPage.vue` | requireAdmin | 單一券類型使用統計（圖表）|

主頁三個 tab：
- **券類型設定**（CouponConfigs，5 種系統類型 + 多筆 auto_checkout）
- **公開促銷碼**（PromoCodes，CRUD）
- **個人券記錄**（UserCoupons，查詢用）

sidebar 已有「折扣與券」連到 `/admin/discounts`。

---

## 2. 後端 API 對應表

| Endpoint | Method | 用途 |
|---|---|---|
| /admin/coupon-configs | GET | 列出全部 CouponConfig |
| /admin/coupon-configs/{id} | PATCH | 修改 config（5 種類型通用，含 auto_checkout 編輯） |
| /admin/coupon-configs/auto-checkout | POST | 新增 auto_checkout 活動 |
| /admin/coupon-configs/{id} | DELETE | 刪除 auto_checkout 活動（其他類型禁用）|
| /admin/coupon-configs/{id}/usage-stats | GET | 使用統計（總發放/總使用/折扣總額/月趨勢） |
| /admin/promo-codes | GET | 列出 PromoCode |
| /admin/promo-codes | POST | 新增 |
| /admin/promo-codes/{id} | PUT | 編輯 |
| /admin/promo-codes/{id} | DELETE | 刪除 |
| /admin/user-coupons | GET | 查 user_coupons（filter: user_id / coupon_type / is_used）|
| /admin/users/issue-coupons | POST | 批次手動發券（manual config）|

---

## 3. 元件樹

```
DiscountsPage（top-level，含 PageHeader + DiscountsTabs）
├─ DiscountsTabs：configs / promo / users
│
├─ Tab A：CouponConfigs
│  ├─ SystemConfigsCard（new_user / spend_reward / returning_loyal / manual 各一筆）
│  │  └─ row：類型 / is_active toggle / 折扣值 / 門檻 / valid_days / [編輯]
│  ├─ AutoCheckoutSection
│  │  ├─ 列 N 筆 auto_checkout：trigger / start~end / 折扣 / [編輯][刪除]
│  │  └─ 「+ 新增促銷活動」按鈕
│  └─ Dialogs：
│     ├─ EditConfigDialog（依 coupon_type 顯示對應欄位 — system 類型、manual 類型、auto_checkout 共用）
│     └─ ConfirmDeleteDialog
│
├─ Tab B：PromoCodes
│  ├─ AppDataTable：code / discount / start~end / total_used/max / is_active
│  ├─ 「+ 新增促銷碼」按鈕 → PromoCodeDialog
│  └─ Dialogs：
│     ├─ PromoCodeDialog（建立 / 編輯）
│     └─ ConfirmDeleteDialog
│
└─ Tab C：UserCoupons
   ├─ FilterBar：user 搜尋 / coupon_type / is_used / source_order_id
   ├─ AppDataTable：用戶 / 類型 badge / 折扣 / 有效期 / 已用 / 來源訂單
   └─ 「批次發放」按鈕 → IssueCouponsDialog（多選 user + 選 manual config）

CouponConfigStatsPage
├─ Header：類型名稱 + 返回
├─ MetricsCards：發放總數 / 使用總數 / 折扣總額 / 使用率
└─ MonthlyChart（echarts，先用簡單表格，圖表 F11 補）
```

---

## 4. 狀態 / Query 設計

```ts
const DC_KEYS = {
  configs:       ['admin','discounts','configs'] as const,
  configStats:   (id: string) => ['admin','discounts','configs','stats', id] as const,
  promoCodes:    ['admin','discounts','promo-codes'] as const,
  userCoupons:   (params) => ['admin','discounts','user-coupons', params] as const,
}
```

- configs / promoCodes：staleTime 60s（變動較少）
- userCoupons：staleTime 30s
- mutation 後 invalidate 對應 key

---

## 5. zod 表單 schema

```ts
const discountTypeEnum = z.enum(['percentage', 'fixed'])

const editConfigSchema = z.object({
  is_active: z.boolean(),
  discount_type: discountTypeEnum,
  discount_value: z.coerce.number().positive(),
  min_purchase: z.coerce.number().min(0),
  // params 依 coupon_type 變動，用 superRefine 動態驗證
  params: z.record(z.any()).optional(),
})

const autoCheckoutCreateSchema = z.object({
  discount_type: discountTypeEnum,
  discount_value: z.coerce.number().positive(),
  min_purchase: z.coerce.number().min(0),
  trigger_threshold: z.coerce.number().min(0),
  start_at: z.string().datetime().optional().nullable(),
  end_at: z.string().datetime().optional().nullable(),
})

const promoCodeSchema = z.object({
  code: z.string().regex(/^[A-Z0-9_-]{3,40}$/, '代碼僅可含大寫字母、數字、底線、連字號（3-40 字）'),
  discount_type: discountTypeEnum,
  discount_value: z.coerce.number().positive(),
  min_purchase: z.coerce.number().min(0).optional().nullable(),
  start_at: z.string().datetime().optional().nullable(),
  end_at: z.string().datetime().optional().nullable(),
  max_total_uses: z.coerce.number().int().positive().optional().nullable(),
  max_per_user: z.coerce.number().int().positive().default(1),
})

const issueCouponsSchema = z.object({
  user_ids: z.array(z.string().uuid()).min(1, '至少選一位用戶'),
  coupon_config_id: z.string().uuid(),
})

const userCouponsFilterSchema = z.object({
  user_id: z.string().uuid().optional(),
  coupon_type: z.enum(['new_user', 'spend_reward', 'returning_loyal', 'manual', 'public_code']).optional(),
  is_used: z.enum(['true', 'false']).optional(),
})
```

---

## 6. 設計決策

| 項目 | 決策 |
|---|---|
| 類型色票 | new_user 暖橘 / spend_reward 木綠 / returning_loyal accent / manual muted / auto_checkout 沙銅 |
| discount_value 顯示 | percentage → `9 折`/`折扣 10%`；fixed → `折 NT$ 100` |
| 系統類型「停用」UX | toggle off 後旁邊顯示 ⚠️「停用後不再自動發放，已發出的券不受影響」|
| auto_checkout 多筆 | accordion / list 形式，每筆獨立卡片 |
| 批次發放 | 第一版用 `<input>` 貼 user UUID（多行貼）；F13 用戶管理做完後再升級成「從用戶列表勾選」|
| 使用統計圖表 | 第一版用簡單金額卡片 + 月份表格；echarts 圖表 F11 銷售報表時統一補 |
| UserCoupon `is_used` 篩選 | 三選一（全部 / 已用 / 未用），對應 query string |

---

## 7. 手動測試覆蓋表

| Case | 預期 | 驗證 |
|---|---|---|
| 進入 /admin/discounts 預設 tab | configs | screenshot |
| 切換三個 tab | URL query 同步 | reload 仍保留 |
| 編輯 new_user discount_value | PATCH 200 + 重 fetch | screenshot 前後 |
| 切 is_active → 系統類型停用 | PATCH 200 + UI 反映 | screenshot |
| 新增 auto_checkout | POST 201 + 列表多一筆 | screenshot |
| 編輯 auto_checkout | PATCH 200 + 重 fetch | screenshot |
| 刪除 auto_checkout（含 confirm dialog） | DELETE 204 + 列表少一筆 | screenshot |
| 嘗試刪除非 auto_checkout（API 直接打）| 後端 400 拒絕 | mock |
| 建立 promo_code 唯一 code | POST 201 | screenshot |
| 建立 promo_code 重複 code | 後端 409 → toast「代碼已存在」| mock |
| 編輯 promo_code | PUT 200 | screenshot |
| 刪除 promo_code | DELETE 204 | screenshot |
| UserCoupons 篩 is_used=true | 結果 only used | screenshot |
| 批次發放 manual | POST 200 + issued_count 顯示 | screenshot |
| 批次發放：選非 manual config | 後端 400 → toast | mock |
| 批次發放：user_id 不存在 | 後端 400 / 422 → toast | mock |
| 看 usage-stats 頁 | 4 卡片 + 月份表 | screenshot |
| 401 / 403 / 404 | 友善錯誤 | mock |
| F5 reload tab 狀態 | 保留 | screenshot |
| < 768px | 不爆版 | resize |

---

## 8. 規格定位

| 規格 | 來源 |
|---|---|
| 路由 | `docs/requirements/admin_routes.md` |
| 5 種 coupon_type 觸發條件 | `docs/requirements/admin_discount.md` §4.2 |
| 各類型參數 | `docs/requirements/admin_discount.md` §4.6 |
| 結帳折扣優先序 | `docs/requirements/admin_discount.md` §4.4 |
| 退款撤銷邏輯 | `docs/requirements/admin_discount.md` §4.8 |
| API request/response | `docs/api.md` 模組十六 |
| EVENT E02/E19/E23/E24/E25/E40/E41/E42/E43/E44 | `docs/EVENT_MATRIX.md` |
| 資料表欄位 | `docs/schema.md` 模組五 |

---

## 9. 不在本模組範圍

- 客戶端「我的優惠券」頁 — 屬 store/
- 結帳套用折扣的 UX — 屬 store/
- promo_code 自動失效 / 自動發放（new_user / spend_reward / returning_loyal）— 後端做
- 退款連動撤銷 — F04 訂單退款流程觸發，後端做
- 高級圖表 — 留到 F11 銷售報表

---

## 10. 待確認事項

1. **UserCoupons 批次發放的 user 選取 UX**：第一版用「貼 UUID（多行）」最簡單，但操作體驗差。**問**：可接受？或要先做 F13 用戶管理再回頭升級？
   - 我傾向：**先用 UUID 貼**，F13 完成後加「從用戶列表勾選」UX 按鈕

2. **使用統計圖表**：規格 §4.5 列了 `usage_by_month` 月份趨勢。第一版用簡單表格，echarts 圖表交給 F11 統一處理（避免重複引入 chart 套件）。**問**：同意？

3. **promo_code `code` 自動 uppercase**：若客戶輸入小寫 `sale2026` 後端是否轉大寫？前端要不要 input 自動 toUpperCase？
   - **傾向**：前端 input 自動 toUpperCase（避免大小寫混淆 + 客戶端直接輸入順手）

4. **`coupon_type` 的「public_code」是否真的存在**：spec 摘錄寫到 user_coupons 篩選有 `public_code` 類型，但 user_coupons 表沒有 `coupon_type` 欄位（只有 coupon_config_id 與 promo_code_id）。前端篩 `coupon_type=public_code` 等於「promo_code_id 非 null 且 coupon_config_id 為 null」。後端 API 是否原生支援這個 alias？
   - **傾向**：先寫 5 個系統類型 + `public_code` 共 6 個選項，後端不支援時改成 client 端 filter

5. **管理員取消用戶 UserCoupon**：spec 沒列「管理員手動撤銷某張券」的 endpoint。實務上可能會有「客戶反映誤領了券、admin 想撤」的需求。**問**：本輪不做，列 backlog？
   - **傾向**：不做（spec 沒列、API 沒有，需要先補後端）

---

我的傾向：**全 A**（除 #5 為 backlog）。同意就告訴我，直接開工。
