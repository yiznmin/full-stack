"""Integration tests for Module 11 — Notifications."""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from auth.models import User
from notifications.models import AdminNotification, NotificationStatusEnum
from notifications.service import (
    create_notification,
    create_or_update_stock_shortage,
    create_payment_resubmitted,
)

LIST_URL = "/api/v1/admin/notifications"
ADMIN_EMAIL = "notif_admin@test.com"
ADMIN_PASS = "adminpass123"
CUSTOMER_EMAIL = "notif_user@test.com"
CUSTOMER_PASS = "userpass123"


async def _make_admin(db):
    admin = User(
        name="NotifAdmin",
        email=ADMIN_EMAIL,
        password_hash=bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode(),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    await db.commit()
    return admin


async def _make_customer(db):
    user = User(
        name="NotifUser",
        email=CUSTOMER_EMAIL,
        password_hash=bcrypt.hashpw(CUSTOMER_PASS.encode(), bcrypt.gensalt()).decode(),
        role="customer",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _login_admin(client):
    res = await client.post("/api/v1/admin/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _login_customer(client):
    res = await client.post("/api/v1/auth/login", json={
        "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _seed(db, count=3, **defaults):
    """Insert N notifications and return them."""
    notifications = []
    for i in range(count):
        await create_notification(
            db,
            type=defaults.get("type", "test_event"),
            message=f"通知 {i}",
            requires_action=defaults.get("requires_action", True),
            status=defaults.get("status", NotificationStatusEnum.unhandled),
        )
    await db.commit()
    result = await db.execute(select(AdminNotification).order_by(AdminNotification.created_at))
    notifications = list(result.scalars().all())
    return notifications


# ── List ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_notifications(client, db):
    await _make_admin(db)
    await _seed(db, count=3)
    await _login_admin(client)
    res = await client.get(LIST_URL)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_list_filter_status(client, db):
    await _make_admin(db)
    await _seed(db, count=2, status=NotificationStatusEnum.unhandled)
    await _seed(db, count=1, status=NotificationStatusEnum.completed)
    await _login_admin(client)
    res = await client.get(LIST_URL + "?status=unhandled")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert all(i["status"] == "unhandled" for i in body["items"])


@pytest.mark.asyncio
async def test_list_filter_requires_action(client, db):
    await _make_admin(db)
    await _seed(db, count=2, requires_action=True)
    await _seed(db, count=1, requires_action=False)
    await _login_admin(client)
    res = await client.get(LIST_URL + "?requires_action=true")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert all(i["requires_action"] is True for i in body["items"])


@pytest.mark.asyncio
async def test_list_pagination(client, db):
    await _make_admin(db)
    await _seed(db, count=5)
    await _login_admin(client)
    res = await client.get(LIST_URL + "?page=1&page_size=2")
    body = res.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


# ── Update status ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_status_to_in_progress(client, db):
    await _make_admin(db)
    await _seed(db, count=1)
    notifs = (await db.execute(select(AdminNotification))).scalars().all()
    nid = notifs[0].id
    await _login_admin(client)
    res = await client.patch(f"{LIST_URL}/{nid}/status", json={"status": "in_progress"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "in_progress"


@pytest.mark.asyncio
async def test_update_status_to_completed(client, db):
    await _make_admin(db)
    await _seed(db, count=1, status=NotificationStatusEnum.in_progress)
    notif = (await db.execute(select(AdminNotification))).scalar_one()
    await _login_admin(client)
    res = await client.patch(
        f"{LIST_URL}/{notif.id}/status", json={"status": "completed"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_reject_status_revert(client, db):
    """completed cannot revert to unhandled (single-direction transitions)."""
    await _make_admin(db)
    await _seed(db, count=1, status=NotificationStatusEnum.completed)
    notif = (await db.execute(select(AdminNotification))).scalar_one()
    await _login_admin(client)
    # Try to set to in_progress (which is allowed only from unhandled)
    res = await client.patch(
        f"{LIST_URL}/{notif.id}/status", json={"status": "in_progress"}
    )
    assert res.status_code == 400
    assert res.json().get("code") == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_update_unknown_404(client, db):
    await _make_admin(db)
    await _login_admin(client)
    fake_id = str(uuid.uuid4())
    res = await client.patch(f"{LIST_URL}/{fake_id}/status", json={"status": "completed"})
    assert res.status_code == 404


# ── Bulk complete ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_complete(client, db):
    await _make_admin(db)
    await _seed(db, count=3)
    notifs = (await db.execute(select(AdminNotification))).scalars().all()
    ids = [str(n.id) for n in notifs]
    await _login_admin(client)
    res = await client.patch(f"{LIST_URL}/bulk-complete", json={"ids": ids})
    assert res.status_code == 200
    body = res.json()
    assert body["completed_count"] == 3
    assert len(body["processed_ids"]) == 3
    assert body["skipped_ids"] == []


@pytest.mark.asyncio
async def test_bulk_complete_skips_completed(client, db):
    await _make_admin(db)
    await _seed(db, count=2, status=NotificationStatusEnum.completed)
    await _seed(db, count=1, status=NotificationStatusEnum.unhandled)
    notifs = (await db.execute(select(AdminNotification))).scalars().all()
    ids = [str(n.id) for n in notifs]
    await _login_admin(client)
    res = await client.patch(f"{LIST_URL}/bulk-complete", json={"ids": ids})
    body = res.json()
    assert body["completed_count"] == 1
    assert len(body["skipped_ids"]) == 2


# ── stock_shortage dedup ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stock_shortage_dedup(client, db):
    """Same physical_color with active stock_shortage → UPDATE not new INSERT."""
    color_id = uuid.uuid4()
    await create_or_update_stock_shortage(db, color_id, "缺 50ml")
    await db.commit()
    await create_or_update_stock_shortage(db, color_id, "缺 80ml")
    await db.commit()
    result = await db.execute(
        select(AdminNotification).where(AdminNotification.reference_id == color_id)
    )
    notifs = list(result.scalars().all())
    assert len(notifs) == 1
    assert notifs[0].message == "缺 80ml"


@pytest.mark.asyncio
async def test_stock_shortage_creates_after_completed(client, db):
    """When earlier stock_shortage is completed, a new one is created."""
    color_id = uuid.uuid4()
    n1 = await create_or_update_stock_shortage(db, color_id, "缺 50ml")
    await db.commit()
    n1.status = NotificationStatusEnum.completed
    await db.commit()
    await create_or_update_stock_shortage(db, color_id, "再次缺貨")
    await db.commit()
    result = await db.execute(
        select(AdminNotification)
        .where(AdminNotification.reference_id == color_id)
        .order_by(AdminNotification.created_at)
    )
    notifs = list(result.scalars().all())
    assert len(notifs) == 2


# ── payment_resubmitted ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_payment_resubmitted_completes_old(client, db):
    """When payment_resubmitted is created, old payment_submitted is auto-completed."""
    import asyncio as _asyncio
    order_id = uuid.uuid4()
    await create_notification(
        db,
        type="payment_submitted",
        message="客戶提交付款",
        reference_type="order",
        reference_id=order_id,
        requires_action=True,
    )
    await db.commit()
    # Snapshot original updated_at before resubmit
    pre_result = await db.execute(
        select(AdminNotification).where(AdminNotification.reference_id == order_id)
    )
    original = pre_result.scalar_one()
    original_updated_at = original.updated_at
    await _asyncio.sleep(0.05)  # ensure clock moves

    await create_payment_resubmitted(db, order_id, "客戶重填付款")
    await db.commit()
    db.expire_all()

    result = await db.execute(
        select(AdminNotification).where(AdminNotification.reference_id == order_id)
    )
    notifs = list(result.scalars().all())
    assert len(notifs) == 2
    submitted = next(n for n in notifs if n.type == "payment_submitted")
    resubmitted = next(n for n in notifs if n.type == "payment_resubmitted")
    assert submitted.status == NotificationStatusEnum.completed
    assert "已被新付款表單取代" in submitted.message
    assert resubmitted.status == NotificationStatusEnum.unhandled
    # updated_at should be bumped on the bulk update (regression for onupdate fix)
    assert submitted.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_bulk_complete_includes_unknown_ids_in_skipped(client, db):
    """Non-existent ids should be reported in skipped_ids, not silently dropped."""
    await _make_admin(db)
    await _seed(db, count=1)
    notif = (await db.execute(select(AdminNotification))).scalar_one()
    fake_id = str(uuid.uuid4())
    await _login_admin(client)
    res = await client.patch(
        f"{LIST_URL}/bulk-complete",
        json={"ids": [str(notif.id), fake_id]},
    )
    body = res.json()
    assert body["completed_count"] == 1
    assert fake_id in body["skipped_ids"]


# ── Auth ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_list_rejected(client, db):
    await _make_customer(db)
    await _login_customer(client)
    res = await client.get(LIST_URL)
    assert res.status_code == 403


# ── Cross-module: custom mark-negotiating uses status enum ───────────────────


@pytest.mark.asyncio
async def test_quote_pending_marked_completed_via_status(client, db):
    """Verify custom._mark_quote_pending_notifications_done uses status enum."""
    request_id = uuid.uuid4()
    await create_notification(
        db,
        type="quote_pending",
        message="新申請",
        reference_type="custom_request",
        reference_id=request_id,
        requires_action=True,
    )
    await db.commit()

    from custom.service import _mark_quote_pending_notifications_done
    await _mark_quote_pending_notifications_done(db, request_id)
    await db.commit()

    result = await db.execute(
        select(AdminNotification).where(AdminNotification.reference_id == request_id)
    )
    notif = result.scalar_one()
    assert notif.status == NotificationStatusEnum.completed
    assert notif.requires_action is False
