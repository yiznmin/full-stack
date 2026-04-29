from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class JobParams(BaseModel):
    detail: Literal["rough", "standard", "detailed", "premium"]
    difficulty: Literal["beginner", "elementary", "intermediate", "advanced"]
    mode: Literal["standard", "sam_refine", "sam_weighted"] = "standard"
    canvas_w_cm: float
    canvas_h_cm: float
    min_brush_diam_cm: float = 1.0
    num_colors: int | None = None
    blur_ksize: int | None = None
    blur_sigma_color: float | None = None
    blur_sigma_space: float | None = None
    prune_iterations: int | None = None
    pruning_threshold: float | None = None
    min_ratio_multiplier: float | None = None
    bg_extra_blur: int | None = None
    extra_colors: int | None = None
    weight_ratio: float | None = None
    sam_points: list[dict] | None = None
    polygons: list[list[list[float]]] | None = None
    mask_url: str | None = None

    @model_validator(mode="after")
    def validate_mode_params(self) -> "JobParams":
        if self.mode == "sam_refine":
            if self.extra_colors is None or self.extra_colors <= 0:
                raise ValueError("sam_refine 模式必須提供 extra_colors（> 0）")
        if self.mode == "sam_weighted":
            if self.weight_ratio is None:
                raise ValueError("sam_weighted 模式必須提供 weight_ratio")
            if not (0.5 <= self.weight_ratio <= 0.8):
                raise ValueError("weight_ratio 必須在 0.5 ~ 0.8 之間")
        return self

    @field_validator("canvas_w_cm", "canvas_h_cm", "min_brush_diam_cm")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("必須大於 0")
        return v


class CreateJobsRequest(BaseModel):
    image_id: UUID | None = None
    custom_request_id: UUID | None = None
    jobs: list[JobParams]

    @model_validator(mode="after")
    def validate_source(self) -> "CreateJobsRequest":
        if self.image_id is None and self.custom_request_id is None:
            raise ValueError("image_id 與 custom_request_id 不能同時為 null")
        if self.image_id is not None and self.custom_request_id is not None:
            raise ValueError("image_id 與 custom_request_id 不能同時提供")
        if not self.jobs:
            raise ValueError("jobs 不能為空")
        if len(self.jobs) > 10:
            raise ValueError("一次最多送出 10 個 job")
        return self


class UploadProductionImageRequest(BaseModel):
    filename: str
    content_type: Literal["image/jpeg", "image/png"]
    size: int = Field(gt=0, le=20_000_000, description="檔案位元組大小，上限 20MB")


class CreateImageRequest(BaseModel):
    original_url: str
    filename: str
    width: int
    height: int

    @field_validator("width", "height")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("必須大於 0")
        return v


class SuggestCanvasSizesRequest(BaseModel):
    width: int = Field(gt=0, description="圖片寬度（像素）")
    height: int = Field(gt=0, description="圖片高度（像素）")
    n: int = Field(default=3, ge=1, le=10, description="要回幾組推薦尺寸")


class ApproveRequest(BaseModel):
    notes: str | None = None


class MergeColorRequest(BaseModel):
    source_template_id: int
    target_template_id: int

    @model_validator(mode="after")
    def validate_different(self) -> "MergeColorRequest":
        if self.source_template_id == self.target_template_id:
            raise ValueError("source_template_id 與 target_template_id 不可相同")
        return self


class EliminateBorderRequest(BaseModel):
    absorbed_template_id: int
    surviving_template_id: int

    @model_validator(mode="after")
    def validate_different(self) -> "EliminateBorderRequest":
        if self.absorbed_template_id == self.surviving_template_id:
            raise ValueError("absorbed_template_id 與 surviving_template_id 不可相同")
        return self


class SmoothContourRequest(BaseModel):
    border_between: list[int]
    smoothness: int

    @model_validator(mode="after")
    def validate_params(self) -> "SmoothContourRequest":
        if len(self.border_between) != 2:
            raise ValueError("border_between 必須包含恰好 2 個區塊編號")
        if self.border_between[0] == self.border_between[1]:
            raise ValueError("border_between 的兩個區塊編號不可相同")
        if not (1 <= self.smoothness <= 10):
            raise ValueError("smoothness 必須在 1 ~ 10 之間")
        return self
