# S05 — 購物車 + 結帳

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #5–7、後端 [backend/orders/router.py](../../../backend/orders/router.py)
>
> **追溯規劃書**：先實作後補寫。

---

## 1. 範圍

| Brief # | 頁面 | URL | Auth |
|---|---|---|---|
| #5 | 購物車 | `/cart` | requiresAuth |
| #6 | 結帳 | `/checkout` | requiresAuth |
| #7 | 完成頁 | `/checkout/complete?order=:id` | requiresAuth |

---

## 2. 檔案清單

```
store/src/features/cart/
├── api.ts                    # cart CRUD + checkout-preview
├── queries.ts                # useCartQuery, useCheckoutPreviewQuery, useCreateOrderMutation
└── pages/
    └── CartPage.vue          # 含免運進度 + 客製 line 識別

store/src/features/checkout/
└── pages/
    ├── CheckoutPage.vue      # 收件地址 + 預購出貨 + 折扣碼 + 備註 + 退款政策同意
    └── CheckoutCompletePage.vue
```

---

## 3. 業務規則

**Cart**：
- 一般商品 line：`product_variant_id` 有值
- 客製商品 line：`custom_request_id + production_job_id` 有值
- 客製不計入免運門檻（金額 + 件數）— 例外：使用免運券時 trump everything

**Checkout 流程**：
1. 收件資料 select（profile）/ 新增 inline form
2. 預購出貨 preference（has_preorder 才顯示）
3. 折扣碼套用
4. 備註（可選）
5. **退款政策同意 checkbox**（必勾才能送出，連 `/refund-policy`）
6. 建單 → redirect `/checkout/complete?order=:id`

---

## 4. API

| Endpoint | 說明 |
|---|---|
| `GET /cart` | 取購物車（含 cart_items + 客製 line） |
| `POST /cart/items` | 加商品 |
| `PATCH /cart/items/:id` | 改數量 |
| `DELETE /cart/items/:id` | 移除 |
| `POST /cart/checkout-preview` | 試算（運費 / 折扣 / 總額） |
| `POST /orders` | 建單 |

---

## 5. Contextual triggers（spec 第 9 頁實作）

- 購物車「運費」row 旁加 ⓘ → InfoDrawer 顯示出貨流程（`b3bdb18`）
- 結帳頁底部「我已閱讀並同意《退款政策》」勾選（早於 `b3bdb18` 已存在）

---

## 6. 事後修正項

- 客製 line 縮圖簽 signed URL（`460802a`）
- pydantic 補齊客製欄位（`fa63500`）
- create_order 支援客製 line（`80c1154`）
