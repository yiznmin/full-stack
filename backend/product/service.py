import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestError, ConflictError, NotFoundError
from product.models import (
    Product,
    ProductImage,
    ProductSeries,
    ProductStatusEnum,
    ProductTag,
    ProductVariant,
    Tag,
)
from production.models import ProductionJob

# ── Pricing formula ──────────────────────────────────────────────────────────

_DETAIL_MULTIPLIER = {
    "rough": Decimal("1.60"),
    "standard": Decimal("1.75"),
    "detailed": Decimal("1.80"),
    "premium": Decimal("1.85"),
}


def calc_price_formula_base(
    canvas_w_cm: float, canvas_h_cm: float, detail: str, num_colors_used: int
) -> Decimal:
    print_area = (canvas_w_cm + 10) * (canvas_h_cm + 10)
    print_cost = math.ceil(print_area / 900) * 45
    frame_cost = canvas_w_cm + canvas_h_cm
    fixed_cost = 25
    base_cost = fixed_cost + print_cost + frame_cost
    paint_cost = num_colors_used
    multiplier = _DETAIL_MULTIPLIER.get(detail, Decimal("1.75"))
    raw = (Decimal(str(base_cost)) + Decimal(str(paint_cost))) * multiplier
    return Decimal(str(round(raw)))


# ── Series ───────────────────────────────────────────────────────────────────

async def list_series(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ProductSeries))
    all_series = result.scalars().all()

    count_result = await db.execute(
        select(Product.series_id, func.count(Product.id).label("cnt"))
        .where(Product.series_id.isnot(None))
        .group_by(Product.series_id)
    )
    count_map = {row.series_id: row.cnt for row in count_result}

    return [
        {**s.__dict__, "product_count": count_map.get(s.id, 0)}
        for s in all_series
    ]


async def create_series(db: AsyncSession, name: str, description: str | None) -> dict:
    existing = await db.execute(select(ProductSeries).where(ProductSeries.name == name))
    if existing.scalar_one_or_none():
        raise ConflictError("系列名稱已存在")
    series = ProductSeries(name=name, description=description)
    db.add(series)
    await db.commit()
    await db.refresh(series)
    return {**series.__dict__, "product_count": 0}


async def update_series(
    db: AsyncSession, series_id: UUID, name: str, description: str | None
) -> dict:
    series = await _get_series_or_404(db, series_id)
    dup = await db.execute(
        select(ProductSeries).where(ProductSeries.name == name, ProductSeries.id != series_id)
    )
    if dup.scalar_one_or_none():
        raise ConflictError("系列名稱已存在")
    series.name = name
    series.description = description
    await db.commit()
    await db.refresh(series)
    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.series_id == series_id)
    )
    count = count_result.scalar() or 0
    return {**series.__dict__, "product_count": count}


async def delete_series(db: AsyncSession, series_id: UUID) -> None:
    series = await _get_series_or_404(db, series_id)
    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.series_id == series_id)
    )
    if (count_result.scalar() or 0) > 0:
        raise ConflictError("系列下仍有商品，請先將所有商品移出系列")
    await db.delete(series)
    await db.commit()


# ── Tags ─────────────────────────────────────────────────────────────────────

async def list_tags(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Tag))
    all_tags = result.scalars().all()

    count_result = await db.execute(
        select(ProductTag.tag_id, func.count(ProductTag.product_id).label("cnt"))
        .group_by(ProductTag.tag_id)
    )
    count_map = {row.tag_id: row.cnt for row in count_result}

    return [
        {**t.__dict__, "product_count": count_map.get(t.id, 0)}
        for t in all_tags
    ]


