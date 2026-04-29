# 規格比對報告 — F08 折扣管理

針對 `F08_discounts.md` 規劃書，對照 `docs/api.md`、`docs/requirements/admin_discount.md`、`docs/EVENT_MATRIX.md`，並用 OpenAPI 真實 dump 驗證。

---

## 1. api.md vs OpenAPI 真實實況

| Endpoint | api.md | OpenAPI | 結果 |
|---|---|---|---|
| GET /admin/coupon-configs | ✓ | ✓ | ✓ |
| PATCH /admin/coupon-configs/{id} | ✓ | ✓ | ✓ |
| POST /admin/coupon-configs/auto-checkout | ✓ | ✓ | ✓ |
| DELETE /admin/coupon-configs/{id} | ✓ | ✓ | ✓ |
| GET /admin/coupon-configs/{id}/usage-stats | ✓ | ✓ | ✓ |
| GET /admin/promo-codes | ✓ | ✓ | ✓ |
| POST /admin/promo-codes | ✓ | ✓ | ✓ |
| PUT /admin/promo-codes/{id} | ✓ | ✓ | ✓ |
| DELETE /admin/promo-codes/{id} | ✓ | ✓ | ✓ |
| GET /admin/user-coupons | ✓ | ✓ | ✓ |
| POST /admin/users/issue-coupons | ✓ | ✓ | ✓ |

**全部 11 個 endpoint 都已實作，無缺口。**

---

## 2. admin_discount.md 業務規則比對

| 規則 | 來源 | 規劃書對應 | 結果 |
|---|---|---|---|
| 5 種系統 coupon_type（new_user / spend_reward / returning_loyal / manual / auto_checkout） | §4.2 | SystemConfigsCard 4 種 + AutoCheckoutSection 多筆 | ✓ |
| auto_checkout 可同時多筆，擇優套用 | §4.4 + §4.6 | AutoCheckoutSection 列表 + 每筆獨立卡 | ✓ |
| 結帳折扣優先序：public_code > user_coupon > auto_checkout | §4.4 | 不在 admin 範圍（store 結帳邏輯）| ✓ |
| 系統類型停用後不再自動發放、已發放不受影響 | §4.6 | 編輯 dialog 顯示 ⚠️ 警語 | ✓ |
| auto_checkout 用 start_at/end_at 絕對日期 | §4.6 | autoCheckoutCreateSchema 含 datetime | ✓ |
| 系統類型用 valid_days 相對日期 | §4.6 | editConfigSchema params 動態驗證 | ✓ |
| 快照機制（user_coupons 記錄發放當時參數）| §4.6 | admin 不需處理（後端機制）| ✓ |
| 退款撤銷 / 失效邏輯 | §4.8 | F04 訂單退款流程觸發，本模組不做 | ✓ |
| 批次發放 manual | §4.5 | IssueCouponsDialog | ✓ |
| 使用統計（總發放/總使用/折扣總額/月趨勢）| §4.5 | CouponConfigStatsPage | ✓ |
| promo_code 唯一 code | §4.6 | zod regex + 後端 409 處理 | ✓ |
| max_total_uses null = 無限 / max_per_user 預設 1 | §4.6 | zod nullable + default(1) | ✓ |

---

## 3. EVENT_MATRIX 副作用比對（admin 觸發的事件）

| Event | 動作 | 副作用 | 前端責任 | 結果 |
|---|---|---|---|---|
| E43 admin 手動發券 | POST /admin/users/issue-coupons | INSERT user_coupons | dialog 提交 + invalidate | ✓ |
| 編輯 coupon_config | PATCH config | UPDATE coupon_configs（不影響已發放快照）| dialog 提交 + invalidate | ✓ |
| 編輯 / 新增 / 刪除 auto_checkout | PATCH/POST/DELETE | UPDATE / INSERT / DELETE | dialog 提交 + invalidate | ✓ |
| CRUD promo_code | POST/PUT/DELETE | UPDATE promo_codes | dialog + invalidate | ✓ |

被動觀察的事件（admin 不直接觸發）：
- E02 email 驗證 → 自動發 new_user
- E19/E23/E24/E25/E40 訂單流程 → 折扣券處理
- E41/E42 退款 → 折扣券撤銷
- E44 結帳套用折扣

---

## 4. admin_routes.md 路由比對

| 規定路由 | 規劃書對應 | 結果 |
|---|---|---|
| `/admin/discounts` | DiscountsPage（含三 tab） | ✓ |
| 〈無明確路由，但需 stats 頁〉 | `/admin/discounts/configs/:id/stats` → CouponConfigStatsPage（自加） | ✓ |

---

## 5. 手動測試覆蓋表

對應 `F08_discounts.md §7` 已列 22 個 case，含 happy / 錯誤 / 邊界 / 響應式。

---

## 6. 差異與待確認

### ⚠️1 UserCoupons 批次發放 user 選取 UX
- 規格沒明示。第一版用 UUID 貼，後續 F13 用戶管理做完再升級。
- **傾向 A**：先 UUID 貼

### ⚠️2 使用統計圖表
- 第一版用表格，echarts 留 F11
- **傾向 A**：先表格

### ⚠️3 promo_code 自動 uppercase
- 規格沒明示，後端是否區分大小寫不明（`code` 是 UNIQUE 列）
- **傾向 A**：前端 input 自動 toUpperCase

### ⚠️4 user_coupons 「public_code」coupon_type 篩選
- spec 隱含此分類但 user_coupons 表沒此欄位
- **傾向**：UI 先列 6 種選項（含 public_code），打 API 失敗再降級為 client 端 filter

### ⚠️5 管理員手動撤銷 user_coupon
- spec 沒此 endpoint，後端 OpenAPI 也沒有
- **傾向**：本輪不做，列 backlog

### 結論

- 全部規格 + API 對齊，無 ⚠️ 阻塞。
- 5 個小決策都傾向「先做 A，需要時再升級」。

**有 ⚠️1–⚠️4 共 4 項決策待你拍板。我的傾向 = 全 A**（⚠️5 是 backlog 不需確認）。同意「全 A」就告訴我，直接開工。
