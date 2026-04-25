from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin
from notifications import service
from notifications.schemas.request import (
    BulkCompleteRequest,
    UpdateNotificationStatusRequest,
)
from notifications.schemas.response import (
    BulkCompleteResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(tags=["Notifications"])


@router.get("/admin/notifications", response_model=NotificationListResponse)
async def list_notifications(
    _=Depends(require_admin),
    status: str | None = Query(default=None),
    requires_action: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_notifications(
        db, status, requires_action, page, page_size
    )


@router.patch(
    "/admin/notifications/{notification_id}/status",
    response_model=NotificationResponse,
)
async def update_notification_status(
    notification_id: UUID,
    body: UpdateNotificationStatusRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    notif = await service.update_status(db, notification_id, body.status)
    return service._serialize(notif)


@router.patch(
    "/admin/notifications/bulk-complete", response_model=BulkCompleteResponse
)
async def bulk_complete_notifications(
    body: BulkCompleteRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.bulk_complete(db, body.ids)
