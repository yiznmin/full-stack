# 後端開發規範

---

## 1. 專案結構

按功能模組組織，每個模組自成一個資料夾：

```
backend/
├── main.py                  # FastAPI app 入口
├── core/
│   ├── config.py            # Pydantic BaseSettings 環境設定
│   ├── database.py          # SQLAlchemy async engine / session
│   ├── exceptions.py        # 自訂 Exception class
│   └── exception_handlers.py# 全域 Exception handler
├── dependencies/
│   └── auth.py              # JWT 解析、require_auth、require_admin
├── {module}/                # 每個功能模組（auth、orders、products...）
│   ├── router.py            # FastAPI router（endpoint 定義）
│   ├── service.py           # 業務邏輯（DB 操作、交易）
│   ├── models.py            # SQLAlchemy ORM model
│   └── schemas/
│       ├── request.py       # Pydantic Request schema
│       └── response.py      # Pydantic Response schema
├── migrations/              # Alembic migration 檔
│   └── versions/
└── tests/
    └── {module}/            # 各模組 integration test
```

---

## 2. 資料庫

- **ORM**：SQLAlchemy 2.x async（`AsyncSession`）
- **Driver**：asyncpg
- **Migration**：Alembic（每次 schema 變更必須產生 migration 檔）
- **交易**：涉及多表寫入一律使用 `async with session.begin()`
- **並發保護**：庫存扣減、訂單狀態變更使用 `SELECT FOR UPDATE`

---

## 3. 非同步

- 所有 route、service function、DB 呼叫全部使用 `async/await`
- Celery task 例外（Celery 使用同步 worker，不混入 async session）

---

## 4. 環境設定

使用 Pydantic `BaseSettings`，自動讀取環境變數：

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    firebase_credentials: str
    resend_api_key: str
    ...

settings = Settings()
```

- 本地開發用 `.env` 檔（加入 `.gitignore`）
- Railway production 直接設環境變數，不需要 `.env`

---

## 5. 錯誤處理

### 5.1 Exception Class 定義

自訂 Exception class，全域 handler 統一轉 HTTP 回應，route / service 內一律 raise 自訂 Exception，不直接使用 `HTTPException`。

```python
# core/exceptions.py
class AppError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class BadRequestError(AppError):
    def __init__(self, detail: str = "請求無法處理"):
        super().__init__(400, detail)

class UnauthorizedError(AppError):
    def __init__(self, detail: str = "請先登入"):
        super().__init__(401, detail)

class ForbiddenError(AppError):
    def __init__(self, detail: str = "權限不足"):
        super().__init__(403, detail)

class NotFoundError(AppError):
    def __init__(self, detail: str = "資源不存在"):
        super().__init__(404, detail)

class ConflictError(AppError):
    def __init__(self, detail: str = "資料衝突"):
        super().__init__(409, detail)

class ExternalServiceError(AppError):
    def __init__(self, detail: str = "外部服務異常，請稍後再試"):
        super().__init__(503, detail)
```

```python
# core/exception_handlers.py
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

async def unhandled_error_handler(request: Request, exc: Exception):
    # 未預期錯誤：寫 log，回傳 500
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "伺服器內部錯誤"})
```

### 5.2 Exception 與狀態碼對應

| HTTP 狀態碼 | Exception class | 典型情境 |
|------------|----------------|---------|
| 400 | `BadRequestError` | 取消已出貨訂單、非法狀態轉換 |
| 401 | `UnauthorizedError` | JWT 無效、`is_active=false` |
| 403 | `ForbiddenError` | customer 存取 admin 路由、操作他人資料 |
| 404 | `NotFoundError` | 訂單、商品、用戶不存在 |
| 409 | `ConflictError` | email 重複、管理員停用自己 |
| 500 | 全域 handler 捕捉 | 未預期錯誤，寫 log，不暴露內部訊息 |
| 503 | `ExternalServiceError` | ECpay / Firebase API 失敗 |

> 回應格式規範見 [api.md](api.md) 通用規則區。

### 5.3 外部服務失敗處理

| 服務 | 失敗行為 |
|------|---------|
| ECpay | `raise ExternalServiceError`，訂單狀態不變，前端顯示錯誤可重試 |
| Firebase Storage | `raise ExternalServiceError`，Celery task 標記 failed，`on_failure` 回呼清理已上傳的孤兒檔案 |
| Resend（email）| **不 raise**，寫 warning log，不因寄信失敗影響主流程，主流程繼續執行 |

### 5.5 DB 連線 / 未預期錯誤

- DB 連線失敗、未捕捉的 Python exception → 由全域 `unhandled_error_handler` 捕捉，回傳 500，寫 error log
- 不在 route / service 層處理，讓全域 handler 統一負責

---

## 6. Router 規範

每個 endpoint 必須明確宣告 `response_model`，不可省略：

```python
# ✅ 正確
@router.post("/auth/register", status_code=201, response_model=MessageResponse)
async def register(...):
    ...

# ❌ 錯誤（Swagger 文件顯示錯誤，前端不知道回傳格式）
@router.post("/auth/register", status_code=201)
async def register(...):
    ...
```

`response_model` 的作用：
1. Swagger 文件顯示正確的回傳格式
2. FastAPI 自動過濾多餘欄位（防止洩漏敏感資料）
3. 前端開發者可以清楚知道每個 API 回傳什麼

---

## 7. Schema 命名規範

| 用途 | 命名範例 |
|------|---------|
| 建立請求 | `OrderCreateRequest` |
| 更新請求 | `OrderUpdateRequest` |
| 單筆回應 | `OrderResponse` |
| 列表回應 | `OrderListResponse` |
| 分頁回應（通用）| `PaginatedResponse[OrderResponse]` |

---

## 8. 命名規範

| 項目 | 風格 | 範例 |
|------|------|------|
| 檔案名 | snake_case | `order_service.py` |
| Class | PascalCase | `OrderService` |
| 函式 / 變數 | snake_case | `get_order_by_id` |
| 常數 | UPPER_SNAKE_CASE | `JWT_ALGORITHM` |
| API route | kebab-case | `/admin/coupon-configs`、`/admin/custom-requests` |
| DB 欄位 | snake_case | `payment_deadline` |

---

## 9. 測試

- **框架**：pytest + httpx `AsyncClient`
- **策略**：Integration test 為主，直接打測試資料庫，不 mock DB
- **測試資料庫**：獨立 PostgreSQL（Railway 可開 test 環境，或本地 Docker）
- **每個模組**對應 `tests/{module}/` 資料夾
- **必測項目**：
  - 正常流程（happy path）
  - 權限驗證（未登入、權限不足）
  - 業務規則邊界（庫存不足、折扣衝突、狀態機非法轉換）

---

## 10. 分頁回應格式

所有列表 API 統一格式：

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

---

## 11. JWT 認證

- Token 存於 `httpOnly cookie`（`access_token`）
- Payload：`{ user_id, role, exp }`
- 過期時間：customer 7 天，admin 8 小時
- 每次請求驗證 `users.is_active`（帳號停用立即踢出，回 401）
- `require_auth` dependency：需登入（customer 或 admin）
- `require_admin` dependency：需 `role=admin`
