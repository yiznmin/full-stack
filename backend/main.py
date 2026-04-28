# ruff: noqa: I001
# _windows_compat MUST run before any module that imports asyncpg (WMI workaround for
# broken Windows dev machines). Ruff would resort imports otherwise.
import core._windows_compat  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.exception_handlers import app_error_handler, unhandled_error_handler
from core.exceptions import AppError

app = FastAPI(title="PaintLearn API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, settings.admin_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health")
async def health():
    return {"status": "ok"}


from admin.router import router as admin_router
from auth.router import router as auth_router
from color.router import router as color_router
from content.router import router as content_router
from custom.router import router as custom_router
from discount.router import router as discount_router
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
