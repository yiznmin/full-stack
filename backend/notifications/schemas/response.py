from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    message: str
    requires_action: bool
    status: str
    reference_type: str | None
    reference_id: UUID | None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int


class BulkCompleteResponse(BaseModel):
    completed_count: int
    processed_ids: list[UUID]
    skipped_ids: list[UUID]
