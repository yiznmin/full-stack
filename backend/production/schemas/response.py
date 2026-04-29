from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ImageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    uploader_id: UUID
    original_url: str
    filename: str
    width: int
    height: int
    created_at: datetime


class ImageListResponse(BaseModel):
    items: list[ImageResponse]
    total: int
    page: int
    page_size: int


class JobSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    status: str
    approved: bool
    detail: str
    difficulty: str
    mode: str
    canvas_w_cm: float
    canvas_h_cm: float
    batch_id: UUID | None
    created_at: datetime


class JobListResponse(BaseModel):
    items: list[JobSummaryResponse]
    total: int
    page: int
    page_size: int


class JobDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    image_id: UUID | None
    custom_request_id: UUID | None
    batch_id: UUID | None
    status: str
    approved: bool
    detail: str
    difficulty: str
    mode: str
    canvas_w_cm: float
    canvas_h_cm: float
    min_brush_diam_cm: float
    num_colors: int | None
    blur_ksize: int | None
    blur_sigma_color: float | None
    blur_sigma_space: float | None
    prune_iterations: int | None
    pruning_threshold: float | None
    min_ratio_multiplier: float | None
    bg_extra_blur: int | None
    extra_colors: int | None
    weight_ratio: float | None
    sam_points: list | None
    polygons: list | None
    mask_url: str | None
    mask_coverage: float | None
    svg_url: str | None
    filled_template_url: str | None
    snapped_rgb_url: str | None
    palette_json: list | None
    num_colors_used: int | None
    notes: str | None
    created_at: datetime
    approved_at: datetime | None


class CreateJobsResponse(BaseModel):
    batch_id: UUID | None
    job_ids: list[UUID]


class SignedUrlResponse(BaseModel):
    url: str | None


class UploadUrlResponse(BaseModel):
    upload_url: str
    public_url: str
    expires_at: datetime


class CanvasSizeSuggestion(BaseModel):
    w: int
    h: int
    ratio_match: float  # 0~1，1 = 比例完全相符


class SuggestCanvasSizesResponse(BaseModel):
    items: list[CanvasSizeSuggestion]
