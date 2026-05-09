"""SSE Hub 煙霧測試 — 驗證 pub/sub + heartbeat + 多訂閱者。

執行：cd backend && venv/Scripts/python scripts/smoke_test_sse.py
不依賴 DB / FastAPI server，純邏輯層驗證。
"""
import asyncio
from uuid import uuid4

from custom.sse import SSEHub


async def test_customer_pubsub():
    hub = SSEHub()
    rid = uuid4()
    q = hub.subscribe_customer(rid)

    hub.publish_to_customer(rid, "new_message", {"id": "abc", "msg": "hi"})

    payload = await asyncio.wait_for(q.get(), timeout=1.0)
    assert b"event: new_message" in payload, f"event header missing: {payload!r}"
    assert b'"id": "abc"' in payload, f"data missing: {payload!r}"
    assert payload.endswith(b"\n\n"), "SSE frame must end with blank line"
    print(f"  ✓ customer pub/sub: {payload!r}")

    hub.unsubscribe_customer(rid, q)
    assert rid not in hub._customer_subs, "request should be removed when last subscriber leaves"
    print("  ✓ unsubscribe cleans up empty bucket")


async def test_admin_pubsub():
    hub = SSEHub()
    q1 = hub.subscribe_admin()
    q2 = hub.subscribe_admin()

    hub.publish_to_admin("new_request", {"request_id": "xyz"})

    p1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    p2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert p1 == p2, "all admin subscribers should get same payload"
    assert b"event: new_request" in p1
    print(f"  ✓ admin fan-out: 2/2 subs received → {p1!r}")

    hub.unsubscribe_admin(q1)
    hub.unsubscribe_admin(q2)
    assert hub._admin_subs == [], "admin list should be empty after unsubs"
    print("  ✓ admin unsubscribe cleans up")


async def test_isolation_across_requests():
    """訂閱 request A 不應收到 request B 的事件。"""
    hub = SSEHub()
    a, b = uuid4(), uuid4()
    qa = hub.subscribe_customer(a)
    qb = hub.subscribe_customer(b)

    hub.publish_to_customer(a, "new_message", {"x": 1})

    pa = await asyncio.wait_for(qa.get(), timeout=1.0)
    assert b'"x": 1' in pa
    assert qb.empty(), "request B subscriber must not receive request A event"
    print("  ✓ per-request isolation OK")


async def test_stream_emits_retry_then_event():
    """stream() 應先 yield retry hint，再 yield event。"""
    hub = SSEHub()
    rid = uuid4()
    q = hub.subscribe_customer(rid)

    gen = hub.stream(q)
    first = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert first == b"retry: 5000\n\n", f"first frame should be retry hint, got {first!r}"
    print("  ✓ stream emits retry: 5000 first")

    hub.publish_to_customer(rid, "evt", {"k": "v"})
    second = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert b"event: evt" in second
    print(f"  ✓ stream emits published event next: {second!r}")

    await gen.aclose()


async def test_queue_full_drops_silently():
    """Queue 滿就 drop，不應 raise（避免拖慢 publisher）。"""
    hub = SSEHub()
    rid = uuid4()
    q = hub.subscribe_customer(rid)

    # 填滿（QUEUE_MAX_SIZE = 32）
    for i in range(50):
        hub.publish_to_customer(rid, "spam", {"i": i})

    assert q.qsize() == 32, f"queue size should clamp to 32, got {q.qsize()}"
    print(f"  ✓ queue full drops silently (32/{50} kept)")


async def main():
    print("=== SSE Hub Smoke Test ===\n")

    print("[1] customer pub/sub:")
    await test_customer_pubsub()
    print()

    print("[2] admin fan-out:")
    await test_admin_pubsub()
    print()

    print("[3] per-request isolation:")
    await test_isolation_across_requests()
    print()

    print("[4] stream() framing:")
    await test_stream_emits_retry_then_event()
    print()

    print("[5] queue full drop:")
    await test_queue_full_drops_silently()
    print()

    print("=== ALL PASS ===")


if __name__ == "__main__":
    asyncio.run(main())
