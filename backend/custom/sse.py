"""客製訂單模組 SSE pub/sub helper。

兩個訂閱：
- 客戶端：subscribe_customer(request_id) → 該 request 的訊息流
- 管理員：subscribe_admin() → 全局訊息／新申請通知

設計：
- in-memory pub/sub（單 worker 部署 OK；多 worker 要改 Redis）
- 每個 subscriber 拿一個 asyncio.Queue
- publish 不 await — 用 put_nowait，queue 滿就 drop（避免拖慢 producer）
- 30 秒 heartbeat 防 Railway 切連線

對應規格：docs/module_plans/21_store_custom_frontend.md §2
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

QUEUE_MAX_SIZE = 32
HEARTBEAT_INTERVAL_SEC = 30


class SSEHub:
    """In-memory pub/sub for SSE subscribers."""

    def __init__(self) -> None:
        # request_id -> list of subscriber queues
        self._customer_subs: dict[UUID, list[asyncio.Queue[bytes]]] = {}
        # admin global subscriber list
        self._admin_subs: list[asyncio.Queue[bytes]] = []

    # ── subscribe ────────────────────────────────────────────────────────

    def subscribe_customer(self, request_id: UUID) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._customer_subs.setdefault(request_id, []).append(q)
        return q

    def unsubscribe_customer(self, request_id: UUID, q: asyncio.Queue[bytes]) -> None:
        subs = self._customer_subs.get(request_id)
        if not subs:
            return
        with suppress(ValueError):
            subs.remove(q)
        if not subs:
            self._customer_subs.pop(request_id, None)

    def subscribe_admin(self) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._admin_subs.append(q)
        return q

    def unsubscribe_admin(self, q: asyncio.Queue[bytes]) -> None:
        with suppress(ValueError):
            self._admin_subs.remove(q)

    # ── publish ──────────────────────────────────────────────────────────

    def publish_to_customer(self, request_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        """Push event to all subscribers of a specific custom_request."""
        payload = _format_sse(event_type, data)
        subs = self._customer_subs.get(request_id, [])
        for q in subs:
            self._try_put(q, payload, label=f"customer:{request_id}")

    def publish_to_admin(self, event_type: str, data: dict[str, Any]) -> None:
        """Push event to all admin subscribers."""
        payload = _format_sse(event_type, data)
        for q in self._admin_subs:
            self._try_put(q, payload, label="admin")

    @staticmethod
    def _try_put(q: asyncio.Queue[bytes], payload: bytes, *, label: str) -> None:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(f"[sse] queue full, drop event on {label}")

    # ── streaming ────────────────────────────────────────────────────────

    @staticmethod
    async def stream(q: asyncio.Queue[bytes]) -> AsyncGenerator[bytes, None]:
        """Async generator for FastAPI StreamingResponse.

        Yields events from queue + heartbeat every 30s. Exits on cancellation.
        """
        # 開頭 retry hint: 客戶端斷線時 EventSource 自動重連間隔 5 秒
        yield b"retry: 5000\n\n"
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL_SEC)
                    yield payload
                except TimeoutError:
                    # 沒事件 → 推 heartbeat 防代理 / 瀏覽器切連線
                    yield b": heartbeat\n\n"
        except asyncio.CancelledError:
            # 客戶端 disconnect → caller 會 unsubscribe
            raise


def _format_sse(event_type: str, data: dict[str, Any]) -> bytes:
    """Format dict as SSE event bytes.

    SSE spec: each event is "event: TYPE\ndata: JSON\n\n"
    """
    body = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {body}\n\n".encode()


# 單例 hub（整個 process 共用）
hub = SSEHub()
