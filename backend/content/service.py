from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from color.models import SystemSetting
from content.models import CaseCategory, CaseImage, CustomCase, Page
from core.exceptions import ConflictError, NotFoundError
from custom.models import CustomPhotoPrice, CustomPhotoSurcharge
from production.models import DifficultyEnum

# ── Pages ──────────────────────────────────────────────────────────────────────


async def get_page(db: AsyncSession, slug: str) -> Page:
    result = await db.execute(select(Page).where(Page.slug == slug))
    page = result.scalar_one_or_none()
    if page is None:
        raise NotFoundError("頁面不存在")
    return page


async def list_pages(db: AsyncSession) -> list[Page]:
    result = await db.execute(select(Page).order_by(Page.slug))
    return list(result.scalars().all())


async def upsert_page(db: AsyncSession, slug: str, title: str, content: str) -> Page:
    result = await db.execute(select(Page).where(Page.slug == slug))
    page = result.scalar_one_or_none()
    if page is None:
        page = Page(slug=slug, title=title, content=content)
        db.add(page)
    else:
        page.title = title
        page.content = content
    await db.commit()
    await db.refresh(page)
    return page


# ── System settings ────────────────────────────────────────────────────────────


_PUBLIC_SETTING_KEYS = {
    "bank_account_number",
    "bank_name",
    "bank_account_name",
    "product_info_tools",
    "product_info_material",
    "product_info_tips",
    "product_info_notes",
    "quote_reply_days",
    "admin_contact_email",  # store 端訂單頁顯示「如需修改請寄信至」
}


async def get_public_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(_PUBLIC_SETTING_KEYS))
    )
    return {s.key: s.value for s in result.scalars().all()}


async def list_admin_settings(db: AsyncSession) -> list[SystemSetting]:
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    return list(result.scalars().all())


async def upsert_setting(
    db: AsyncSession, key: str, value: str
) -> SystemSetting:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = SystemSetting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
        setting.updated_at = func.now()
    await db.commit()
    await db.refresh(setting)
    return setting


# ── Custom cases ───────────────────────────────────────────────────────────────


async def _load_case_images(db: AsyncSession, case_id: UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(CaseImage)
            .where(CaseImage.case_id == case_id)
            .order_by(CaseImage.sort_order, CaseImage.created_at)
        )
    ).scalars().all()
    return [
        {"id": r.id, "image_url": r.image_url, "sort_order": r.sort_order}
        for r in rows
    ]


async def _replace_case_images(
    db: AsyncSession, case_id: UUID, items: list[dict]
) -> None:
    """整批替換：清掉既有 case_images，按 list 順序重新插入（sort_order = index）。

    items 的 image_url 必填；sort_order 一律以陣列 index 為準，前端不必算。
    呼叫端要負責 commit。
    """
    from sqlalchemy import delete
    await db.execute(delete(CaseImage).where(CaseImage.case_id == case_id))
    for idx, item in enumerate(items):
        url = item.get("image_url")
        if not url:
            continue
        db.add(CaseImage(case_id=case_id, image_url=url, sort_order=idx))


def _serialize_case(c: CustomCase, images: list[dict] | None = None) -> dict:
    diff = c.difficulty
    return {
        "id": c.id,
        "image_url": c.image_url,
        "title": c.title,
        "description": c.description,
        "category_id": c.category_id,
        "canvas_w_cm": c.canvas_w_cm,
        "canvas_h_cm": c.canvas_h_cm,
        "difficulty": diff.value if hasattr(diff, "value") else (str(diff) if diff else None),
        "is_published": c.is_published,
        "created_at": c.created_at,
        "images": images or [],
    }


async def _serialize_case_with_images(
    db: AsyncSession, c: CustomCase
) -> dict:
    images = await _load_case_images(db, c.id)
    return _serialize_case(c, images)


