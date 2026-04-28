"""
建立第一個管理員帳號（初次部署用）

用法：
    cd backend
    python scripts/create_admin.py --email admin@paintlearn.com --password <password>
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402  # bypass broken WMI before asyncpg

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import bcrypt as _bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings


async def create_admin(email: str, password: str) -> None:
    from auth.models import User

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"錯誤：{email} 已存在")
            await engine.dispose()
            return

        user = User(
            name="Admin",
            email=email,
            password_hash=_bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode(),
            role="admin",
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        await db.commit()
        print(f"管理員帳號已建立：{email}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="建立管理員帳號")
    parser.add_argument("--email", required=True, help="管理員 Email")
    parser.add_argument("--password", required=True, help="管理員密碼")
    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.password))
