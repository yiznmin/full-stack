# 整體架構

## 系統概覽

```
用戶商店（Vue）          管理介面（Vue）
      ↓                        ↓
      └──────── FastAPI 後端 ────┘
                    ↓
         ┌──────────┴──────────┐
    PostgreSQL            Firebase Storage
    （Railway）            （圖片、SVG、PNG）
                    ↓
              任務佇列（Celery + Redis）
                    ↓
          核心處理引擎（paint-by-number/src/）
```

---

## 技術選型

| 層 | 技術 | 部署 |
|---|---|---|
| 核心處理引擎 | Python（pbn_gen.py） | Railway Worker |
| 後端 API | FastAPI | Railway |
| 資料庫 | PostgreSQL | Railway |
| 任務佇列 | Celery + Redis | Railway |
| 圖片儲存 | Firebase Storage | Firebase |
| 管理介面前端 | Vue 3 | Vercel |
| 用戶商店前端 | Vue 3 | Vercel |
| 會員驗證 | JWT 自建 | — |
| 金流 | 暫無（銀行轉帳） | — |

---

## 前端拆分

### admin（管理介面）
- 管理者登入後才能操作
- 上傳圖片、設定參數、產生模板
- 審核商品、上架管理
- 訂單查詢

### store（用戶商店）
- 用戶註冊 / 登入
- 瀏覽商品、購買
- 查看訂單記錄
- 下載已購買的模板

---

## 後端 API 共用

- `admin` 和 `store` 共用同一個 FastAPI 後端
- 透過 JWT 角色區分（`role: admin` / `role: user`）
- Admin 路由加 `require_admin` 依賴保護

---

## 處理流程

```
1. 管理者上傳圖片 → Firebase Storage
2. 建立處理任務 → PostgreSQL（production_jobs 表）
3. Celery Worker 取任務 → 呼叫 pbn_gen.py
4. 輸出檔案（SVG / PNG / JSON）→ Firebase Storage
5. 任務完成 → 更新 PostgreSQL
6. 管理者後處理調整 → 審核通過
7. 管理者完成實體色對應 → 上架為商品
8. 用戶下單 → 銀行轉帳付款（24 小時內）
9. 管理者確認付款 → 備貨（印製模板 + 備妥顏料套組）
10. 宅配到府 或 超商店到店（7-11 / 全家）出貨
```

---

## 資料夾結構

```
PaintLearn/
├── CLAUDE.md
├── docs/
│   ├── requirements.md
│   ├── schema.md
│   ├── api.md
│   └── architecture.md         ← 本文件
├── paint-by-number/            ← 核心處理引擎（勿動）
│   └── src/
│       ├── pbn_gen.py
│       └── run.py
├── backend/                    ← FastAPI + Celery
│   ├── app/
│   │   ├── api/                ← 路由
│   │   ├── models/             ← SQLAlchemy 資料模型
│   │   ├── schemas/            ← Pydantic 驗證
│   │   ├── services/           ← 商業邏輯
│   │   └── workers/            ← Celery 任務
│   ├── main.py
│   └── requirements.txt
├── admin/                      ← Vue 管理介面
└── store/                      ← Vue 用戶商店
```
