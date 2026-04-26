import uuid

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


class PhysicalColor(Base):
    __tablename__ = "physical_colors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    color_family = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    rgb = Column(JSONB, nullable=False)
    stock_ml = Column(Numeric(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PhysicalColorRgbHistory(Base):
    """每次實體色 RGB 變動的 audit snapshot（建色 / 校正 / 還原皆寫入）。"""
    __tablename__ = "physical_color_rgb_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physical_color_id = Column(
        UUID(as_uuid=True),
        ForeignKey("physical_colors.id", ondelete="CASCADE"),
        nullable=False,
    )
    rgb = Column(JSONB, nullable=False)
    changed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
