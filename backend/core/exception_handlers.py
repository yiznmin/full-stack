import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import AppError

logger = logging.getLogger(__name__)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    body: dict = {"detail": exc.detail}
    if exc.code is not None:
        body["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=body)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "伺服器內部錯誤"})