async def public_list_cases(
    db: AsyncSession, category_id: UUID | None, page: int, page_size: int
) -> dict:
    query = select(CustomCase).where(CustomCase.is_published.is_(True))
    if category_id:
        query = query.where(CustomCase.category_id == category_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    rows = (await db.execute(
        query.order_by(CustomCase.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [await _serialize_case_with_images(db, c) for c in rows],
        "total": total, "page": page, "page_size": page_size,
    }


async def public_get_case(db: AsyncSession, case_id: UUID) -> dict:
    result = await db.execute(
        select(CustomCase).where(
            CustomCase.id == case_id, CustomCase.is_published.is_(True)
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError("案例不存在或未公開")
    return await _serialize_case_with_images(db, case)


async def admin_list_cases(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(CustomCase).order_by(CustomCase.created_at.desc())
    )).scalars().all()
    return [await _serialize_case_with_images(db, c) for c in rows]


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> CustomCase:
    result = await db.execute(select(CustomCase).where(CustomCase.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError("案例不存在")
    return case


async def admin_create_case(db: AsyncSession, data: dict) -> dict:
    if data.get("category_id"):
        cat = await db.execute(
            select(CaseCategory).where(CaseCategory.id == data["category_id"])
        )
        if cat.scalar_one_or_none() is None:
            raise NotFoundError("案例分類不存在")

    # 取出 images（不會傳給 ORM constructor）
    images_payload = data.pop("images", None)

    # image_url 必填於 DB level：若呼叫端只給 images，把第一張帶入 image_url
    if not data.get("image_url") and images_payload:
        data["image_url"] = images_payload[0].get("image_url")
    if not data.get("image_url"):
        raise ConflictError("案例至少需要一張圖片")

    case = CustomCase(**data)
    db.add(case)
    await db.flush()  # 拿到 case.id

    # 若有 images 陣列，用它做 source-of-truth；
    # 否則（向後相容）建一筆 sort_order=0 的 case_image 對應 image_url。
    if images_payload:
        await _replace_case_images(db, case.id, images_payload)
    else:
        await _replace_case_images(db, case.id, [{"image_url": case.image_url}])

    await db.commit()
    await db.refresh(case)
    return await _serialize_case_with_images(db, case)


async def admin_update_case(
    db: AsyncSession, case_id: UUID, data: dict
) -> dict:
    case = await _get_case_or_404(db, case_id)
    if "category_id" in data and data["category_id"] is not None:
        cat = await db.execute(
            select(CaseCategory).where(CaseCategory.id == data["category_id"])
        )
        if cat.scalar_one_or_none() is None:
            raise NotFoundError("案例分類不存在")

    images_payload = data.pop("images", None)

    for key, value in data.items():
        if key == "difficulty" and isinstance(value, str):
            value = DifficultyEnum(value)
        setattr(case, key, value)

    # 處理 images：傳了就同步 case_images（即使空陣列也視為「全清」），
    # 並把第一張 URL 同步到 case.image_url（前端列表縮圖讀此欄位）。
    if images_payload is not None:
        if len(images_payload) == 0:
            raise ConflictError("案例至少需要一張圖片")
        await _replace_case_images(db, case_id, images_payload)
        case.image_url = images_payload[0].get("image_url") or case.image_url

    await db.commit()
    await db.refresh(case)
    return await _serialize_case_with_images(db, case)


async def admin_delete_case(db: AsyncSession, case_id: UUID) -> None:
    case = await _get_case_or_404(db, case_id)
    await db.delete(case)
    await db.commit()


async def admin_toggle_publish_case(db: AsyncSession, case_id: UUID) -> dict:
    case = await _get_case_or_404(db, case_id)
    case.is_published = not case.is_published
    await db.commit()
    await db.refresh(case)
    return await _serialize_case_with_images(db, case)


# ── Case categories ────────────────────────────────────────────────────────────


async def list_categories(db: AsyncSession) -> list[CaseCategory]:
    rows = (await db.execute(
        select(CaseCategory).order_by(CaseCategory.name)
    )).scalars().all()
    return list(rows)


async def create_category(db: AsyncSession, name: str) -> CaseCategory:
    existing = await db.execute(select(CaseCategory).where(CaseCategory.name == name))
    if existing.scalar_one_or_none():
        raise ConflictError("分類名稱已存在")
    cat = CaseCategory(name=name)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def update_category(db: AsyncSession, cat_id: UUID, name: str) -> CaseCategory:
    cat = await _get_category_or_404(db, cat_id)
    dup = await db.execute(
        select(CaseCategory).where(
            CaseCategory.name == name, CaseCategory.id != cat_id
        )
    )
    if dup.scalar_one_or_none():
        raise ConflictError("分類名稱已存在")
    cat.name = name
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, cat_id: UUID) -> None:
    cat = await _get_category_or_404(db, cat_id)
    # ON DELETE SET NULL on FK takes care of custom_cases.category_id
    await db.delete(cat)
    await db.commit()


async def _get_category_or_404(db: AsyncSession, cat_id: UUID) -> CaseCategory:
    result = await db.execute(select(CaseCategory).where(CaseCategory.id == cat_id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise NotFoundError("案例分類不存在")
    return cat


# ── Custom photo prices ────────────────────────────────────────────────────────


def _serialize_price(p: CustomPhotoPrice) -> dict:
    return {
        "id": p.id,
        "canvas_w": p.canvas_w,
        "canvas_h": p.canvas_h,
        "difficulty": p.difficulty.value if hasattr(p.difficulty, "value") else str(p.difficulty),
        "price": float(p.price),
    }


async def list_photo_prices(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(CustomPhotoPrice).order_by(
            CustomPhotoPrice.canvas_w, CustomPhotoPrice.canvas_h, CustomPhotoPrice.difficulty
        )
    )).scalars().all()
    return [_serialize_price(p) for p in rows]


async def update_photo_price(
    db: AsyncSession, price_id: UUID, new_price: float
) -> dict:
    result = await db.execute(
        select(CustomPhotoPrice).where(CustomPhotoPrice.id == price_id)
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise NotFoundError("價格項目不存在")
    p.price = new_price
    await db.commit()
    await db.refresh(p)
    return _serialize_price(p)


# ── Custom photo surcharges ────────────────────────────────────────────────────


def _serialize_surcharge(s: CustomPhotoSurcharge) -> dict:
    return {
        "id": s.id,
        "category": s.category,
        "label": s.label,
        "amount": float(s.amount),
        "is_active": s.is_active,
        "created_at": s.created_at,
    }


async def list_surcharges(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(CustomPhotoSurcharge)
        .order_by(CustomPhotoSurcharge.category, CustomPhotoSurcharge.label)
    )).scalars().all()
    return [_serialize_surcharge(s) for s in rows]


async def create_surcharge(db: AsyncSession, data: dict) -> dict:
    s = CustomPhotoSurcharge(**data)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _serialize_surcharge(s)


async def update_surcharge(
    db: AsyncSession, surcharge_id: UUID, data: dict
) -> dict:
    s = await _get_surcharge_or_404(db, surcharge_id)
    for key, value in data.items():
        setattr(s, key, value)
    await db.commit()
    await db.refresh(s)
    return _serialize_surcharge(s)


async def toggle_surcharge_active(
    db: AsyncSession, surcharge_id: UUID
) -> dict:
    s = await _get_surcharge_or_404(db, surcharge_id)
    s.is_active = not s.is_active
    await db.commit()
    await db.refresh(s)
    return _serialize_surcharge(s)


async def delete_surcharge(db: AsyncSession, surcharge_id: UUID) -> None:
    s = await _get_surcharge_or_404(db, surcharge_id)
    await db.delete(s)
    await db.commit()


async def _get_surcharge_or_404(
    db: AsyncSession, surcharge_id: UUID
) -> CustomPhotoSurcharge:
    result = await db.execute(
        select(CustomPhotoSurcharge).where(CustomPhotoSurcharge.id == surcharge_id)
    )
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError("加費項目不存在")
    return s
