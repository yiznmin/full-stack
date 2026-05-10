"""Security headers middleware — 防禦性 HTTP headers。

涵蓋：
- X-Content-Type-Options：禁止 MIME sniffing（防 XSS via 偽造 type）
- X-Frame-Options：禁止站外 iframe（防 clickjacking）
- Referrer-Policy：限制 referer 洩漏
- Strict-Transport-Security：強制 HTTPS（Railway 已有 SSL，加 HSTS 1 年）
- Content-Security-Policy：API-only 嚴格 CSP（不該有 inline script、外部資源）
- Permissions-Policy：禁用不需要的瀏覽器特權

API 端 CSP 比一般網站更嚴 — 我們不渲染 HTML 給瀏覽器（除了 Swagger /docs），
所以 default-src 'none' 是合理 baseline。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# Swagger / ReDoc 需要的路徑 — CSP 放寬
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # 一律加上的基本 headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # HSTS — 強制 HTTPS 1 年（subdomains 包含、preload list 候選）
        # 只在 https 才送（避免 dev http 被永久綁定）
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # CSP — Swagger 路徑放寬給 ReDoc / Swagger UI inline JS / CDN
        # 其他 API endpoint 給最嚴格的 default-src 'none'
        if any(request.url.path.startswith(p) for p in _DOCS_PATHS):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )

        return response
