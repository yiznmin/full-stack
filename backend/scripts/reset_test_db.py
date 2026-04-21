"""Reset test DB - run in a subprocess to avoid pytest asyncio conflicts."""
# ruff: noqa: I001
import asyncio
import sys

sys.path.insert(0, ".")

import auth.models  # noqa: E402, F401
import color.models  # noqa: E402, F401
import palette.models  # noqa: E402, F401
import production.models  # noqa: E402, F401
import users.models  # noqa: E402, F401
from core.config import settings  # noqa: E402
from core.database import Base  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


async def main():
    url = settings.test_database_url or settings.database_url
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("DB reset OK")


asyncio.run(main())
