import asyncio
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt as _bcrypt
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from auth.models import EmailVerificationToken, TokenTypeEnum, User
from core.config import settings
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from users.models import ShippingProfile


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


async def _send_email(to: str, subject: str, html: str) -> None:
    try:
        import resend
        resend.api_key = settings.resend_api_key
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: resend.Emails.send({
                "from": settings.resend_from_email,
                "to": to,
                "subject": subject,
                "html": html,
            }),
        )
    except Exception as e:
        logger.warning("Email send failed to %s: %s", to, e)


_ALLOWED_PROFILE_FIELDS = {"name", "gender", "birthday"}


async def update_profile(
    db: AsyncSession,
    user: User,
    fields: dict,
) -> User:
    for key, value in fields.items():
        if key in _ALLOWED_PROFILE_FIELDS:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> None:
    if not _verify_password(old_password, user.password_hash):
        raise BadRequestError("舊密碼錯誤")
    user.password_hash = _hash_password(new_password)
    await db.commit()


async def request_email_change(
    db: AsyncSession, user: User, new_email: str
) -> None:
    if new_email == user.email:
        raise BadRequestError("新 Email 不能與目前 Email 相同")

    if new_email == user.pending_email:
        raise ConflictError("此 Email 與待驗證的 Email 相同")

    result = await db.execute(
        select(User).where(
            (User.id != user.id)
            & ((User.email == new_email) | (User.pending_email == new_email))
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError("此 Email 已被使用")

    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.token_type == TokenTypeEnum.email_change,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(UTC))
    )

    user.pending_email = new_email
    await db.flush()

    plain = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    ))
    await db.commit()

    verify_url = f"{settings.frontend_url}/verify-email?token={plain}"
    body = (
        f"<p>請點擊以下連結驗證您的新 Email：</p>"
        f"<p><a href='{verify_url}'>{verify_url}</a></p>"
        f"<p>連結 24 小時內有效。</p>"
    )
    await _send_email(new_email, "PaintLearn — 驗證您的新 Email", body)


async def list_shipping_profiles(
    db: AsyncSession, user_id: UUID
) -> list[ShippingProfile]:
    result = await db.execute(
        select(ShippingProfile)
        .where(ShippingProfile.user_id == user_id)
        .order_by(ShippingProfile.is_default.desc(), ShippingProfile.created_at)
    )
    return list(result.scalars().all())


SHIPPING_PROFILE_LIMIT = 10


async def create_shipping_profile(
    db: AsyncSession, user_id: UUID, data: dict
) -> ShippingProfile:
    count_result = await db.execute(
        select(func.count()).select_from(ShippingProfile).where(ShippingProfile.user_id == user_id)
    )
    if count_result.scalar() >= SHIPPING_PROFILE_LIMIT:
        raise BadRequestError(f"收件資料最多 {SHIPPING_PROFILE_LIMIT} 筆")

    if data.get("is_default"):
        await db.execute(
            update(ShippingProfile)
            .where(ShippingProfile.user_id == user_id)
            .values(is_default=False)
        )

    profile = ShippingProfile(user_id=user_id, **data)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_shipping_profile(
    db: AsyncSession, user_id: UUID, profile_id: UUID, data: dict
) -> ShippingProfile:
    result = await db.execute(
        select(ShippingProfile).where(
            ShippingProfile.id == profile_id,
            ShippingProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("收件資料不存在")

    if data.get("is_default"):
        await db.execute(
            update(ShippingProfile)
            .where(ShippingProfile.user_id == user_id, ShippingProfile.id != profile_id)
            .values(is_default=False)
        )

    for key, value in data.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_shipping_profile(
    db: AsyncSession, user_id: UUID, profile_id: UUID
) -> None:
    result = await db.execute(
        select(ShippingProfile).where(
            ShippingProfile.id == profile_id,
            ShippingProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("收件資料不存在")

    await db.delete(profile)
    await db.commit()


async def set_default_shipping_profile(
    db: AsyncSession, user_id: UUID, profile_id: UUID
) -> ShippingProfile:
    result = await db.execute(
        select(ShippingProfile).where(
            ShippingProfile.id == profile_id,
            ShippingProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("收件資料不存在")

    await db.execute(
        update(ShippingProfile)
        .where(ShippingProfile.user_id == user_id)
        .values(is_default=False)
    )
    profile.is_default = True
    await db.commit()
    await db.refresh(profile)
    return profile
