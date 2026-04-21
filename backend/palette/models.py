import uuid
from enum import StrEnum

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class MappedByEnum(StrEnum):
    system = "system"
    manual = "manual"


class PaletteColorMapping(Base):
    __tablename__ = "palette_color_mappings"
    __table_args__ = (UniqueConstraint("production_job_id", "template_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    production_job_id = Column(
        UUID(as_uuid=True), ForeignKey("production_jobs.id"), nullable=False
    )
    template_id = Column(Integer, nullable=False)
    algorithm_rgb = Column(ARRAY(Integer), nullable=False)
    physical_color_id = Column(
        UUID(as_uuid=True), ForeignKey("physical_colors.id"), nullable=False
    )
    required_ml = Column(Numeric(8, 4), nullable=True)
    mapped_by = Column(
        Enum(MappedByEnum), nullable=False, default=MappedByEnum.system
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
