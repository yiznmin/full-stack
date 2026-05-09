from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from content import service
from content.schemas.request import (
    CaseCategoryCreateRequest,
    CaseCategoryUpdateRequest,
    CustomCaseCreateRequest,
    CustomCaseUpdateRequest,
    CustomPhotoPriceUpdateRequest,
    CustomPhotoSurchargeCreateRequest,
    CustomPhotoSurchargeUpdateRequest,
    PageUpsertRequest,
    SystemSettingUpsertRequest,
)
from content.schemas.response import (
    CaseCategoryListResponse,
    CaseCategoryResponse,
    CustomCaseListResponse,
    CustomCaseResponse,
    CustomPhotoPriceListResponse,
    CustomPhotoPriceResponse,
    CustomPhotoSurchargeListResponse,
    CustomPhotoSurchargeResponse,
    PageListResponse,
    PageResponse,
    PublicSettingsResponse,
    SystemSettingListResponse,
    SystemSettingResponse,
)
from core.database import get_db
from dependencies.auth import require_admin

router = APIRouter(tags=["Content"])


# ── Pages ─────────────────────────────────────────────────────────────────────


_SLUG_PATTERN = r"^[a-z0-9_]{1,50}$"


@router.get("/pages/{slug}", response_model=PageResponse)
async def get_page(
    slug: str = Path(..., pattern=_SLUG_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_page(db, slug)


@router.get("/admin/pages", response_model=PageListResponse)
async def admin_list_pages(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_pages(db)
    return {"items": items}


@router.put("/admin/pages/{slug}", response_model=PageResponse)
async def admin_upsert_page(
    body: PageUpsertRequest,
    slug: str = Path(..., pattern=_SLUG_PATTERN),
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.upsert_page(db, slug, body.title, body.content)


# ── System Settings ───────────────────────────────────────────────────────────


@router.get("/system-settings/public", response_model=PublicSettingsResponse)
async def public_settings(
    db: AsyncSession = Depends(get_db),
):
    return {"items": await service.get_public_settings(db)}


@router.get("/admin/system-settings", response_model=SystemSettingListResponse)
async def admin_list_settings(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_admin_settings(db)
    return {"items": items}


@router.patch("/admin/system-settings", response_model=SystemSettingResponse)
async def admin_upsert_setting(
    body: SystemSettingUpsertRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.upsert_setting(db, body.key, body.value)


# ── Custom Cases ──────────────────────────────────────────────────────────────


@router.get("/custom-cases", response_model=CustomCaseListResponse)
async def public_list_cases(
    category_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.public_list_cases(db, category_id, page, page_size)


@router.get("/custom-cases/{case_id}", response_model=CustomCaseResponse)
async def public_get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await service.public_get_case(db, case_id)


@router.get("/admin/custom-cases", response_model=CustomCaseListResponse)
async def admin_list_cases(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.admin_list_cases(db)
    return {"items": items, "total": len(items), "page": 1, "page_size": len(items)}


@router.post(
    "/admin/custom-cases", status_code=201, response_model=CustomCaseResponse
)
async def admin_create_case(
    body: CustomCaseCreateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_create_case(db, body.model_dump())


@router.put("/admin/custom-cases/{case_id}", response_model=CustomCaseResponse)
async def admin_update_case(
    case_id: UUID,
    body: CustomCaseUpdateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_update_case(
        db, case_id, body.model_dump(exclude_unset=True)
    )


@router.delete(
    "/admin/custom-cases/{case_id}", status_code=204, response_model=None
)
async def admin_delete_case(
    case_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.admin_delete_case(db, case_id)


@router.patch(
    "/admin/custom-cases/{case_id}/toggle-publish",
    response_model=CustomCaseResponse,
)
async def admin_toggle_publish(
    case_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_toggle_publish_case(db, case_id)


# ── Case Categories ───────────────────────────────────────────────────────────


@router.get("/case-categories", response_model=CaseCategoryListResponse)
async def public_list_categories(
    db: AsyncSession = Depends(get_db),
):
    """公開：列出案例分類（給 store /custom/cases 過濾 UI 用）。"""
    items = await service.list_categories(db)
    return {"items": items}


@router.get("/admin/case-categories", response_model=CaseCategoryListResponse)
async def list_categories(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_categories(db)
    return {"items": items}


@router.post(
    "/admin/case-categories", status_code=201, response_model=CaseCategoryResponse
)
async def create_category(
    body: CaseCategoryCreateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_category(db, body.name)


@router.put(
    "/admin/case-categories/{cat_id}", response_model=CaseCategoryResponse
)
async def update_category(
    cat_id: UUID,
    body: CaseCategoryUpdateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_category(db, cat_id, body.name)


@router.delete(
    "/admin/case-categories/{cat_id}", status_code=204, response_model=None
)
async def delete_category(
    cat_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_category(db, cat_id)


# ── Custom Photo Prices ───────────────────────────────────────────────────────


@router.get(
    "/admin/custom-photo-prices", response_model=CustomPhotoPriceListResponse
)
async def list_photo_prices(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_photo_prices(db)
    return {"items": items}


@router.put(
    "/admin/custom-photo-prices/{price_id}", response_model=CustomPhotoPriceResponse
)
async def update_photo_price(
    price_id: UUID,
    body: CustomPhotoPriceUpdateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_photo_price(db, price_id, body.price)


@router.post(
    "/admin/custom-photo-prices/seed-defaults",
    description=(
        "一次性 seed 預設客製照片價格表（17 canvas × 4 difficulty = 68 筆）。"
        "冪等：已存在的 (canvas_w, canvas_h, difficulty) 組合會跳過。"
        "用途：production DB 從沒跑過 seed_content.py 時用此 endpoint 補。"
    ),
)
async def seed_default_photo_prices(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.seed_default_photo_prices(db)


# ── Custom Photo Surcharges ───────────────────────────────────────────────────


@router.get(
    "/admin/custom-photo-surcharges",
    response_model=CustomPhotoSurchargeListResponse,
)
async def list_surcharges(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_surcharges(db)
    return {"items": items}


@router.post(
    "/admin/custom-photo-surcharges",
    status_code=201,
    response_model=CustomPhotoSurchargeResponse,
)
async def create_surcharge(
    body: CustomPhotoSurchargeCreateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_surcharge(db, body.model_dump())


@router.put(
    "/admin/custom-photo-surcharges/{surcharge_id}",
    response_model=CustomPhotoSurchargeResponse,
)
async def update_surcharge(
    surcharge_id: UUID,
    body: CustomPhotoSurchargeUpdateRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_surcharge(
        db, surcharge_id, body.model_dump(exclude_unset=True)
    )


@router.patch(
    "/admin/custom-photo-surcharges/{surcharge_id}/toggle-active",
    response_model=CustomPhotoSurchargeResponse,
)
async def toggle_surcharge(
    surcharge_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.toggle_surcharge_active(db, surcharge_id)


@router.delete(
    "/admin/custom-photo-surcharges/{surcharge_id}",
    status_code=204,
    response_model=None,
)
async def delete_surcharge(
    surcharge_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_surcharge(db, surcharge_id)
