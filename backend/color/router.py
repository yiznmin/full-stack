from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from color import service
from color.schemas.request import (
    AddStockRequest,
    CreateColorRequest,
    RevertRgbRequest,
    UpdateColorRequest,
    UpdateRgbRequest,
)
from color.schemas.response import (
    AddStockResponse,
    ColorListResponse,
    PhysicalColorResponse,
    RgbHistoryListResponse,
    ShortageDashboardResponse,
)
from core.database import get_db
from dependencies.auth import require_admin

router = APIRouter(tags=["Admin - Colors"])


@router.get("/admin/colors", response_model=ColorListResponse)
async def list_colors(
    color_family: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_colors(db, color_family, is_active, search)
    return ColorListResponse(items=items)


@router.get("/admin/colors/shortage-dashboard", response_model=ShortageDashboardResponse)
async def shortage_dashboard(
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.shortage_dashboard(db)
    return ShortageDashboardResponse(items=items)


@router.post("/admin/colors", response_model=PhysicalColorResponse, status_code=201)
async def create_color(
    body: CreateColorRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_color(db, body.model_dump(), operator.id)


@router.put("/admin/colors/{color_id}", response_model=PhysicalColorResponse)
async def update_color(
    color_id: UUID,
    body: UpdateColorRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # exclude_unset=True：只含使用者實際送來的欄位，省略的不會誤蓋掉 DB 值
    return await service.update_color(db, color_id, body.model_dump(exclude_unset=True))


@router.patch("/admin/colors/{color_id}/toggle-active", response_model=PhysicalColorResponse)
async def toggle_active(
    color_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.toggle_active(db, color_id)


@router.patch("/admin/colors/{color_id}/rgb", response_model=PhysicalColorResponse)
async def update_rgb(
    color_id: UUID,
    body: UpdateRgbRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """校正實體色 RGB。Body 接 hex（"#RRGGBB"）或 rgb（[R,G,B]）二擇一。

    用於 palette workspace 彈跳視窗：管理員依實品顏料微調系統存的 RGB。
    """
    return await service.update_rgb(db, color_id, body.rgb, operator.id, "manual")


@router.get(
    "/admin/colors/{color_id}/rgb-history", response_model=RgbHistoryListResponse
)
async def list_rgb_history(
    color_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await service.list_rgb_history(db, color_id)
    return RgbHistoryListResponse(items=items)


@router.post(
    "/admin/colors/{color_id}/rgb-revert", response_model=PhysicalColorResponse
)
async def revert_rgb(
    color_id: UUID,
    body: RevertRgbRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.revert_rgb(
        db, color_id, UUID(body.history_id), operator.id
    )


@router.patch("/admin/colors/{color_id}/stock", response_model=AddStockResponse)
async def add_stock(
    color_id: UUID,
    body: AddStockRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.add_stock(db, color_id, body.add_ml)
