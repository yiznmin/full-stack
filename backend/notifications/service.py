import uuid as uuidlib
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestError, NotFoundError
from notifications.models import AdminNotification, NotificationStatusEnum


async def create_notification(
    db: AsyncSession,
    type: str,
    message: str,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    requires_action: bool = False,
    status: NotificationStatusEnum = NotificationStatusEnum.unhandled,
) -> AdminNotification:
    notification = AdminNotification(
        type=type,
        reference_type=reference_type,
        reference_id=reference_id,
        message=message,
        requires_action=requires_action,
        status=status,
    )
    db.add(notification)
    return notification


async def create_or_update_stock_shortage(
    db: AsyncSession,
    physical_color_id: UUID,
    message: str,
) -> AdminNotification:
    """Dedup rule (§73): at most one ACTIVE stock_shortage per physical_color.
    Race-safe via partial unique index `uq_active_stock_shortage_per_ref` +
    INSERT ... ON CONFLICT DO UPDATE.
    """
    if physical_color_id is None:
        raise ValueError("physical_color_id is required for stock_shortage notification")

    new_id = uuidlib.uuid4()
    stmt = (
        pg_insert(AdminNotification)
        .values(
            id=new_id,
            type="stock_shortage",
            message=message,
            reference_type="physical_color",
            reference_id=physical_color_id,
            requires_action=True,
            status=NotificationStatusEnum.unhandled,
        )
        .on_conflict_do_update(
            index_elements=[
                AdminNotification.reference_type,
                AdminNotification.reference_id,
            ],
            index_where=text(
                "type = 'stock_shortage' "
                "AND status IN ('unhandled', 'in_progress')"
            ),
            set_={
                "message": message,
                "requires_action": True,
                "updated_at": func.now(),
            },
        )
        .returning(AdminNotification)
    )
    result = await db.execute(
        stmt.execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def create_payment_resubmitted(
    db: AsyncSession,
    order_id: UUID,
    message: str,
) -> AdminNotification:
    """Create payment_resubmitted notification AND mark prior payment_submitted
    notifications for the same order as completed (per admin_notifications.md §73).
    """
    await db.execute(
        update(AdminNotification)
        .where(
            AdminNotification.type == "payment_submitted",
            AdminNotification.reference_type == "order",
            AdminNotification.reference_id == order_id,
            AdminNotification.status != NotificationStatusEnum.completed,
        )
        .values(
            status=NotificationStatusEnum.completed,
            message=AdminNotification.message + "（已被新付款表單取代）",
            updated_at=func.now(),
        )
    )
    return await create_notification(
        db,
        type="payment_resubmitted",
        message=message,
        reference_type="order",
        reference_id=order_id,
        requires_action=True,
    )


# ── Admin endpoints ────────────────────────────────────────────────────────────


async def list_notifications(
    db: AsyncSession,
    status: str | None,
    requires_action: bool | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(AdminNotification)
    if status:
        query = query.where(AdminNotification.status == status)
    if requires_action is not None:
        query = query.where(AdminNotification.requires_action == requires_action)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    rows = (await db.execute(
        query.order_by(AdminNotification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return {
        "items": [_serialize(n) for n in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


_VALID_TRANSITIONS = {
    NotificationStatusEnum.in_progress: {NotificationStatusEnum.unhandled},
    NotificationStatusEnum.completed: {
        NotificationStatusEnum.unhandled,
        NotificationStatusEnum.in_progress,
    },
}


async def update_status(
    db: AsyncSession, notification_id: UUID, new_status: str
) -> AdminNotification:
    result = await db.execute(
        select(AdminNotification)
        .where(AdminNotification.id == notification_id)
        .with_for_update()
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        raise NotFoundError("通知不存在")

    target = NotificationStatusEnum(new_status)
    allowed_from = _VALID_TRANSITIONS.get(target)
    if allowed_from is None or notif.status not in allowed_from:
        raise BadRequestError(
            f"無法從 {notif.status} 轉換至 {new_status}",
            code="INVALID_STATUS_TRANSITION",
        )

    notif.status = target
    await db.commit()
    await db.refresh(notif)
    return notif


async def bulk_complete(db: AsyncSession, ids: list[UUID]) -> dict:
    requested = list(set(ids))
    result = await db.execute(
        select(AdminNotification)
        .where(AdminNotification.id.in_(requested))
        .with_for_update()
    )
    rows = list(result.scalars().all())
    found_ids = {n.id for n in rows}

    processed: list[UUID] = []
    skipped: list[UUID] = []
    for notif in rows:
        if notif.status == NotificationStatusEnum.completed:
            skipped.append(notif.id)
            continue
        notif.status = NotificationStatusEnum.completed
        processed.append(notif.id)

    # IDs not found at all also count as skipped
    for rid in requested:
        if rid not in found_ids:
            skipped.append(rid)

    await db.commit()
    return {
        "completed_count": len(processed),
        "processed_ids": processed,
        "skipped_ids": skipped,
    }


def _serialize(n: AdminNotification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "requires_action": n.requires_action,
        "status": n.status.value if hasattr(n.status, "value") else str(n.status),
        "reference_type": n.reference_type,
        "reference_id": n.reference_id,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
    }
