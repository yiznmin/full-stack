from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin
from product import service
from product.schemas.request import (
    ImageReorderRequest,
    ProductCreateRequest,
    ProductImageCreateRequest,
    ProductUpdateRequest,
    SeriesCreateRequest,
    SeriesUpdateRequest,
    TagCreateRequest,
    TagUpdateRequest,
    ThemeCreateRequest,
    ThemeUpdateRequest,
    VariantCreateRequest,
    VariantUpdateRequest,
)
from product.schemas.response import (
    ProductDetailResponse,
    ProductImageListResponse,
    ProductImageResponse,
    ProductListResponse,
    PublicProductDetailResponse,
    PublicProductListResponse,
    PublicTagListResponse,
    RelatedProductsResponse,
    SeriesListResponse,
    SeriesResponse,
    TagListResponse,
    TagResponse,
    ThemeListResponse,
    ThemeResponse,
    VariantListResponse,
    VariantResponse,
)

router = APIRouter(tags=["Admin - Products"])


# ── Public store-browse endpoints ─────────────────────────────────────────────


@router.get("/products", response_model=PublicProductListResponse, tags=["Store - Browse"])
async def store_list_products(
    difficulty: (
        Literal["beginner", "elementary", "intermediate", "advanced"] | None
    ) = Query(default=None),
    detail: Literal["rough", "standard", "detailed", "premium"] | None = Query(default=None),
    canvas_size: str | None = Query(default=None, description="WxH e.g. 30x40"),
    tag_id: UUID | None = Query(default=None),
    series_id: UUID | None = Query(default=None),
    sort: Literal["latest", "popular", "price_asc", "price_desc"] = Query(default="latest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.public_list_products(
        db, difficulty, detail, canvas_size, tag_id, series_id, sort, page, page_size,
    )


@router.get("/products/search", response_model=PublicProductListResponse, tags=["Store - Browse"])
async def store_search_products(
    q: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.public_search_products(db, q, page, page_size)


@router.get(
    "/products/{product_id}",
    response_model=PublicProductDetailResponse,
    tags=["Store - Browse"],
)
async def store_get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await service.public_get_product(db, product_id)


@router.get(
    "/products/{product_id}/related",
    response_model=RelatedProductsResponse,
    tags=["Store - Browse"],
)
async def store_related_products(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await service.public_related_products(db, product_id)


@router.get("/tags", response_model=PublicTagListResponse, tags=["Store - Browse"])
async def store_list_tags(
    db: AsyncSession = Depends(get_db),
):
    return await service.public_list_tags(db)


# ── Admin endpoints (unchanged) ────────────────────────────────────────────────


# ── Themes ───────────────────────────────────────────────────────────────────

@router.get("/admin/themes", response_model=ThemeListResponse)
async def list_themes(
    _: None = Depends(require_admin),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_themes(db, search, page, page_size)


@router.get("/admin/themes/{theme_id}", response_model=ThemeResponse)
async def get_theme(
    theme_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_theme(db, theme_id)


@router.post("/admin/themes", response_model=ThemeResponse, status_code=201)
async def create_theme(
    body: ThemeCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_theme(db, body.model_dump())


@router.put("/admin/themes/{theme_id}", response_model=ThemeResponse)
async def update_theme(
    theme_id: UUID,
    body: ThemeUpdateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_theme(db, theme_id, body.model_dump())


@router.delete("/admin/themes/{theme_id}", response_model=None, status_code=204)
async def delete_theme(
    theme_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_theme(db, theme_id)


# ── Series ────────────────────────────────────────────────────────────────────

@router.get("/admin/series", response_model=SeriesListResponse)
async def list_series(
    _: None = Depends(require_admin),
    theme_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_series(db, theme_id=theme_id)
    return {"items": items}


@router.post("/admin/series", response_model=SeriesResponse, status_code=201)
async def create_series(
    body: SeriesCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_series(db, body.name, body.description, body.theme_id)


@router.put("/admin/series/{series_id}", response_model=SeriesResponse)
async def update_series(
    series_id: UUID,
    body: SeriesUpdateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_series(
        db, series_id, body.name, body.description, body.theme_id
    )


@router.delete("/admin/series/{series_id}", response_model=None, status_code=204)
async def delete_series(
    series_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_series(db, series_id)


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/admin/tags", response_model=TagListResponse)
async def list_tags(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_tags(db)
    return {"items": items}


@router.post("/admin/tags", response_model=TagResponse, status_code=201)
async def create_tag(
    body: TagCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_tag(db, body.name)


@router.put("/admin/tags/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID,
    body: TagUpdateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_tag(db, tag_id, body.name)


@router.delete("/admin/tags/{tag_id}", response_model=None, status_code=204)
async def delete_tag(
    tag_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_tag(db, tag_id)


# ── Products ──────────────────────────────────────────────────────────────────

@router.get("/admin/products", response_model=ProductListResponse)
async def list_products(
    search: str | None = Query(default=None),
    status: Literal["draft", "on_sale", "off_sale"] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_products(db, search, status, page, page_size)


@router.post("/admin/products", response_model=ProductDetailResponse, status_code=201)
async def create_product(
    body: ProductCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_product(db, body.model_dump())


@router.get("/admin/products/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_product(db, product_id)


@router.put("/admin/products/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: UUID,
    body: ProductUpdateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_product(db, product_id, body.model_dump())


@router.delete("/admin/products/{product_id}", response_model=None, status_code=204)
async def delete_product(
    product_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_product(db, product_id)


# ── Product images ────────────────────────────────────────────────────────────

@router.get(
    "/admin/products/{product_id}/images",
    response_model=ProductImageListResponse,
)
async def list_images(
    product_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    images = await service.list_product_images(db, product_id)
    return {"items": images}


@router.post(
    "/admin/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=201,
)
async def add_image(
    product_id: UUID,
    body: ProductImageCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.add_product_image(db, product_id, body.image_url, body.sort_order)


@router.delete(
    "/admin/products/{product_id}/images/{image_id}",
    response_model=None,
    status_code=204,
)
async def delete_image(
    product_id: UUID,
    image_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_product_image(db, product_id, image_id)


@router.patch(
    "/admin/products/{product_id}/images/reorder",
    response_model=ProductImageListResponse,
)
async def reorder_images(
    product_id: UUID,
    body: ImageReorderRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    images = await service.reorder_product_images(db, product_id, body.order)
    return {"items": images}


# ── Product variants ──────────────────────────────────────────────────────────

@router.get(
    "/admin/products/{product_id}/variants",
    response_model=VariantListResponse,
)
async def list_variants(
    product_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    variants = await service.list_product_variants(db, product_id)
    return {"items": variants}


@router.post("/admin/products/{product_id}/variants", response_model=VariantResponse)
async def create_variant(
    product_id: UUID,
    body: VariantCreateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_or_update_variant(
        db, product_id, body.production_job_id, body.price
    )


@router.patch(
    "/admin/products/{product_id}/variants/{variant_id}",
    response_model=VariantResponse,
)
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    body: VariantUpdateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_variant(
        db, product_id, variant_id, body.price, body.is_active
    )


@router.delete(
    "/admin/products/{product_id}/variants/{variant_id}",
    response_model=None,
    status_code=204,
)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_variant(db, product_id, variant_id)
