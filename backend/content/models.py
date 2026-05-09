import uuid

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base
from production.models import DifficultyEnum


class Page(Base):
    __tablename__ = "static_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CaseCategory(Base):
    __tablename__ = "case_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class CustomCase(Base):
    __tablename__ = "custom_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 主圖 URL（= case_images sort_order=0 的快取，service 層自動同步）
    # 保留此欄位作為向後相容；前端 list 顯示縮圖直接讀此欄位較快。
    image_url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("case_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    canvas_w_cm = Column(Integer, nullable=True)
    canvas_h_cm = Column(Integer, nullable=True)
    difficulty = Column(Enum(DifficultyEnum), nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class CaseImage(Base):
    """custom_case 的多圖：sort_order 決定順序，0 = 封面（同步到 custom_cases.image_url）。"""
    __tablename__ = "case_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("custom_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
