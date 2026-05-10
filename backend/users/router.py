from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth.schemas.response import MessageResponse
from core.database import get_db
from dependencies.auth import require_auth
from users import service
from users.schemas.request import (
    ChangePasswordRequest,
    RequestEmailChangeRequest,
    ShippingProfileRequest,
    UpdateProfileRequest,
)
from users.schemas.response import (
    MemberStatsResponse,
    ShippingProfileResponse,
    UserProfileResponse,
)

router = APIRouter()


# ── Profile ────────────────────────────────────────────────────────────────────

@router.patch("/users/me", response_model=UserProfileResponse, tags=["Users"])
async def update_profile(
    body: UpdateProfileRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    updated = await service.update_profile(db, user, body.model_dump(exclude_unset=True))
    return updated


@router.post("/users/me/change-password", response_model=None, status_code=204, tags=["Users"])
async def change_password(
    body: ChangePasswordRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await service.change_password(db, user, body.old_password, body.new_password)
    return Response(status_code=204)


@router.post("/users/me/request-email-change", response_model=MessageResponse, tags=["Users"])
async def request_email_change(
    body: RequestEmailChangeRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await service.request_email_change(db, user, str(body.new_email))
    return MessageResponse(message="驗證信已寄出")


@router.post(
    "/users/me/resend-email-change-verification",
    response_model=MessageResponse,
    tags=["Users"],
)
async def resend_email_change_verification(
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """重寄 pending_email 的驗證信（用戶說沒收到 / 想重新觸發）。"""
    await service.resend_email_change_verification(db, user)
    return MessageResponse(message="驗證信已重新寄出")


@router.get("/users/me/stats", response_model=MemberStatsResponse, tags=["Users"])
async def get_member_stats(
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """會員 dashboard 統計：訂單數 / 完成數 / 待付款 / 可用券 / 待確認報價。"""
    return await service.get_member_stats(db, user.id)


# ── Shipping Profiles ──────────────────────────────────────────────────────────

@router.get(
    "/users/me/shipping-profiles",
    response_model=list[ShippingProfileResponse],
    tags=["Users"],
)
async def list_shipping_profiles(
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_shipping_profiles(db, user.id)


@router.post(
    "/users/me/shipping-profiles",
    response_model=ShippingProfileResponse,
    status_code=201,
    tags=["Users"],
)
async def create_shipping_profile(
    body: ShippingProfileRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_shipping_profile(db, user.id, body.model_dump())


@router.put(
    "/users/me/shipping-profiles/{profile_id}",
    response_model=ShippingProfileResponse,
    tags=["Users"],
)
async def update_shipping_profile(
    profile_id: UUID,
    body: ShippingProfileRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_shipping_profile(db, user.id, profile_id, body.model_dump())


@router.delete(
    "/users/me/shipping-profiles/{profile_id}",
    response_model=None,
    status_code=204,
    tags=["Users"],
)
async def delete_shipping_profile(
    profile_id: UUID,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_shipping_profile(db, user.id, profile_id)
    return Response(status_code=204)


@router.patch(
    "/users/me/shipping-profiles/{profile_id}/set-default",
    response_model=ShippingProfileResponse,
    tags=["Users"],
)
async def set_default_shipping_profile(
    profile_id: UUID,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.set_default_shipping_profile(db, user.id, profile_id)
