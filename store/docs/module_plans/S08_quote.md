# S08 — 報價確認頁（token-based）

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #15–16、後端 [backend/customer_quote/router.py](../../../backend/customer_quote/router.py)
>
> **追溯規劃書**：先實作後補寫。

---

## 1. 範圍

| Brief # | 頁面 | URL | Auth |
|---|---|---|---|
| #15 | 報價確認 viewer | `/custom/quote/:token` | **token 驗證**（不需登入 cookie） |
| #16 | 客製結帳（confirm 後加入購物車）| 無獨立 URL，在 viewer 內按鈕觸發 → `/cart` | requiresAuth（confirm action） |

---

## 2. 檔案清單

```
store/src/features/custom/
└── pages/
    └── QuotePage.vue           # token-based 報價 viewer
```

---

## 3. 設計重點

**為什麼 token-based 不走 session auth**：
- admin 寄 email 含 quote link，客戶可能未登入即點開預覽
- token 對 owner 不是 secret（owner 自己的 detail 也能拿到 token）
- 但對非 owner 來說 token 即訪問憑證 → 限 24h 過期 + view_count tracking

---

## 4. 流程

1. admin QuoteDialog 送出報價 → 生成 quote_token + 寄 email
2. 客戶點 link → `/custom/quote/:token`
3. 後端 `_load_request_by_token` 雙路徑比對（plain / hash）→ 載入 request 詳情 + filled_template_url
4. 客戶可選：
   - **加入購物車**：confirm → 建 cart_item（custom_request_id + production_job_id）→ redirect `/cart`
   - **要求修改**：post message + 計入 revision_count（最多 3 次）
   - **拒絕**：req.status = rejected

---

## 5. Layout

採 `MinimalLayout`（無 site header / footer），讓 quote viewer 像獨立預覽頁。

---

## 6. 事後修正項

- 報價綁 admin 選定的 production_job（`34a26af`）
- 客戶從詳情頁直接進報價 viewer（`64eaebd`）
- 報價確認改成「加入購物車」+ 客製商品免運門檻（`ac4a243`）
- 「讓管理員建議」時 admin 也能算客製化價格（`d7d60e3`）

---

## 7. 安全

- token TTL 24h（admin 可延長一次 +24h）
- view_count + last_viewed_at 追蹤（防 token 流到競品 / 廠商）
- confirm action 仍走 require_auth（要 cookie）— 即便 token 洩漏，攻擊者也無法以受害者帳號加購物車
