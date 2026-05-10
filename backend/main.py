# ruff: noqa: I001
# _windows_compat MUST run before any module that imports asyncpg (WMI workaround for
# broken Windows dev machines). Ruff would resort imports otherwise.
import core._windows_compat  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.exception_handlers import app_error_handler, unhandled_error_handler
from core.exceptions import AppError
from core.security_headers import SecurityHeadersMiddleware

app = FastAPI(title="PaintLearn API", version="1.0.0")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, settings.admin_url],
    allow_credentials=True,
    # 收斂方法白名單（替代 ["*"]）— SAFE 方法 + 我們實際使用的 mutation 動詞 + OPTIONS preflight
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    # 限制 headers — 只允許前端實際會送的，避免 attacker 利用 echo 探測 internal headers
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
    ],
    # response 暴露給 JS 的 headers — 我們不需要任何特殊 response header 給前端讀
    expose_headers=[],
    max_age=600,
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


# Liveness probe（只驗 process 存活）— 不查 DB / Redis / Firebase。
# 刻意不做 readiness 檢查：避免 DB 短暫斷線就觸發 Railway 把 web service 重啟，
# 反而拉長恢復時間。若 DB 永久壞掉，內部 API 會自然回 500（前端可看到具體錯誤）。
@app.get("/health")
async def health():
    return {"status": "ok"}


from admin.router import router as admin_router
from auth.router import router as auth_router
from color.router import router as color_router
from content.router import router as content_router
from custom.router import router as custom_router
from discount.router import router as discount_router
from logistics.router import router as logistics_router
from notifications.router import router as notifications_router
from orders.router import router as orders_router
from palette.router import router as palette_router
from print_batch.router import router as print_batch_router
from product.router import router as product_router
from production.router import router as production_router
from reports.router import router as reports_router
from upload.router import router as upload_router
from users.router import router as users_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(production_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(color_router, prefix="/api/v1")
app.include_router(palette_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")
app.include_router(discount_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(custom_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(print_batch_router, prefix="/api/v1")
app.include_router(logistics_router, prefix="/api/v1")


# ── Startup: idempotent reference data seed ─────────────────────────────────
# 某些環境 alembic bulk_insert seed 沒生效（dev / Railway prod 都遇過 canvas_sizes
# 為空）。這裡用 ON CONFLICT DO NOTHING 補；既有資料不動，admin 後台改的不會被洗。
@app.on_event("startup")
async def _bootstrap_seeds() -> None:
    from core.database import engine as _engine
    from custom.bootstrap import ensure_canvas_sizes
    await ensure_canvas_sizes(_engine)
