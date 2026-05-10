"""Auth endpoint 速率限制 — Redis 計數器 + sliding TTL。

防護目標：login / register / forgot-password / reset-password 被 brute force。

設計：
- 用 Redis INCR + EXPIRE 做固定窗口計數（簡單、原子）
- key: `ratelimit:{endpoint}:{ip_or_identifier}`
- 第一次 INCR 得到 1 → 設 EXPIRE = window_seconds
- 之後每次 INCR 比對 limit；超過 → 503 + Retry-After header
- Redis 不可用時 fail-open（不擋）— 避免 Redis 短暫斷線就鎖死所有登入

Fail-open 是刻意選擇：rate limit 是縱深防禦的一層，不是唯一防線。
應用層其他保護（強密碼策略、bcrypt、JWT expire）仍在；Redis 故障時 graceful degrade。
"""
from __future__ import annotations

import logging

import redis.asyncio as redis_async
from fastapi import HTTPException, Request, status

from core.config import settings

logger = logging.getLogger(__name__)

# 全域 Redis client — 第一次呼叫 lazy 建立
_client: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis:
    global _client
    if _client is None:
        _client = redis_async.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    return _client


async def check_rate_limit(
    *,
    key_id: str,
    endpoint: str,
    limit: int,
    window_sec: int,
) -> None:
    """檢查 (endpoint, key_id) 在 window_sec 內是否超過 limit 次。

    超過 → raise HTTPException 429 with Retry-After header
    Redis 不可用 → 不擋（fail-open + log warning）
    """
    redis_key = f"ratelimit:{endpoint}:{key_id}"
    try:
        client = _get_redis()
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, window_sec)
        if count > limit:
            ttl = await client.ttl(redis_key)
            retry_after = max(ttl, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"嘗試次數過多，請於 {retry_after} 秒後再試",
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except Exception as e:
        # Redis 不可用 → fail-open，不擋使用者
        logger.warning("rate limit check failed (fail-open): %s", e)


def _client_ip(request: Request) -> str:
    """從 X-Forwarded-For（Railway proxy）抽 client IP，否則用直接 client。"""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # X-Forwarded-For 可能是 "client, proxy1, proxy2" — 取第一個
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── FastAPI dependencies ──────────────────────────────────────────────────────


async def rate_limit_login(request: Request) -> None:
    """Login: 10 次 / 15 分鐘 / IP."""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="login",
        limit=10,
        window_sec=15 * 60,
    )


async def rate_limit_register(request: Request) -> None:
    """Register: 5 次 / 60 分鐘 / IP."""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="register",
        limit=5,
        window_sec=60 * 60,
    )


async def rate_limit_forgot_password(request: Request) -> None:
    """Forgot-password: 3 次 / 60 分鐘 / IP."""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="forgot",
        limit=3,
        window_sec=60 * 60,
    )


async def rate_limit_reset_password(request: Request) -> None:
    """Reset-password: 5 次 / 60 分鐘 / IP."""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="reset",
        limit=5,
        window_sec=60 * 60,
    )


async def rate_limit_admin_login(request: Request) -> None:
    """Admin login: 5 次 / 15 分鐘 / IP — 比 customer 嚴一階。"""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="admin_login",
        limit=5,
        window_sec=15 * 60,
    )


async def rate_limit_resend_verification(request: Request) -> None:
    """Resend verification: 3 次 / 60 分鐘 / IP."""
    await check_rate_limit(
        key_id=_client_ip(request),
        endpoint="resend_verify",
        limit=3,
        window_sec=60 * 60,
    )
