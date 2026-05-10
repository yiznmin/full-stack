"""訂單模組 SSE pub/sub helper。

訂閱對象：
- 客戶端：subscribe_customer(order_id) → 該訂單的狀態變更（paid / shipped / delivered / completed / refund）

設計沿用 custom/sse.py 的 in-memory hub（單 worker 部署，多 worker 改 Redis）。

事件種類：
- status_changed：訂單 status 變動（pending_payment → paid → shipped → completed）
- production_progress：客製訂單製作進度推進（manufacturing / packaging / ready_to_ship）
- shipment_created：admin 建立 shipment（含 tracking）
- shipment_status_changed：ECpay webhook 推狀態（在途 / 到店 / 已取貨）
- refund_processed：admin 處理退款
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


class OrderSSEHub:
    """In-memory pub/sub for order SSE subscribers."""

    def __init__(self) -> None:
        # order_id -> list of subscriber queues
        self._customer_subs: dict[UUID, list[asyncio.Queue[bytes]]] = {}

    # ── subscribe ────────────────────────────────────────────────────────

    def subscribe_customer(self, order_id: UUID) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._customer_subs.setdefault(order_id, []).append(q)
        return q

    def unsubscribe_customer(self, order_id: UUID, q: asyncio.Queue[bytes]) -> None:
        subs = self._customer_subs.get(order_id)
        if not subs:
            return
        with suppress(ValueError):
            subs.remove(q)
        if not subs:
            self._customer_subs.pop(order_id, None)

    # ── publish ──────────────────────────────────────────────────────────

    def publish_to_customer(self, order_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        """Push event to all subscribers of a specific order."""
        payload = _format_sse(event_type, data)
        subs = self._customer_subs.get(order_id, [])
        for q in subs:
            self._try_put(q, payload, label=f"order:{order_id}")

    @staticmethod
    def _try_put(q: asyncio.Queue[bytes], payload: bytes, *, label: str) -> None:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(f"[order-sse] queue full, drop event on {label}")

    # ── streaming ────────────────────────────────────────────────────────

    @staticmethod
    async def stream(q: asyncio.Queue[bytes]) -> AsyncGenerator[bytes, None]:
        yield b"retry: 5000\n\n"
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL_SEC)
                    yield payload
                except TimeoutError:
                    yield b": heartbeat\n\n"
        except asyncio.CancelledError:
            raise


def _format_sse(event_type: str, data: dict[str, Any]) -> bytes:
    body = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {body}\n\n".encode()


# 單例 hub（整個 process 共用）
hub = OrderSSEHub()
