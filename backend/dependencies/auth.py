import jwt
from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.exceptions import ForbiddenError, UnauthorizedError


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not access_token:
        raise UnauthorizedError()
    try:
        # PyJWT 鎖定演算法白名單避免 CVE-2024-33663（algorithm confusion）類攻擊。
        # 過期 token 會 raise jwt.ExpiredSignatureError，亦屬 jwt.InvalidTokenError 子類。
        payload = jwt.decode(
            access_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("user_id")
        if not user_id:
            raise UnauthorizedError()
    except jwt.InvalidTokenError:
        raise UnauthorizedError() from None

    from auth.models import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError()
    if not user.is_active:
        raise UnauthorizedError("帳號已停用")
    return user


async def require_auth(user=Depends(get_current_user)):
    return user


async def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise ForbiddenError()
    return user
