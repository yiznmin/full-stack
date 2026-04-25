import uuid
from enum import StrEnum

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base
from production.models import DetailEnum, DifficultyEnum


class CustomRequestTypeEnum(StrEnum):
    custom_photo = "custom_photo"
    custom_spec = "custom_spec"


class CustomRequestStatusEnum(StrEnum):
    quote_pending = "quote_pending"
    negotiating = "negotiating"
    quote_sent = "quote_sent"
    draft_revision = "draft_revision"
    quote_confirmed = "quote_confirmed"
    quote_rejected = "quote_rejected"
    quote_expired = "quote_expired"


class MessageSenderTypeEnum(StrEnum):
    admin = "admin"
    customer = "customer"


class CustomRequest(Base):
    __tablename__ = "custom_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    request_type = Column(Enum(CustomRequestTypeEnum), nullable=False)
    status = Column(
        Enum(CustomRequestStatusEnum),
        nullable=False,
        default=CustomRequestStatusEnum.quote_pending,
    )
    photo_url = Column(String, nullable=True)
    ref_product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    canvas_w_cm = Column(Integer, nullable=True)
    canvas_h_cm = Column(Integer, nullable=True)
    difficulty = Column(Enum(DifficultyEnum), nullable=True)
    detail = Column(Enum(DetailEnum), nullable=True)
    customer_notes = Column(Text, nullable=True)
    quoted_price = Column(Numeric(10, 2), nullable=True)
    quote_token = Column(String, nullable=True, unique=True)
    quote_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_extended = Column(Boolean, nullable=False, default=False)
    revision_count = Column(Integer, nullable=False, default=0)
    parent_request_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_requests.id"), nullable=True
    )
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    quoted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    rejected_at = Column(TIMESTAMP(timezone=True), nullable=True)


class CustomRequestMessage(Base):
    __tablename__ = "custom_request_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_requests.id"), nullable=False
    )
    sender_type = Column(Enum(MessageSenderTypeEnum), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class CustomPhotoPrice(Base):
    __tablename__ = "custom_photo_prices"
    __table_args__ = (UniqueConstraint("canvas_w", "canvas_h", "difficulty"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canvas_w = Column(Integer, nullable=False)
    canvas_h = Column(Integer, nullable=False)
    difficulty = Column(Enum(DifficultyEnum), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)


class CustomPhotoSurcharge(Base):
    __tablename__ = "custom_photo_surcharges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String, nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class CanvasSize(Base):
    __tablename__ = "canvas_sizes"
    __table_args__ = (UniqueConstraint("canvas_w_cm", "canvas_h_cm"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canvas_w_cm = Column(Integer, nullable=False)
    canvas_h_cm = Column(Integer, nullable=False)
    display_name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