async def create_tag(db: AsyncSession, name: str) -> dict:
    existing = await db.execute(select(Tag).where(Tag.name == name))
    if existing.scalar_one_or_none():
        raise ConflictError("標籤名稱已存在")
    tag = Tag(name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return {**tag.__dict__, "product_count": 0}


async def update_tag(db: AsyncSession, tag_id: UUID, name: str) -> dict:
    tag = await _get_tag_or_404(db, tag_id)
    dup = await db.execute(
        select(Tag).where(Tag.name == name, Tag.id != tag_id)
    )
    if dup.scalar_one_or_none():
        raise ConflictError("標籤名稱已存在")
    tag.name = name
    await db.commit()
    await db.refresh(tag)
    count_result = await db.execute(
        select(func.count(ProductTag.product_id)).where(ProductTag.tag_id == tag_id)
    )
    count = count_result.scalar() or 0
    return {**tag.__dict__, "product_count": count}


async def delete_tag(db: AsyncSession, tag_id: UUID) -> None:
    tag = await _get_tag_or_404(db, tag_id)
    await db.delete(tag)
    await db.commit()


# ── Products ─────────────────────────────────────────────────────────────────

async def list_products(
    db: AsyncSession,
    search: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(Product)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    if status:
        query = query.where(Product.status == status)

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    query = query.order_by(Product.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    items = []
    for p in products:
        tags = await _get_product_tags(db, p.id)
        variant_count_result = await db.execute(
            select(func.count(ProductVariant.id)).where(ProductVariant.product_id == p.id)
        )
        variant_count = variant_count_result.scalar() or 0
        items.append({
            **p.__dict__,
            "tags": tags,
            "variant_count": variant_count,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def create_product(db: AsyncSession, data: dict) -> dict:
    tag_ids = list(dict.fromkeys(data.pop("tag_ids", [])))
    series_id = data.get("series_id")
    if series_id:
        await _get_series_or_404(db, series_id)
        if data.get("series_order") is None:
            raise BadRequestError("指定系列時 series_order 必填")
    await _validate_tag_ids(db, tag_ids)

    product = Product(**data)
    db.add(product)
    await db.flush()

    for tag_id in tag_ids:
        db.add(ProductTag(product_id=product.id, tag_id=tag_id))

    await db.commit()
    await db.refresh(product)
    return await _enrich_product(db, product)


async def get_product(db: AsyncSession, product_id: UUID) -> dict:
    product = await _get_product_or_404(db, product_id)
    return await _enrich_product(db, product)


async def update_product(db: AsyncSession, product_id: UUID, data: dict) -> dict:
    product = await _get_product_or_404(db, product_id)
    tag_ids = list(dict.fromkeys(data.pop("tag_ids", [])))
    effective_series_id = data["series_id"] if "series_id" in data else product.series_id
    if effective_series_id:
        await _get_series_or_404(db, effective_series_id)
        effective_order = data["series_order"] if "series_order" in data else product.series_order
        if effective_order is None:
            raise BadRequestError("指定系列時 series_order 必填")
    await _validate_tag_ids(db, tag_ids)

    for key, value in data.items():
        setattr(product, key, value)

    await db.execute(
        ProductTag.__table__.delete().where(ProductTag.product_id == product_id)
    )
    for tag_id in tag_ids:
        db.add(ProductTag(product_id=product_id, tag_id=tag_id))

    await db.commit()
    await db.refresh(product)
    return await _enrich_product(db, product)


async def delete_product(db: AsyncSession, product_id: UUID) -> None:
    product = await _get_product_or_404(db, product_id)
    if product.status != ProductStatusEnum.off_sale:
        raise ConflictError("請先將商品下架才能刪除")
    active_variants = await db.execute(
        select(func.count(ProductVariant.id)).where(
            ProductVariant.product_id == product_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
    )
    if (active_variants.scalar() or 0) > 0:
        raise ConflictError("請先停用所有規格變體才能刪除商品")
    await db.delete(product)
    await db.commit()


# ── Product images ────────────────────────────────────────────────────────────

async def add_product_image(
    db: AsyncSession, product_id: UUID, image_url: str, sort_order: int
) -> ProductImage:
    await _get_product_or_404(db, product_id)
    image = ProductImage(product_id=product_id, image_url=image_url, sort_order=sort_order)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


async def delete_product_image(
    db: AsyncSession, product_id: UUID, image_id: UUID
) -> None:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id, ProductImage.product_id == product_id
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise NotFoundError("商品圖片不存在")
    await db.delete(image)
    await db.commit()


async def reorder_product_images(
    db: AsyncSession, product_id: UUID, order: list[UUID]
) -> list[ProductImage]:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage).where(ProductImage.product_id == product_id)
    )
    images = {img.id: img for img in result.scalars().all()}

    for img_id in order:
        if img_id not in images:
            raise BadRequestError(f"圖片 {img_id} 不屬於此商品")

    if len(order) != len(images) or set(order) != set(images.keys()):
        raise BadRequestError("order 必須包含此商品的所有圖片 ID（不可重複、不可缺漏）")

    for idx, img_id in enumerate(order):
        images[img_id].sort_order = idx

    await db.commit()
    return [images[img_id] for img_id in order]


# ── Product variants ──────────────────────────────────────────────────────────

async def create_or_update_variant(
    db: AsyncSession, product_id: UUID, production_job_id: UUID, price: float
) -> dict:
    await _get_product_or_404(db, product_id)
    job = await _get_approved_job_or_400(db, production_job_id)
    formula_base = calc_price_formula_base(
        float(job.canvas_w_cm), float(job.canvas_h_cm), job.detail, job.num_colors_used
    )

    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.production_job_id == production_job_id,
        )
    )
    variant = result.scalar_one_or_none()
    if variant:
        variant.price = Decimal(str(price))
        variant.price_formula_base = formula_base
        variant.is_active = True
    else:
        variant = ProductVariant(
            product_id=product_id,
            production_job_id=production_job_id,
            price=Decimal(str(price)),
            price_formula_base=formula_base,
        )
        db.add(variant)

    await db.commit()
    await db.refresh(variant)
    return _variant_with_job(variant, job)


async def update_variant(
    db: AsyncSession,
    product_id: UUID,
    variant_id: UUID,
    price: float | None,
    is_active: bool | None,
) -> dict:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id, ProductVariant.product_id == product_id
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundError("規格變體不存在")
    if price is not None:
        variant.price = Decimal(str(price))
    if is_active is not None:
        variant.is_active = is_active
    await db.commit()
    await db.refresh(variant)

    job_result = await db.execute(
        select(ProductionJob).where(ProductionJob.id == variant.production_job_id)
    )
    job = job_result.scalar_one()
    return _variant_with_job(variant, job)


async def delete_variant(
    db: AsyncSession, product_id: UUID, variant_id: UUID
) -> None:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id, ProductVariant.product_id == product_id
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundError("規格變體不存在")
    await db.delete(variant)
    await db.commit()


async def list_available_jobs(
    db: AsyncSession, exclude_product_id: UUID | None
) -> list[dict]:
    query = select(ProductionJob).where(
        ProductionJob.approved == True,  # noqa: E712
        ProductionJob.num_colors_used.isnot(None),
    )
    if exclude_product_id:
        excluded_subq = select(ProductVariant.production_job_id).where(
            ProductVariant.product_id == exclude_product_id
        )
        query = query.where(ProductionJob.id.notin_(excluded_subq))

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        {
            "id": job.id,
            "detail": job.detail,
            "difficulty": job.difficulty,
            "canvas_w_cm": float(job.canvas_w_cm),
            "canvas_h_cm": float(job.canvas_h_cm),
            "num_colors_used": job.num_colors_used,
            "price_formula_base": calc_price_formula_base(
                float(job.canvas_w_cm), float(job.canvas_h_cm), job.detail, job.num_colors_used
            ),
        }
        for job in jobs
    ]


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_series_or_404(db: AsyncSession, series_id: UUID) -> ProductSeries:
    result = await db.execute(select(ProductSeries).where(ProductSeries.id == series_id))
    series = result.scalar_one_or_none()
    if not series:
        raise NotFoundError("系列不存在")
    return series


async def _get_tag_or_404(db: AsyncSession, tag_id: UUID) -> Tag:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise NotFoundError("標籤不存在")
    return tag


async def _get_product_or_404(db: AsyncSession, product_id: UUID) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise NotFoundError("商品不存在")
    return product


async def _validate_tag_ids(db: AsyncSession, tag_ids: list[UUID]) -> None:
    if not tag_ids:
        return
    result = await db.execute(select(Tag.id).where(Tag.id.in_(tag_ids)))
    found = {row for row in result.scalars().all()}
    missing = [str(tid) for tid in tag_ids if tid not in found]
    if missing:
        raise BadRequestError(f"標籤不存在：{missing}")


async def _get_product_tags(db: AsyncSession, product_id: UUID) -> list[Tag]:
    result = await db.execute(
        select(Tag)
        .join(ProductTag, Tag.id == ProductTag.tag_id)
        .where(ProductTag.product_id == product_id)
    )
    return list(result.scalars().all())


async def _get_approved_job_or_400(
    db: AsyncSession, production_job_id: UUID
) -> ProductionJob:
    result = await db.execute(
        select(ProductionJob).where(ProductionJob.id == production_job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("製作記錄不存在")
    if not job.approved:
        raise BadRequestError("製作記錄尚未通過審核")
    if job.num_colors_used is None:
        raise BadRequestError("製作記錄缺少色數資訊，無法計算定價")
    return job


async def _enrich_product(db: AsyncSession, product: Product) -> dict:
    tags = await _get_product_tags(db, product.id)

    images_result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product.id)
        .order_by(ProductImage.sort_order)
    )
    images = list(images_result.scalars().all())

    variants_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    )
    raw_variants = list(variants_result.scalars().all())

    variants = []
    if raw_variants:
        job_ids = [v.production_job_id for v in raw_variants]
        jobs_result = await db.execute(
            select(ProductionJob).where(ProductionJob.id.in_(job_ids))
        )
        jobs_by_id = {j.id: j for j in jobs_result.scalars().all()}
        for v in raw_variants:
            job = jobs_by_id.get(v.production_job_id)
            variants.append(_variant_with_job(v, job))

    return {
        **product.__dict__,
        "tags": tags,
        "images": images,
        "variants": variants,
        "variant_count": len(raw_variants),
    }


def _variant_with_job(variant: ProductVariant, job: ProductionJob | None) -> dict:
    job_spec = None
    if job:
        job_spec = {
            "detail": job.detail,
            "difficulty": job.difficulty,
            "canvas_w_cm": float(job.canvas_w_cm),
            "canvas_h_cm": float(job.canvas_h_cm),
            "num_colors_used": job.num_colors_used,
        }
    return {
        "id": variant.id,
        "product_id": variant.product_id,
        "production_job_id": variant.production_job_id,
        "price": variant.price,
        "price_formula_base": variant.price_formula_base,
        "is_active": variant.is_active,
        "created_at": variant.created_at,
        "job_spec": job_spec,
    }
