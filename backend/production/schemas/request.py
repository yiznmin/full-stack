from typing import Annotated, Literal
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
    """A 格子合併（區域層級）：admin 點 template.svg 上一格 → 選目標色號。

    - polygon_id：被合併那一格的 SVG region 識別碼（pbn_gen.py 寫入 id="rN"）
    - target_template_id：目標色號（從 palette 任選，後端從 palette_json 找對應 RGB）
    """
    polygon_id: str
    target_template_id: int


class EliminateBorderRequest(BaseModel):
    """B 消除邊界（區域層級）：admin 點兩格 + 對話框選保留哪邊。

    - absorbed_polygon_id：被吸收的那一格（會被改成存活側的顏色）
    - surviving_polygon_id：存活的那一格（顏色不變、邊界吃掉吸收側）
    """
    absorbed_polygon_id: str
    surviving_polygon_id: str

    @model_validator(mode="after")
    def validate_different(self) -> "EliminateBorderRequest":
        if self.absorbed_polygon_id == self.surviving_polygon_id:
            raise ValueError(
                "absorbed_polygon_id 與 surviving_polygon_id 不可相同"
            )
        return self


# ── Batch 後處理 ─────────────────────────────────────────────────────────────


class BatchMergeOp(BaseModel):
    op: Literal["merge_color"]
    polygon_id: str
    target_template_id: int


class BatchEliminateOp(BaseModel):
    op: Literal["eliminate_border"]
    absorbed_polygon_id: str
    surviving_polygon_id: str

    @model_validator(mode="after")
    def validate_different(self) -> "BatchEliminateOp":
        if self.absorbed_polygon_id == self.surviving_polygon_id:
            raise ValueError(
                "absorbed_polygon_id 與 surviving_polygon_id 不可相同"
            )
        return self


_BatchOp = Annotated[
    BatchMergeOp | BatchEliminateOp,
    Field(discriminator="op"),
]


class BatchPostProcessRequest(BaseModel):
    """區域層級批次後處理：admin 在 dialog 內累積多個動作 → 一次送出。

    後端在同一個 Celery 任務內按順序套用所有 ops（同 snapped_rgb 緩衝、所有 mask
    都用**原始** SVG 的 polygon 範圍），最後**只跑一次** output_to_svg + filled
    + Firebase 上傳，比 N 個單獨 endpoint 高效 N 倍。
    """
    operations: list[_BatchOp]

    @model_validator(mode="after")
    def validate_size(self) -> "BatchPostProcessRequest":
        if not self.operations:
            raise ValueError("operations 不能為空")
        if len(self.operations) > 50:
            raise ValueError("一次最多 50 個操作")
        return self


class SamPointInput(BaseModel):
    x: float
    y: float
    label: int  # 1 = foreground, 0 = background


class SamMaskRequest(BaseModel):
    """admin_production.md §10：遮罩編輯時機限制 — 僅 status=pending 可改。"""

    sam_points: list[SamPointInput] | None = None
    polygons: list[list[list[float]]] | None = None  # [[[x,y], ...], ...]
    mode: Literal["sam_refine", "sam_weighted"]

    @model_validator(mode="after")
    def validate_payload(self) -> "SamMaskRequest":
        if not self.sam_points and not self.polygons:
            raise ValueError("sam_points 與 polygons 至少需提供一個")
        return self
