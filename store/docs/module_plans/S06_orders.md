# S06 — 訂單管理

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #8–10、後端 [backend/orders/router.py](../../../backend/orders/router.py)
>
> **追溯規劃書**：先實作後補寫。

---

## 1. 範圍

| Brief # | 頁面 | URL | Auth |
|---|---|---|---|
| #8 | 訂單列表 | `/orders` | requiresAuth |
| #9 | 訂單詳情 | `/orders/:id` | requiresAuth |
| #10 | 付款核對表單 | `/orders/:id`（內嵌 PaymentForm） | requiresAuth |

---

## 2. 檔案清單

```
store/src/features/orders/
├── api.ts
├── queries.ts                # useOrdersQuery, useOrderDetailQuery, useSubmitPaymentMutation
├── useOrderSse.ts            # SSE composable: status / shipment 即時通知
└── pages/
    ├── OrderListPage.vue     # 5 個 tab: unpaid / shipping / completed / cancelled / refund
    └── OrderDetailPage.vue   # stepper + 退款 banner + 付款 + 取消 + 確認收貨
```

---

## 3. 訂單狀態 → tab 分類

對應 backend OrderStatusEnum 完整 10 個狀態：

| Tab | Statuses |
|---|---|
| 待付款 | pending_payment、payment_expired |
| 出貨中 | paid、processing、shipped |
| 已完成 | completed |
| 已取消 | cancelled |
| 退款 | refund_processing、refunded、partially_refunded |

---

## 4. 進度 timeline（OrderDetailPage 5-step stepper）

5 step + lucide icon + connecting line progress fill + pulse current step：

| Step | Icon | timestamp |
|---|---|---|
| 待付款 | Wallet | created_at |
| 已付款 | CheckCircle2 | paid_at |
| 製作中 | Hammer | paid_at |
| 已出貨 | Truck | shipments[0].shipped_at |
| 已完成 | Sparkles | completed_at |

cancelled / refund_* 不顯示 stepper，改 banner（`ed983ae` + `e2a44dc`）。

---

## 5. SSE 即時通知

訂閱 `GET /orders/:id/sse`，事件類型：
- `status_changed`：admin 標 paid / 出貨 / webhook 收 ECpay 狀態
- `shipment_created`：admin 建出貨（含 tracking）
- `shipment_status_changed`：ECpay webhook 推狀態（在途 / 到店 / 已取貨）

事件到達自動 invalidate query cache + toast 提示。

---

## 6. Contextual triggers

- 退款 banner 內「了解退款政策 →」 → InfoDrawer（`b3bdb18`）

---

## 7. 事後修正項

- timeline 視覺從純編號圈圈升級為 lucide icon + 漸層 fill（`e2a44dc`）
- list 從「進行中 / 已完成」2 tab 細分為 5 tab（`e574618`）
