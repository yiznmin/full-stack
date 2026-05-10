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

    verify_url = f"{settings.frontend_url}/verify-email/{plain}"
    body = (
        f"<p>請點擊以下連結驗證您的新 Email：</p>"
        f"<p><a href='{verify_url}'>{verify_url}</a></p>"
        f"<p>連結 24 小時內有效。</p>"
    )
    await _send_email(new_email, "PaintLearn — 驗證您的新 Email", body)


async def get_member_stats(db: AsyncSession, user_id: UUID) -> dict:
    """會員 dashboard 用的統計 — 一次拿齊：訂單數 / 完成數 / 待付款 /
    可用券數 / 待確認報價數。

    取代多個 round-trip。所有 count 都是 user-bound（owner-only）。
    """
    from sqlalchemy import func as sa_func  # noqa: PLC0415

    from custom.models import CustomRequest, CustomRequestStatusEnum  # noqa: PLC0415
    from discount.models import UserCoupon  # noqa: PLC0415
    from orders.models import Order, OrderStatusEnum  # noqa: PLC0415

    # Orders
    orders_total = (await db.execute(
        select(sa_func.count(Order.id)).where(Order.user_id == user_id)
    )).scalar() or 0
    orders_completed = (await db.execute(
        select(sa_func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.status == OrderStatusEnum.completed,
        )
    )).scalar() or 0
    orders_pending_payment = (await db.execute(
        select(sa_func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.status == OrderStatusEnum.pending_payment,
        )
    )).scalar() or 0

    # Available coupons（未過期 + 未使用）
    now = datetime.now(UTC)
    available_coupons = (await db.execute(
        select(sa_func.count(UserCoupon.id)).where(
            UserCoupon.user_id == user_id,
            UserCoupon.is_used.is_(False),
            (UserCoupon.expires_at.is_(None)) | (UserCoupon.expires_at > now),
        )
    )).scalar() or 0

    # 待確認的報價
    custom_quote_pending = (await db.execute(
        select(sa_func.count(CustomRequest.id)).where(
            CustomRequest.user_id == user_id,
            CustomRequest.status == CustomRequestStatusEnum.quote_sent,
        )
    )).scalar() or 0

    return {
        "orders_total": orders_total,
        "orders_completed": orders_completed,
        "orders_pending_payment": orders_pending_payment,
        "available_coupons": available_coupons,
        "custom_quote_pending": custom_quote_pending,
    }


async def resend_email_change_verification(
    db: AsyncSession, user: User,
) -> None:
    """重寄 pending_email 的驗證信（用戶沒收到 / 過期想重發）。

    必要條件：user.pending_email 必須有值（已 request 過）。
    行為：作廢舊 token + 簽新 token + 寄信至 pending_email。
    """
    if not user.pending_email:
        raise BadRequestError("目前沒有待驗證的新 Email", code="NO_PENDING_EMAIL")

    # 作廢所有舊 email_change token
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.token_type == TokenTypeEnum.email_change,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(UTC))
    )

    plain = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    ))
    await db.commit()

    verify_url = f"{settings.frontend_url}/verify-email/{plain}"
    body = (
        f"<p>請點擊以下連結驗證您的新 Email：</p>"
        f"<p><a href='{verify_url}'>{verify_url}</a></p>"
        f"<p>連結 24 小時內有效。</p>"
    )
    await _send_email(user.pending_email, "PaintLearn — 驗證您的新 Email（重寄）", body)


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
