from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from product.models import ProductStatusEnum


class ThemeResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    cover_image_url: str | None
    sort_order: int
    series_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThemeListResponse(BaseModel):
    items: list[ThemeResponse]
    total: int
    page: int
    page_size: int


class SeriesResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    theme_id: UUID | None
    theme_name: str | None
    is_featured: bool
    sample_cover_image_url: str | None = None
    product_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SeriesListResponse(BaseModel):
    items: list[SeriesResponse]


class TagResponse(BaseModel):
    id: UUID
    name: str
    product_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TagListResponse(BaseModel):
    items: list[TagResponse]


class TagBriefResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class ProductImageResponse(BaseModel):
    id: UUID
    image_url: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductImageListResponse(BaseModel):
    items: list[ProductImageResponse]


class VariantJobSpecResponse(BaseModel):
    detail: str
    difficulty: str
    canvas_w_cm: float
    canvas_h_cm: float
    num_colors_used: int | None
    # 顯示用（15-min signed URL，過期即失效；不可寫入永久欄位）
    filled_template_url: str | None
    # 寫入永久欄位用（Firebase download URL，無 TTL）
    cover_url: str | None
    svg_url: str | None


class VariantResponse(BaseModel):
    id: UUID
    product_id: UUID
    production_job_id: UUID
    price: Decimal
    price_formula_base: Decimal
    is_active: bool
    created_at: datetime
    job_spec: VariantJobSpecResponse | None

    model_config = {"from_attributes": True}


class VariantListResponse(BaseModel):
    items: list[VariantResponse]


class ProductBriefResponse(BaseModel):
    id: UUID
    title: str
    status: ProductStatusEnum
    cover_image_url: str
    series_id: UUID | None
    series_name: str | None
    variant_count: int
    is_featured: bool
    tags: list[TagBriefResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductBriefResponse]
    total: int
    page: int
    page_size: int


class ProductDetailResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    cover_image_url: str
    series_id: UUID | None
    series_order: int | None
    status: ProductStatusEnum
    is_featured: bool
    tags: list[TagBriefResponse]
    images: list[ProductImageResponse]
    variants: list[VariantResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AvailableJobResponse(BaseModel):
    id: UUID
    # 同一張原圖的 jobs 共用 image_id，前端可據此分組（一張畫的不同規格放一起）
    image_id: UUID | None = None
    detail: str
    difficulty: str
    canvas_w_cm: float
    canvas_h_cm: float
    num_colors_used: int
    price_formula_base: Decimal
    # 短期預覽 URL（15-min signed）— 只用於 picker 內顯示縮圖，不可寫永久欄位
    preview_url: str | None = None
    # 永久公開 URL（Firebase download URL）— 給「從製作任務選封面」寫入 cover_image_url
    cover_url: str | None = None

    model_config = {"from_attributes": True}


class AvailableJobListResponse(BaseModel):
    items: list[AvailableJobResponse]


# ── Public (store-browse) responses ────────────────────────────────────────────


class PublicTagBrief(BaseModel):
    id: UUID
    name: str


class PublicTagListResponse(BaseModel):
    items: list[PublicTagBrief]


class PublicVariantResponse(BaseModel):
    id: UUID
    canvas_w_cm: float
    canvas_h_cm: float
    difficulty: str
    detail: str
    color_count: int | None
    price: float
    is_active: bool
    is_preorder: bool
    filled_template_url: str | None


class PublicProductBrief(BaseModel):
    id: UUID
    title: str
    cover_image_url: str
    difficulty_range: list[str]
    price_min: float
    price_max: float
    is_preorder: bool
    is_featured: bool


class PublicProductListResponse(BaseModel):
    items: list[PublicProductBrief]
    total: int
    page: int
    page_size: int


class PublicSeriesBrief(BaseModel):
    id: UUID
    name: str


class PublicSeriesProductBrief(BaseModel):
    id: UUID
    title: str
    cover_image_url: str
    price_min: float
    is_preorder: bool


class PublicSeriesWithProducts(BaseModel):
    id: UUID
    name: str
    products: list[PublicSeriesProductBrief]


class PublicProductDetailResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    cover_image_url: str
    is_featured: bool
    images: list[ProductImageResponse]
    series: PublicSeriesWithProducts | None
    tags: list[PublicTagBrief]
    variants: list[PublicVariantResponse]


class RelatedProductsResponse(BaseModel):
    series: PublicSeriesBrief | None
    items: list[PublicSeriesProductBrief]


# ── Public themes / series ────────────────────────────────────────────────────
# 公開主題與系列瀏覽（store_design_brief.md 第 4a/4b/4c 頁）
# 跟 admin 端的 ThemeResponse / SeriesResponse 區分：
#   - 公開只回 store 需要的欄位（不含 updated_at）
#   - 加 product_count（admin 端只有 series_count）

class PublicThemeBrief(BaseModel):
    id: UUID
    name: str
    description: str | None
    cover_image_url: str | None
    sort_order: int
    series_count: int
    product_count: int

    model_config = {"from_attributes": True}


class PublicThemeListResponse(BaseModel):
    items: list[PublicThemeBrief]


class PublicSeriesInTheme(BaseModel):
    """主題詳情頁巢狀的系列摘要（含 product_count）。"""
    id: UUID
    name: str
    description: str | None
    product_count: int

    model_config = {"from_attributes": True}


class PublicThemeDetailResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    cover_image_url: str | None
    sort_order: int
    series: list[PublicSeriesInTheme]


class PublicSeriesBriefWithCount(BaseModel):
    id: UUID
    name: str
    description: str | None
    theme_id: UUID | None
    theme_name: str | None
    is_featured: bool
    product_count: int

    model_config = {"from_attributes": True}


class PublicSeriesListResponse(BaseModel):
    items: list[PublicSeriesBriefWithCount]


class PublicSeriesDetailResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    theme_id: UUID | None
    theme_name: str | None
    is_featured: bool
    sample_cover_image_url: str | None = None
    products: list[PublicProductBrief]   # 依 series_order ASC 排
