import asyncio
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt
import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import EmailVerificationToken, PasswordResetToken, TokenTypeEnum, User
from core.config import settings
from core.exceptions import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)

def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def _make_jwt(user_id: str, role: str, expire_seconds: int) -> str:
    exp = datetime.now(UTC) + timedelta(seconds=expire_seconds)
    return jwt.encode(
        {"user_id": user_id, "role": role, "exp": exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


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
        logger.warning(f"Email send failed to {to}: {e}")


async def register(db: AsyncSession, name: str, email: str, password: str) -> None:
    result = await db.execute(
        select(User).where((User.email == email) | (User.pending_email == email))
    )
    if result.scalar_one_or_none():
        raise ConflictError("此 Email 已被使用")

    user = User(
        name=name,
        email=email,
        password_hash=_hash_password(password),
    )
    db.add(user)
    await db.flush()

    plain = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.signup,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    ))
    await db.commit()

    verify_url = f"{settings.frontend_url}/verify-email/{plain}"
    body = (
        f"<p>請點擊以下連結驗證您的帳號：</p>"
        f"<p><a href='{verify_url}'>{verify_url}</a></p>"
        f"<p>連結 24 小時內有效。</p>"
    )
    await _send_email(email, "PaintLearn — 請驗證您的 Email", body)


async def login(
    db: AsyncSession, email: str, password: str, admin_only: bool = False
) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(password, user.password_hash):
        raise UnauthorizedError("帳號或密碼錯誤")

    if not user.is_email_verified:
        raise ForbiddenError("請先驗證您的 Email")

    if not user.is_active:
        raise ForbiddenError("帳號已停用")

    if admin_only and user.role != "admin":
        raise ForbiddenError("權限不足")

    expire_seconds = (
        settings.jwt_expire_hours_admin * 3600
        if user.role == "admin"
        else settings.jwt_expire_days_customer * 86400
    )
    token = _make_jwt(str(user.id), user.role, expire_seconds)
    return user, token


async def verify_email(db: AsyncSession, plain_token: str) -> str:
    hashed = _hash_token(plain_token)
    now = datetime.now(UTC)

    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == hashed)
    )
    token = result.scalar_one_or_none()

    if not token or token.used_at is not None:
        raise BadRequestError("token 無效或已使用")
    if token.expires_at.replace(tzinfo=UTC) < now:
        raise BadRequestError("token 已過期")

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one()

    token.used_at = now

    if token.token_type == TokenTypeEnum.signup:
        user.is_email_verified = True
        await db.commit()
        try:
            from coupons.service import issue_new_user_coupon
            await issue_new_user_coupon(db, user.id)
        except Exception:
            logger.info("Coupon issuance skipped for user %s", user.id)
    else:
        user.email = user.pending_email
        user.pending_email = None
        await db.commit()

    return token.token_type.value


async def resend_verification(db: AsyncSession, email: str) -> None:
    result = await db.execute(
        select(User).where(User.email == email, User.is_email_verified == False)  # noqa: E712
    )
    user = result.scalar_one_or_none()

    if user:
        plain = secrets.token_urlsafe(32)
        db.add(EmailVerificationToken(
            user_id=user.id,
            token=_hash_token(plain),
            token_type=TokenTypeEnum.signup,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        ))
        await db.commit()

        verify_url = f"{settings.frontend_url}/verify-email/{plain}"
        body = (
            f"<p>請點擊以下連結驗證您的帳號：</p>"
            f"<p><a href='{verify_url}'>{verify_url}</a></p>"
            f"<p>連結 24 小時內有效。</p>"
        )
        await _send_email(email, "PaintLearn — 重新驗證您的 Email", body)


async def forgot_password(db: AsyncSession, email: str, admin_only: bool = False) -> None:
    query = select(User).where(User.email == email)
    if admin_only:
        query = query.where(User.role == "admin")

    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user:
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at == None)  # noqa: E711
            .values(used_at=datetime.now(UTC))
        )
        plain = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id,
            token=_hash_token(plain),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        await db.commit()

        base_url = settings.admin_url if admin_only else settings.frontend_url
        reset_url = f"{base_url}/reset-password/{plain}"
        body = (
            f"<p>請點擊以下連結重設您的密碼：</p>"
            f"<p><a href='{reset_url}'>{reset_url}</a></p>"
            f"<p>連結 1 小時內有效。</p>"
        )
        await _send_email(email, "PaintLearn — 重設密碼", body)


async def cleanup_unverified_users(db: AsyncSession, grace_hours: int = 25) -> int:
    """刪除註冊後 grace_hours 仍未驗證 email 的客戶帳號 + 其驗證 / 重設 token。

    用途：寄信失敗 / 用戶不點驗證連結時，避免 email 被永久佔用。
    24h 是 verification token TTL，加 1h 緩衝避免邊界情況。
    只刪 role=customer，不會誤殺 admin。
    """
    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(hours=grace_hours)

    # 找符合條件的 user ids（避免 ORM relationship 自動 cascade 衝突）
    result = await db.execute(
        select(User.id).where(
            User.role == "customer",
            User.is_email_verified.is_(False),
            User.created_at < cutoff,
        )
    )
    user_ids = [row[0] for row in result.all()]

    if not user_ids:
        return 0

    # 先刪 token（避免 FK 違反），再刪 user
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id.in_(user_ids))
    )
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids))
    )
    await db.execute(delete(User).where(User.id.in_(user_ids)))
    await db.commit()

    logger.info(f"cleanup_unverified_users: deleted {len(user_ids)} stale customer(s)")
    return len(user_ids)


async def reset_password(db: AsyncSession, plain_token: str, new_password: str) -> None:
    hashed = _hash_token(plain_token)
    now = datetime.now(UTC)

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == hashed)
    )
    token = result.scalar_one_or_none()

    if not token or token.used_at is not None:
        raise BadRequestError("token 無效或已使用")
    if token.expires_at.replace(tzinfo=UTC) < now:
        raise BadRequestError("token 已過期")

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one()

    user.password_hash = _hash_password(new_password)
    token.used_at = now
    await db.commit()
