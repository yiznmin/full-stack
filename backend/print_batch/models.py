import uuid
from enum import StrEnum

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class PrintBatchStatusEnum(StrEnum):
    draft = "draft"
    finalized = "finalized"


class PrintBatchItemSourceEnum(StrEnum):
    order_item = "order_item"
    standalone = "standalone"


class PrintBatch(Base):
    __tablename__ = "print_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(
        Enum(PrintBatchStatusEnum),
        nullable=False,
        default=PrintBatchStatusEnum.draft,
    )
    total_inch_count = Column(Numeric(10, 2), nullable=False)
    billable_inch_count = Column(Numeric(10, 2), nullable=False)
    print_cost = Column(Numeric(10, 2), nullable=False)
    cut_cost = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    pdf_url = Column(String, nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    finalized_at = Column(TIMESTAMP(timezone=True), nullable=True)


class PrintBatchItem(Base):
    __tablename__ = "print_batch_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    print_batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("print_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(Enum(PrintBatchItemSourceEnum), nullable=False)
    source_order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    production_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    inch_per_unit = Column(Numeric(10, 4), nullable=False)
    canvas_w_cm = Column(Numeric(6, 1), nullable=False)
    canvas_h_cm = Column(Numeric(6, 1), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_print_batch_item_qty_positive"),
    )
