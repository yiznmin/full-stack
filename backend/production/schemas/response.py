from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


def _resolve_filled_url(raw: Any) -> Any:
    """admin 顯示用：gs:// → 15-min signed https URL；http(s):// 直接回；None / 異常 → None。

    瀏覽器 <img :src="..."> 無法載 gs://，需即時簽名。簽名是本地 crypto，無 Firebase API 呼叫成本。
    """
    if not raw or not isinstance(raw, str):
        return raw
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    try:
        from production.service import _make_signed_url  # noqa: PLC0415

        return _make_signed_url(raw)
    except Exception:  # noqa: BLE001
        return None


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
    filled_template_url: str | None
    # 列表頁用：filled_template_url 不存在時 fallback 顯原圖縮圖
    # （由 service.list_jobs 動態 attach 到 ORM 物件）
    image_preview_url: str | None = None
    num_colors_used: int | None
    notes: str | None
    created_at: datetime
    approved_at: datetime | None

    @field_validator("filled_template_url", mode="before")
    @classmethod
    def _convert_filled(cls, v: Any) -> Any:
        return _resolve_filled_url(v)

    @field_validator("image_preview_url", mode="before")
    @classmethod
    def _convert_image_preview(cls, v: Any) -> Any:
        return _resolve_filled_url(v)


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
    template_final_url: str | None = None
    palette_final_url: str | None = None
    filled_template_final_url: str | None = None
    finalized_at: datetime | None = None
    created_at: datetime
    approved_at: datetime | None

    @field_validator("filled_template_url", mode="before")
    @classmethod
    def _convert_filled(cls, v: Any) -> Any:
        return _resolve_filled_url(v)

    @field_validator("mask_url", mode="before")
    @classmethod
    def _convert_mask(cls, v: Any) -> Any:
        return _resolve_filled_url(v)

    @field_validator("template_final_url", mode="before")
    @classmethod
    def _convert_template_final(cls, v: Any) -> Any:
        # gs:// → 15-min signed https URL（admin 預覽用）
        return _resolve_filled_url(v)

    @field_validator("filled_template_final_url", mode="before")
    @classmethod
    def _convert_filled_final(cls, v: Any) -> Any:
        return _resolve_filled_url(v)


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


class SamMaskResponse(BaseModel):
    # 注意：DB 內 mask_url 存的是 gs://...，回 client 前轉 https signed URL
    # （HTML <img> 不認 gs://）
    mask_url: str | None
    # 遮罩面積佔圖片面積比例 0~1；純 sam_points 等 Celery 推論時為 null
    mask_coverage: float | None

    @field_validator("mask_url", mode="before")
    @classmethod
    def _convert_mask(cls, v: Any) -> Any:
        return _resolve_filled_url(v)


class BatchStartSkippedItem(BaseModel):
    job_id: UUID
    reason: str  # "missing mask_url" / "already processing" / "already completed" / etc.


class BatchStartResponse(BaseModel):
    enqueued: int
    skipped: list[BatchStartSkippedItem]


class BatchDeleteJobResult(BaseModel):
    """批次刪除單筆結果（成功 or 失敗）."""
    job_id: UUID
    ok: bool
    error: str | None = None  # 失敗時填原因（中文，給 admin 看）


class BatchDeleteJobsResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: list[BatchDeleteJobResult]
