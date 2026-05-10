# S07 — 客製申請（會員端）

> 對應 [docs/store_design_brief.md](../../../docs/store_design_brief.md) #11–14、後端 [backend/custom/router.py](../../../backend/custom/router.py)
>
> **追溯規劃書**：先實作後補寫。

---

## 1. 範圍

| Brief # | 頁面 | URL | Auth |
|---|---|---|---|
| #11 | 客製服務 hub + about + cases | `/custom`、`/custom/about`、`/custom/cases` | 公開 |
| #12 | 申請表單 | `/custom/apply` | 公開（送出時要求登入） |
| #13 | 我的申請列表 | `/custom/requests` | requiresAuth |
| #14 | 申請詳情 + 訊息 + SSE | `/custom/requests/:id` | requiresAuth |

---

## 2. 檔案清單

```
store/src/features/custom/
├── api.ts                          # custom-requests CRUD + messages
├── queries.ts                      # useCustomRequestsQuery, useCreateCustomRequestMutation
├── upload.ts                       # uploadCustomPhoto（私密路徑 signed URL）
├── composables/
│   └── usePendingFormStorage.ts    # 未登入時暫存 form draft（localStorage）
├── components/
│   └── CustomApplyForm.vue         # 5 step：照片 / 規格 / 難度 / 備註 / 展示授權
└── pages/
    ├── CustomPage.vue              # hub
    ├── CustomAboutPage.vue         # 服務介紹
    ├── CustomCasesPage.vue         # 案例分享
    ├── CustomApplyPage.vue         # 申請（含報價參考 banner）
    ├── CustomRequestListPage.vue
    └── CustomRequestDetailPage.vue # 含 messages + SSE
```

---

## 3. 申請流程（CustomApplyForm 5 step）

| Step | 內容 | 必填 |
|---|---|---|
| 01 | 上傳照片（JPEG / PNG，10MB） | ✓ |
| 02 | 畫布尺寸（17 種 standard 或 custom） | ✓ |
| 03 | 難易度（4 階 + 「讓管理員建議」） | ✓ |
| 04 | 給我們的備註（< 2000 chars） | 選填 |
| 05 | 展示授權 checkbox（spec 第 9 頁智財權條款） | 選填 |

**未登入時送出**：暫存 form 進 localStorage、redirect `/login`，登入後自動 resume。

---

## 4. 申請狀態流

```
quote_pending → negotiating（客戶要求修改最多 3 次）
                → quoted （admin 報價）
                  → in_cart （客戶確認加入購物車）
                  → rejected
                → expired （24h 未確認）
```

---

## 5. SSE 即時訊息

訂閱 `GET /custom-requests/:id/sse`：admin 回訊息 / 報價時即時推送，自動 invalidate cache。

---

## 6. Contextual triggers

- 申請頁上方「不確定多少錢？」banner → InfoDrawer 開報價參考（`b3bdb18`）
- 申請完成 success state 內嵌「接下來會發生什麼」3 步說明（`b3bdb18`）

---

## 7. 事後修正項

- display_consent 欄位 + UI checkbox + admin 顯示（`e2a44dc`）
- 客製照片 read 用 signed URL 簽（`e7277b3`）
- 審稿頁綁定 admin 選定的 production_job（`34a26af`）
- 重新設計詳情頁（`da427ad`）
