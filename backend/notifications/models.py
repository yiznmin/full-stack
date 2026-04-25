import uuid
from enum import StrEnum

from sqlalchemy import TIMESTAMP, Boolean, Column, Enum, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class NotificationStatusEnum(StrEnum):
    unhandled = "unhandled"
    in_progress = "in_progress"
    completed = "completed"


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)
    reference_type = Column(String, nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    message = Column(Text, nullable=False)
    requires_action = Column(Boolean, nullable=False, default=False)
    status = Column(
        Enum(NotificationStatusEnum),
        nullable=False,
        default=NotificationStatusEnum.unhandled,
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # Partial unique index for race-safe stock_shortage dedup (admin_notifications.md §73).
        # Combined with INSERT ... ON CONFLICT DO UPDATE in service layer.
        Index(
            "uq_active_stock_shortage_per_ref",
            "reference_type",
            "reference_id",
            unique=True,
            postgresql_where=text(
                "type = 'stock_shortage' AND status IN ('unhandled', 'in_progress')"
            ),
        ),
    )
