# 功能需求規格 — 索引

詳細需求各模組文件位於 `docs/` 根目錄。

---

## 總覽與規範

| 文件 | 說明 | 狀態 |
|------|------|------|
| [OVERVIEW.md](OVERVIEW.md) | 系統總覽與地圖 | 完成 |
| [architecture.md](architecture.md) | 架構與技術棧 | 完成 |
| [schema.md](schema.md) | 資料庫 schema 總表 | 完成 |
| [api.md](api.md) | API 規格總表 | 完成 |
| [backend_conventions.md](backend_conventions.md) | 後端開發規範 | 完成 |
| [implementation_plan.md](implementation_plan.md) | 實作規劃 | 完成 |
| [implementation_questions.md](implementation_questions.md) | 實作待確認問題 | 進行中 |

---

## 定價

| 文件 | 狀態 |
|------|------|
| [pricing_formula.md](pricing_formula.md) | 完成 |

---

## 共用

| 模組 | 檔案 | 狀態 |
|------|------|------|
| 使用者系統（註冊 / 登入 / 收件資料 / JWT）| [auth_users.md](auth_users.md) | 完成 |

---

## 管理者端

| 模組 | 檔案 | 狀態 |
|------|------|------|
| 路由結構 | [admin_routes.md](admin_routes.md) | 完成 |
| 1. 製作模組 | [admin_production.md](admin_production.md) | 完成 |
| 2. 填色色號對應實體色管理 | [admin_color.md](admin_color.md) | 完成 |
| 3. 商品管理 | [admin_product.md](admin_product.md) | 完成 |
| 4. 折扣券管理 | [admin_discount.md](admin_discount.md) | 完成 |
| 5. 客戶訂單管理 | [admin_orders.md](admin_orders.md) | 完成 |
| 6. 內容管理 | [admin_content.md](admin_content.md) | 完成 |
| 7. 通知系統 | [admin_notifications.md](admin_notifications.md) | 完成 |

---

## 用戶商店端

| 模組 | 檔案 | 狀態 |
|------|------|------|
| 路由結構 | [store_routes.md](store_routes.md) | 完成 |
| 1. 瀏覽與購買 | [store_browse.md](store_browse.md) | 完成 |
| 2. 會員系統 | [store_auth.md](store_auth.md) | 完成 |
| 3. 訂單管理 | [store_orders.md](store_orders.md) | 完成 |
| 4. 客製化商品頁 | [store_custom.md](store_custom.md) | 完成 |
| 5. 資訊頁 | [store_info.md](store_info.md) | 完成 |

---

## 參考與稽核

| 文件 | 說明 | 狀態 |
|------|------|------|
| [EVENT_MATRIX.md](EVENT_MATRIX.md) | 全系統事件 → 狀態 → 通知對照表 | 完成 |
| [CONSISTENCY_CHECK.md](CONSISTENCY_CHECK.md) | 規格一致性稽核清單 | 全部已解 |

---

## 模組間的上架流程依賴

```
製作模組（status=completed, approved=true）
    ↓
實體色對應模組（所有 template_id 對應完成）
    ↓
商品管理模組（建立商品、設定定價、上架）
    ↓
用戶商店（瀏覽、購買、下載）
```
