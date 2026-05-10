import logging
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
    Theme,
)
from production.models import ProductionJob

logger = logging.getLogger(__name__)


def _public_filled_url(raw: str | None) -> str | None:
    """把 production_jobs.filled_template_url 轉成瀏覽器可載入的 https URL（短期預覽用）。

    - None → None
    - 已是 https → 直接回（兼容舊資料 / 測試 stub URL）
    - gs:// → 走 production._make_signed_url 產 15-min TTL signed URL
    - 解析失敗 → log warning + return None（避免一筆壞資料把整頁 list endpoint 弄掛）

    ⚠ 這個 URL 有 15 分鐘 TTL，**不可寫入永久欄位（如 cover_image_url）**。
    永久存放請用 _persistent_firebase_url。
    """
    if not raw:
        return None
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    try:
        from production.service import _make_signed_url  # noqa: PLC0415

        return _make_signed_url(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning("filled_template_url signed URL 失敗：%s — %s", raw, e)
        return None


def _persistent_firebase_url(raw: str | None) -> str | None:
    """把 gs:// URL 轉成 Firebase 下載 URL（永久有效，公開讀由 storage.rules 控制）。

    格式：https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}?alt=media
    用途：寫入永久欄位（如 products.cover_image_url），與 upload service 行為一致。
    """
    if not raw:
        return None
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    if not raw.startswith("gs://"):
        return None
    try:
        import urllib.parse  # noqa: PLC0415

        # gs://bucket/path → bucket, path
        bucket_and_path = raw[len("gs://"):]
        bucket_name, _, path = bucket_and_path.partition("/")
        if not bucket_name or not path:
            return None
        encoded = urllib.parse.quote(path, safe="")
        return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded}?alt=media"
    except Exception as e:  # noqa: BLE001
        logger.warning("gs:// → firebase download URL 失敗：%s — %s", raw, e)
        return None


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


# ── Themes ───────────────────────────────────────────────────────────────────

