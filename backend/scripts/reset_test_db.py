"""Reset test DB - run in a subprocess to avoid pytest asyncio conflicts."""
# ruff: noqa: I001
import asyncio
import sys

sys.path.insert(0, ".")

import core._windows_compat  # noqa: F401  # bypass broken WMI before asyncpg

# Windows asyncpg fix: Selector event loop avoids hangs on Proactor
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import auth.models  # noqa: E402, F401
import color.models  # noqa: E402, F401
import content.models  # noqa: E402, F401
import custom.models  # noqa: E402, F401
import discount.models  # noqa: E402, F401
import notifications.models  # noqa: E402, F401
import orders.models  # noqa: E402, F401
import palette.models  # noqa: E402, F401
import print_batch.models  # noqa: E402, F401
import product.models  # noqa: E402, F401
import production.models  # noqa: E402, F401
import users.models  # noqa: E402, F401
from core.config import settings  # noqa: E402
from core.database import Base  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


async def main():
    from sqlalchemy import text  # noqa: E402

    url = settings.test_database_url or settings.database_url
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        # 直接 DROP SCHEMA public CASCADE 砍光，避免 cycle FK / 舊 named constraint
        # 與 new model（use_alter=True）的 mismatch — 比 metadata.drop_all 更乾淨
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("DROP SEQUENCE IF EXISTS order_number_seq"))
        await conn.execute(text("DROP TYPE IF EXISTS customrequesttypeenum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS customrequeststatusenum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS messagesendertypeenum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS notificationstatusenum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS printbatchstatusenum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS printbatchitemsourceenum CASCADE"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1"))
        # Seed system_settings.quote_reply_days for module 10
        await conn.execute(text(
            "INSERT INTO system_settings (key, value) VALUES "
            "('quote_reply_days', '3') ON CONFLICT (key) DO NOTHING"
        ))
    await engine.dispose()
    print("DB reset OK")


asyncio.run(main())
