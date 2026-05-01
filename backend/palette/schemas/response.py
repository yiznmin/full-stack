from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PhysicalColorBriefResponse(BaseModel):
    id: UUID
    code: str
    name: str
    rgb: list[int]
    stock_ml: float


class PaletteMappingResponse(BaseModel):
    template_id: int
    algorithm_rgb: list[int]
    physical_color: PhysicalColorBriefResponse | None
    required_ml: float | None
    mapped_by: str


class PaletteMappingListResponse(BaseModel):
    mappings: list[PaletteMappingResponse]


class ShortageColorItem(BaseModel):
    template_id: int
    physical_color_id: UUID
    code: str
    name: str


class CompleteResponse(BaseModel):
    all_stocked: bool
    shortage_colors: list[ShortageColorItem]


class CopyCandidateItem(BaseModel):
    """admin_color.md §2.2「從其他 job 複製對應」候選 job。"""
    job_id: UUID
    detail: str
    difficulty: str
    canvas_w_cm: float
    canvas_h_cm: float
    num_colors_used: int | None
    filled_template_url: str | None  # 縮圖預覽（已轉 signed URL）
    relation: str  # "same_batch" 或 "same_image"
    created_at: datetime


class CopyCandidatesResponse(BaseModel):
    items: list[CopyCandidateItem]