async def list_themes(
    db: AsyncSession, search: str | None, page: int, page_size: int
) -> dict:
    query = select(Theme)
    if search:
        query = query.where(Theme.name.ilike(f"%{search}%"))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    rows = (await db.execute(
        query.order_by(Theme.sort_order.asc(), Theme.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    series_count_result = await db.execute(
        select(ProductSeries.theme_id, func.count(ProductSeries.id).label("cnt"))
        .where(ProductSeries.theme_id.isnot(None))
        .group_by(ProductSeries.theme_id)
    )
    series_count_map = {r.theme_id: r.cnt for r in series_count_result}

    items = [
        {**t.__dict__, "series_count": series_count_map.get(t.id, 0)}
        for t in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_theme(db: AsyncSession, theme_id: UUID) -> dict:
    theme = await _get_theme_or_404(db, theme_id)
    count_result = await db.execute(
        select(func.count(ProductSeries.id)).where(ProductSeries.theme_id == theme_id)
    )
    return {**theme.__dict__, "series_count": count_result.scalar() or 0}


async def create_theme(db: AsyncSession, data: dict) -> dict:
    existing = await db.execute(select(Theme).where(Theme.name == data["name"]))
    if existing.scalar_one_or_none():
        raise ConflictError("主題名稱已存在")
    theme = Theme(**data)
    db.add(theme)
    await db.commit()
    await db.refresh(theme)
    return {**theme.__dict__, "series_count": 0}


async def update_theme(db: AsyncSession, theme_id: UUID, data: dict) -> dict:
    theme = await _get_theme_or_404(db, theme_id)
    dup = await db.execute(
        select(Theme).where(Theme.name == data["name"], Theme.id != theme_id)
    )
    if dup.scalar_one_or_none():
        raise ConflictError("主題名稱已存在")
    for key, value in data.items():
        setattr(theme, key, value)
    await db.commit()
    await db.refresh(theme)
    count_result = await db.execute(
        select(func.count(ProductSeries.id)).where(ProductSeries.theme_id == theme_id)
    )
    return {**theme.__dict__, "series_count": count_result.scalar() or 0}


async def delete_theme(db: AsyncSession, theme_id: UUID) -> None:
    theme = await _get_theme_or_404(db, theme_id)
    # ON DELETE SET NULL — series 自動變成未分類，不需手動處理
    await db.delete(theme)
    await db.commit()


async def _get_theme_or_404(db: AsyncSession, theme_id: UUID) -> Theme:
    result = await db.execute(select(Theme).where(Theme.id == theme_id))
    theme = result.scalar_one_or_none()
    if theme is None:
        raise NotFoundError("主題不存在")
    return theme


# ── Series ───────────────────────────────────────────────────────────────────

async def list_series(db: AsyncSession, theme_id: UUID | None = None) -> list[dict]:
    query = select(ProductSeries)
    if theme_id is not None:
        query = query.where(ProductSeries.theme_id == theme_id)
    result = await db.execute(query)
    all_series = result.scalars().all()

    count_result = await db.execute(
        select(Product.series_id, func.count(Product.id).label("cnt"))
        .where(Product.series_id.isnot(None))
        .group_by(Product.series_id)
    )
    count_map = {row.series_id: row.cnt for row in count_result}

    theme_ids = {s.theme_id for s in all_series if s.theme_id is not None}
    theme_map: dict[UUID, str] = {}
    if theme_ids:
        theme_rows = await db.execute(
            select(Theme.id, Theme.name).where(Theme.id.in_(theme_ids))
        )
        theme_map = {row.id: row.name for row in theme_rows}

    return [
        {
            **s.__dict__,
            "product_count": count_map.get(s.id, 0),
            "theme_name": theme_map.get(s.theme_id) if s.theme_id else None,
        }
        for s in all_series
    ]


async def create_series(
    db: AsyncSession,
    name: str,
    description: str | None,
    theme_id: UUID | None = None,
    is_featured: bool = False,
    sample_cover_image_url: str | None = None,
) -> dict:
    existing = await db.execute(select(ProductSeries).where(ProductSeries.name == name))
    if existing.scalar_one_or_none():
        raise ConflictError("系列名稱已存在")
    if theme_id is not None:
        await _get_theme_or_404(db, theme_id)
    series = ProductSeries(
        name=name,
        description=description,
        theme_id=theme_id,
        is_featured=is_featured,
        sample_cover_image_url=sample_cover_image_url,
    )
    db.add(series)
    await db.commit()
    await db.refresh(series)
    theme_name = None
    if theme_id is not None:
        theme = await db.get(Theme, theme_id)
        theme_name = theme.name if theme else None
    return {**series.__dict__, "product_count": 0, "theme_name": theme_name}


async def update_series(
    db: AsyncSession,
    series_id: UUID,
    name: str,
    description: str | None,
    theme_id: UUID | None = None,
    is_featured: bool = False,
    sample_cover_image_url: str | None = None,
) -> dict:
    series = await _get_series_or_404(db, series_id)
    dup = await db.execute(
        select(ProductSeries).where(ProductSeries.name == name, ProductSeries.id != series_id)
    )
    if dup.scalar_one_or_none():
        raise ConflictError("系列名稱已存在")
    if theme_id is not None:
        await _get_theme_or_404(db, theme_id)
    series.name = name
    series.description = description
    series.theme_id = theme_id
    series.is_featured = is_featured
    series.sample_cover_image_url = sample_cover_image_url
    await db.commit()
    await db.refresh(series)
    count_result = await db.execute(
        select(func.count(Product.id)).where(Product.series_id == series_id)
    )
    count = count_result.scalar() or 0
    theme_name = None
    if theme_id is not None:
        theme = await db.get(Theme, theme_id)
        theme_name = theme.name if theme else None
    return {**series.__dict__, "product_count": count, "theme_name": theme_name}


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

    series_ids = {p.series_id for p in products if p.series_id}
    series_name_by_id: dict[UUID, str] = {}
    if series_ids:
        series_result = await db.execute(
            select(ProductSeries).where(ProductSeries.id.in_(series_ids))
        )
        series_name_by_id = {s.id: s.name for s in series_result.scalars().all()}

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
            "series_name": series_name_by_id.get(p.series_id) if p.series_id else None,
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

    # 自動處理 cover_image_url：production_jobs/ → 複製到公開路徑
    if data.get("cover_image_url"):
        data["cover_image_url"] = _maybe_repath_to_public(data["cover_image_url"])

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
    # 自動處理 cover_image_url：production_jobs/ → 複製到公開路徑
    if data.get("cover_image_url"):
        data["cover_image_url"] = _maybe_repath_to_public(data["cover_image_url"])
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
    # on_sale 不能直接刪（避免前台破圖）；draft / off_sale 都允許
    if product.status == ProductStatusEnum.on_sale:
        raise ConflictError("請先將商品下架才能刪除")

    # 任何 status 都要檢查 OrderItem 引用：order_items.product_variant_id 沒設 ondelete=
    # CASCADE，products → variants 是 CASCADE 但 variants → order_items 不是，硬刪會
    # IntegrityError 500。雖然「draft 不應該有訂單」是設計直覺，但 update_product
    # 沒擋反向 status 轉移（on_sale → draft 合法），不能假設 invariant 成立。
    from orders.models import OrderItem  # noqa: PLC0415

    referenced = await db.execute(
        select(func.count(OrderItem.id))
        .join(ProductVariant, OrderItem.product_variant_id == ProductVariant.id)
        .where(ProductVariant.product_id == product_id)
    )
    if (referenced.scalar() or 0) > 0:
        raise ConflictError("此商品的變體被訂單引用，無法刪除")

    # off_sale 曾上架過，需確認 admin 已主動停用所有變體（避免誤刪有銷售紀錄的）
    # draft 從未上架過 → 不需此檢查（前面已過 OrderItem 引用檢查）
    if product.status == ProductStatusEnum.off_sale:
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

def _maybe_repath_to_public(image_url: str) -> str:
    """如果 URL 是 Firebase 內部路徑（production_jobs/），server-side 複製到
    product_images/ 公開可讀路徑。其他 URL（包括外部 URL）原樣回傳。

    回傳新的 Firebase download URL（如有複製）或原本 URL。
    """
    import logging
    import urllib.parse
    import uuid as _uuid

    log = logging.getLogger(__name__)

    # 解析 Firebase download URL
    # https://firebasestorage.googleapis.com/v0/b/<bucket>/o/<encoded_path>?alt=media
    if "firebasestorage.googleapis.com/v0/b/" not in image_url:
        return image_url
    try:
        prefix = image_url.split("/o/", 1)[1]
        encoded_path = prefix.split("?", 1)[0]
        path = urllib.parse.unquote(encoded_path)
    except (IndexError, ValueError):
        return image_url

    # 只處理 production_jobs/ 路徑
    if not path.startswith("production_jobs/"):
        return image_url

    try:
        from core.firebase import get_bucket
        bucket = get_bucket()
        source_blob = bucket.blob(path)
        if not source_blob.exists():
            log.warning(f"Source blob not found: {path}")
            return image_url

        # 目標路徑：product_images/<uuid>_<basename>
        basename = path.rsplit("/", 1)[-1]
        new_path = f"product_images/{_uuid.uuid4().hex}_{basename}"
        new_blob = bucket.blob(new_path)
        new_blob.rewrite(source_blob)

        # 回 Firebase download URL（與 generate_public_signed_url 同 pattern）
        encoded_new = urllib.parse.quote(new_path, safe="")
        return f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{encoded_new}?alt=media"
    except Exception as e:
        log.warning(f"Failed to repath image to public path: {e}")
        return image_url


async def add_product_image(
    db: AsyncSession, product_id: UUID, image_url: str, sort_order: int
) -> ProductImage:
    await _get_product_or_404(db, product_id)
    # 自動處理：production_jobs/ 路徑（admin 匯入變體模板時）→ 複製到 product_images/ 公開讀
    final_url = _maybe_repath_to_public(image_url)
    image = ProductImage(product_id=product_id, image_url=final_url, sort_order=sort_order)
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


async def list_product_images(
    db: AsyncSession, product_id: UUID
) -> list[ProductImage]:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
    )
    return list(result.scalars().all())


async def list_product_variants(
    db: AsyncSession, product_id: UUID
) -> list[dict]:
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == product_id)
    )
    raw_variants = list(result.scalars().all())
    if not raw_variants:
        return []
    job_ids = [v.production_job_id for v in raw_variants]
    jobs_result = await db.execute(
        select(ProductionJob).where(ProductionJob.id.in_(job_ids))
    )
    jobs_by_id = {j.id: j for j in jobs_result.scalars().all()}
    return [_variant_with_job(v, jobs_by_id.get(v.production_job_id)) for v in raw_variants]


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
            "image_id": job.image_id,
            "detail": job.detail,
            "difficulty": job.difficulty,
            "canvas_w_cm": float(job.canvas_w_cm),
            "canvas_h_cm": float(job.canvas_h_cm),
            "num_colors_used": job.num_colors_used,
            "price_formula_base": calc_price_formula_base(
                float(job.canvas_w_cm), float(job.canvas_h_cm), job.detail, job.num_colors_used
            ),
            # picker 顯示用（短期 signed URL）
            "preview_url": _public_filled_url(job.filled_template_url),
            # 寫入 cover_image_url 永久欄位用（Firebase download URL）
            "cover_url": _persistent_firebase_url(job.filled_template_url),
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
            # 顯示用（15-min signed URL）
            "filled_template_url": _public_filled_url(job.filled_template_url),
            # 寫入永久欄位用（Firebase download URL，無 TTL）
            "cover_url": _persistent_firebase_url(job.filled_template_url),
            "svg_url": job.svg_url,
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


# ── Public (store-browse) endpoints ───────────────────────────────────────────


_DIFFICULTY_ORDER = {
    "beginner": 0,
    "elementary": 1,
    "intermediate": 2,
    "advanced": 3,
}


def _enum_str(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _parse_canvas_size(canvas_size: str) -> tuple[int, int]:
    parts = canvas_size.lower().split("x")
    if len(parts) != 2:
        raise BadRequestError("canvas_size 格式應為 WxH（例如 30x40）")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise BadRequestError("canvas_size 必須為整數 WxH") from exc


async def _public_product_brief(db: AsyncSession, product: Product) -> dict:
    rows = (await db.execute(
        select(ProductVariant, ProductionJob)
        .join(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
        .where(
            ProductVariant.product_id == product.id,
            ProductVariant.is_active.is_(True),
        )
    )).all()

    if not rows:
        prices = [Decimal("0")]
        difficulties: list[str] = []
    else:
        prices = [v.price for v, _ in rows]
        difficulties = [_enum_str(j.difficulty) for _, j in rows]

    def _key(d):
        return _DIFFICULTY_ORDER.get(d, 0)

    diff_min = min(difficulties, key=_key) if difficulties else None
    diff_max = max(difficulties, key=_key) if difficulties else None

    return {
        "id": product.id,
        "title": product.title,
        "cover_image_url": product.cover_image_url,
        "difficulty_range": [diff_min, diff_max] if diff_min else [],
        "price_min": float(min(prices)),
        "price_max": float(max(prices)),
        "is_preorder": False,
        "is_featured": product.is_featured,
    }


async def public_list_products(
    db: AsyncSession,
    difficulty: str | None,
    detail: str | None,
    canvas_size: str | None,
    tag_id: UUID | None,
    series_id: UUID | None,
    sort: str,
    page: int,
    page_size: int,
    theme_id: UUID | None = None,
    featured: bool | None = None,
) -> dict:
    query = select(Product).where(Product.status == ProductStatusEnum.on_sale)

    # theme_id 過濾：撈該主題下所有 series_id，再用 series_id 過濾
    # （Product 沒直接 theme_id，要透過 series 查）
    if theme_id is not None:
        theme_series_ids = (
            select(ProductSeries.id).where(ProductSeries.theme_id == theme_id)
        )
        query = query.where(Product.series_id.in_(theme_series_ids))

    # featured 過濾
    if featured is not None:
        query = query.where(Product.is_featured == featured)

    # Always require at least one active variant — exclude "zombie" products
    active_variant_pids = (
        select(ProductVariant.product_id)
        .join(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
        .where(ProductVariant.is_active.is_(True))
    )
    if difficulty:
        active_variant_pids = active_variant_pids.where(
            ProductionJob.difficulty == difficulty
        )
    if detail:
        active_variant_pids = active_variant_pids.where(
            ProductionJob.detail == detail
        )
    if canvas_size:
        w, h = _parse_canvas_size(canvas_size)
        active_variant_pids = active_variant_pids.where(
            ProductionJob.canvas_w_cm == w, ProductionJob.canvas_h_cm == h,
        )
    query = query.where(Product.id.in_(active_variant_pids))

    if tag_id:
        query = query.where(
            Product.id.in_(
                select(ProductTag.product_id).where(ProductTag.tag_id == tag_id)
            )
        )
    if series_id:
        query = query.where(Product.series_id == series_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    if sort in ("price_asc", "price_desc"):
        price_sub = (
            select(
                ProductVariant.product_id.label("pid"),
                func.min(ProductVariant.price).label("min_price"),
            )
            .where(ProductVariant.is_active.is_(True))
            .group_by(ProductVariant.product_id)
            .subquery()
        )
        query = query.join(price_sub, Product.id == price_sub.c.pid, isouter=True)
        if sort == "price_asc":
            query = query.order_by(price_sub.c.min_price.asc())
        else:
            query = query.order_by(price_sub.c.min_price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    products = (await db.execute(query)).scalars().all()

    items = [await _public_product_brief(db, p) for p in products]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def public_search_products(
    db: AsyncSession, q: str, page: int, page_size: int,
) -> dict:
    pattern = f"%{q}%"
    tag_match = (
        select(ProductTag.product_id)
        .join(Tag, ProductTag.tag_id == Tag.id)
        .where(Tag.name.ilike(pattern))
    )
    active_variant_pids = (
        select(ProductVariant.product_id).where(ProductVariant.is_active.is_(True))
    )
    query = select(Product).where(
        Product.status == ProductStatusEnum.on_sale,
        Product.id.in_(active_variant_pids),
        (
            Product.title.ilike(pattern)
            | Product.description.ilike(pattern)
            | Product.id.in_(tag_match)
        ),
    )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    products = (await db.execute(
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = [await _public_product_brief(db, p) for p in products]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def public_get_product(db: AsyncSession, product_id: UUID) -> dict:
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.status == ProductStatusEnum.on_sale,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise NotFoundError("商品不存在或未上架")

    images_result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
    )
    images = list(images_result.scalars().all())

    tag_rows = (await db.execute(
        select(Tag).join(ProductTag, ProductTag.tag_id == Tag.id)
        .where(ProductTag.product_id == product_id)
    )).scalars().all()
    tags = [{"id": t.id, "name": t.name} for t in tag_rows]

    variant_rows = (await db.execute(
        select(ProductVariant, ProductionJob)
        .join(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
        .where(
            ProductVariant.product_id == product_id,
            ProductVariant.is_active.is_(True),
        )
    )).all()
    variants = [
        {
            "id": v.id,
            "canvas_w_cm": float(j.canvas_w_cm),
            "canvas_h_cm": float(j.canvas_h_cm),
            "difficulty": _enum_str(j.difficulty),
            "detail": _enum_str(j.detail),
            "color_count": j.num_colors_used,
            "price": float(v.price),
            "is_active": v.is_active,
            "is_preorder": False,
            "filled_template_url": _public_filled_url(j.filled_template_url),
        }
        for v, j in variant_rows
    ]

    series_payload = None
    if product.series_id:
        s_result = await db.execute(
            select(ProductSeries).where(ProductSeries.id == product.series_id)
        )
        series = s_result.scalar_one()
        active_pids = (
            select(ProductVariant.product_id).where(ProductVariant.is_active.is_(True))
        )
        siblings_rows = (await db.execute(
            select(Product).where(
                Product.series_id == series.id,
                Product.status == ProductStatusEnum.on_sale,
                Product.id != product.id,
                Product.id.in_(active_pids),
            ).order_by(Product.series_order.asc(), Product.created_at.asc())
        )).scalars().all()
        siblings = []
        for sib in siblings_rows:
            brief = await _public_product_brief(db, sib)
            siblings.append({
                "id": brief["id"],
                "title": brief["title"],
                "cover_image_url": brief["cover_image_url"],
                "price_min": brief["price_min"],
                "is_preorder": brief["is_preorder"],
            })
        series_payload = {
            "id": series.id, "name": series.name, "products": siblings,
        }

    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "cover_image_url": product.cover_image_url,
        "is_featured": product.is_featured,
        "images": images,
        "series": series_payload,
        "tags": tags,
        "variants": variants,
    }


async def public_related_products(db: AsyncSession, product_id: UUID) -> dict:
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.status == ProductStatusEnum.on_sale,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise NotFoundError("商品不存在或未上架")

    if product.series_id is None:
        return {"series": None, "items": []}

    series = (await db.execute(
        select(ProductSeries).where(ProductSeries.id == product.series_id)
    )).scalar_one()

    active_pids = (
        select(ProductVariant.product_id).where(ProductVariant.is_active.is_(True))
    )
    siblings = (await db.execute(
        select(Product).where(
            Product.series_id == product.series_id,
            Product.status == ProductStatusEnum.on_sale,
            Product.id != product_id,
            Product.id.in_(active_pids),
        ).order_by(Product.series_order.asc(), Product.created_at.asc())
    )).scalars().all()

    items = []
    for sib in siblings:
        brief = await _public_product_brief(db, sib)
        items.append({
            "id": brief["id"], "title": brief["title"],
            "cover_image_url": brief["cover_image_url"],
            "price_min": brief["price_min"],
            "is_preorder": brief["is_preorder"],
        })
    return {
        "series": {"id": series.id, "name": series.name},
        "items": items,
    }


async def public_list_tags(db: AsyncSession) -> dict:
    rows = (await db.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return {"items": [{"id": t.id, "name": t.name} for t in rows]}


# ── Public Themes / Series ────────────────────────────────────────────────────
# store_design_brief.md §P0+ 主題與系列公開瀏覽。
# 跟 admin list_themes/list_series 區分：
#   - 公開只回 series_count + product_count（admin 沒 product_count）
#   - 依 sort_order 排（admin 端用 search 找）
#   - 過濾 published 商品（only on_sale + 有 active variant）

async def public_list_themes(db: AsyncSession) -> dict:
    """所有主題（不分頁，量級小且 store 通常一次顯示完）。每個含 series_count + product_count。"""
    themes = (await db.execute(
        select(Theme).order_by(Theme.sort_order.asc(), Theme.created_at.desc())
    )).scalars().all()

    if not themes:
        return {"items": []}

    # 各 theme 的 series_count
    series_count_rows = (await db.execute(
        select(ProductSeries.theme_id, func.count(ProductSeries.id).label("cnt"))
        .where(ProductSeries.theme_id.in_([t.id for t in themes]))
        .group_by(ProductSeries.theme_id)
    )).all()
    series_count_map = {r.theme_id: r.cnt for r in series_count_rows}

    # 各 theme 的 product_count（透過 series 連 Product，僅 on_sale）
    # SELECT s.theme_id, COUNT(p.id) FROM product_series s JOIN products p ON p.series_id=s.id
    #   WHERE s.theme_id IN (...) AND p.status='on_sale' GROUP BY s.theme_id
    product_count_rows = (await db.execute(
        select(ProductSeries.theme_id, func.count(Product.id).label("cnt"))
        .join(Product, Product.series_id == ProductSeries.id)
        .where(
            ProductSeries.theme_id.in_([t.id for t in themes]),
            Product.status == ProductStatusEnum.on_sale,
        )
        .group_by(ProductSeries.theme_id)
    )).all()
    product_count_map = {r.theme_id: r.cnt for r in product_count_rows}

    items = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "cover_image_url": t.cover_image_url,
            "sort_order": t.sort_order,
            "series_count": series_count_map.get(t.id, 0),
            "product_count": product_count_map.get(t.id, 0),
        }
        for t in themes
    ]
    return {"items": items}


async def public_get_theme(db: AsyncSession, theme_id: UUID) -> dict:
    """單一主題詳情 + 該主題下所有系列（含 product_count）。"""
    theme = await _get_theme_or_404(db, theme_id)

    # 撈該 theme 的所有 series
    series_rows = (await db.execute(
        select(ProductSeries).where(ProductSeries.theme_id == theme_id)
        .order_by(ProductSeries.created_at.asc())
    )).scalars().all()

    # 各 series 的 product_count
    if series_rows:
        count_rows = (await db.execute(
            select(Product.series_id, func.count(Product.id).label("cnt"))
            .where(
                Product.series_id.in_([s.id for s in series_rows]),
                Product.status == ProductStatusEnum.on_sale,
            )
            .group_by(Product.series_id)
        )).all()
        count_map = {r.series_id: r.cnt for r in count_rows}
    else:
        count_map = {}

    return {
        "id": theme.id,
        "name": theme.name,
        "description": theme.description,
        "cover_image_url": theme.cover_image_url,
        "sort_order": theme.sort_order,
        "series": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "product_count": count_map.get(s.id, 0),
            }
            for s in series_rows
        ],
    }


async def public_list_series(
    db: AsyncSession,
    theme_id: UUID | None = None,
    featured: bool | None = None,
) -> dict:
    """所有系列；可帶 theme_id / featured 過濾。每筆含 theme_name + product_count + is_featured。"""
    query = select(ProductSeries)
    if theme_id is not None:
        query = query.where(ProductSeries.theme_id == theme_id)
    if featured is not None:
        query = query.where(ProductSeries.is_featured == featured)

    series_rows = (await db.execute(
        query.order_by(ProductSeries.created_at.desc())
    )).scalars().all()

    if not series_rows:
        return {"items": []}

    # product_count（only on_sale）
    count_rows = (await db.execute(
        select(Product.series_id, func.count(Product.id).label("cnt"))
        .where(
            Product.series_id.in_([s.id for s in series_rows]),
            Product.status == ProductStatusEnum.on_sale,
        )
        .group_by(Product.series_id)
    )).all()
    count_map = {r.series_id: r.cnt for r in count_rows}

    # theme_name
    theme_ids = {s.theme_id for s in series_rows if s.theme_id is not None}
    theme_map: dict[UUID, str] = {}
    if theme_ids:
        theme_rows = (await db.execute(
            select(Theme.id, Theme.name).where(Theme.id.in_(theme_ids))
        )).all()
        theme_map = {r.id: r.name for r in theme_rows}

    items = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "theme_id": s.theme_id,
            "theme_name": theme_map.get(s.theme_id) if s.theme_id else None,
            "is_featured": s.is_featured,
            "product_count": count_map.get(s.id, 0),
        }
        for s in series_rows
    ]
    return {"items": items}


async def public_get_series(db: AsyncSession, series_id: UUID) -> dict:
    """單一系列詳情 + 該系列下所有 on_sale 商品（依 series_order ASC）。"""
    series_row = (await db.execute(
        select(ProductSeries).where(ProductSeries.id == series_id)
    )).scalar_one_or_none()
    if series_row is None:
        raise NotFoundError("系列不存在")

    # 撈該系列下所有 on_sale + 至少一個 active variant 的商品
    active_variant_pids = (
        select(ProductVariant.product_id).where(ProductVariant.is_active.is_(True))
    )
    products = (await db.execute(
        select(Product)
        .where(
            Product.series_id == series_id,
            Product.status == ProductStatusEnum.on_sale,
            Product.id.in_(active_variant_pids),
        )
        .order_by(
            # series_order NULL 放最後；等同 PostgreSQL NULLS LAST
            Product.series_order.asc().nulls_last(),
            Product.created_at.asc(),
        )
    )).scalars().all()

    items = [await _public_product_brief(db, p) for p in products]

    # theme_name
    theme_name: str | None = None
    if series_row.theme_id is not None:
        theme_row = (await db.execute(
            select(Theme.name).where(Theme.id == series_row.theme_id)
        )).scalar_one_or_none()
        theme_name = theme_row

    return {
        "id": series_row.id,
        "name": series_row.name,
        "description": series_row.description,
        "theme_id": series_row.theme_id,
        "theme_name": theme_name,
        "is_featured": series_row.is_featured,
        "sample_cover_image_url": series_row.sample_cover_image_url,
        "products": items,
    }
