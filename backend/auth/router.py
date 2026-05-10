from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth import service
from auth.schemas.request import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from auth.schemas.response import LoginResponse, MeResponse, MessageResponse, VerifyEmailResponse
from core.config import settings
from core.database import get_db
from core.rate_limit import (
    rate_limit_admin_login,
    rate_limit_forgot_password,
    rate_limit_login,
    rate_limit_register,
    rate_limit_resend_verification,
    rate_limit_reset_password,
)
from dependencies.auth import require_admin, require_auth

router = APIRouter()


def _set_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=max_age,
    )


# ── Customer Auth ──────────────────────────────────────────────────────────────

@router.post("/auth/register", status_code=201, response_model=MessageResponse, tags=["Auth"])
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_register),
):
    await service.register(db, body.name, body.email, body.password)
    return MessageResponse(message="驗證信已寄出")


@router.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_login),
):
    user, token = await service.login(db, body.email, body.password)
    _set_cookie(response, token, settings.jwt_expire_days_customer * 86400)
    return LoginResponse(id=str(user.id), name=user.name, role=user.role)


@router.post("/auth/logout", response_model=MessageResponse, tags=["Auth"])
async def logout(response: Response, _=Depends(require_auth)):
    response.delete_cookie("access_token")
    return MessageResponse(message="已登出")


@router.get("/auth/me", response_model=MeResponse, tags=["Auth"])
async def me(user=Depends(require_auth)):
    return user


@router.post("/auth/verify-email", response_model=VerifyEmailResponse, tags=["Auth"])
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token_type = await service.verify_email(db, body.token)
    return VerifyEmailResponse(token_type=token_type)


@router.post("/auth/resend-verification", response_model=MessageResponse, tags=["Auth"])
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_resend_verification),
):
    await service.resend_verification(db, body.email)
    return MessageResponse(message="若此 email 已登記且尚未驗證，驗證信已重新寄出")


@router.post("/auth/forgot-password", response_model=MessageResponse, tags=["Auth"])
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_forgot_password),
):
    await service.forgot_password(db, body.email)
    return MessageResponse(message="若帳號存在，重設連結已寄出")


@router.post("/auth/reset-password", response_model=MessageResponse, tags=["Auth"])
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_reset_password),
):
    await service.reset_password(db, body.token, body.new_password)
    return MessageResponse(message="密碼已更新")


# ── Admin Auth ─────────────────────────────────────────────────────────────────

@router.post("/admin/auth/login", response_model=LoginResponse, tags=["Admin Auth"])
async def admin_login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_admin_login),
):
    user, token = await service.login(db, body.email, body.password, admin_only=True)
    _set_cookie(response, token, settings.jwt_expire_hours_admin * 3600)
    return LoginResponse(id=str(user.id), name=user.name, role=user.role)


@router.post("/admin/auth/logout", response_model=MessageResponse, tags=["Admin Auth"])
async def admin_logout(response: Response, _=Depends(require_admin)):
    response.delete_cookie("access_token")
    return MessageResponse(message="已登出")


@router.post("/admin/auth/forgot-password", response_model=MessageResponse, tags=["Admin Auth"])
async def admin_forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_forgot_password),
):
    await service.forgot_password(db, body.email, admin_only=True)
    return MessageResponse(message="若帳號存在，重設連結已寄出")
