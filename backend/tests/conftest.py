import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import auth.models  # noqa: F401
import color.models  # noqa: F401
import content.models  # noqa: F401
import custom.models  # noqa: F401
import discount.models  # noqa: F401
import notifications.models  # noqa: F401
import orders.models  # noqa: F401
import palette.models  # noqa: F401
import print_batch.models  # noqa: F401
import product.models  # noqa: F401
import production.models  # noqa: F401
import users.models  # noqa: F401
from core.config import settings
from core.database import Base, get_db
from main import app

DB_URL = settings.test_database_url or settings.database_url
_BACKEND = Path(__file__).parent.parent


def _run_script(script: str) -> None:
    subprocess.run([sys.executable, f"scripts/{script}"], cwd=_BACKEND, check=True)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create tables once per session via subprocess to avoid asyncio event loop conflicts."""
    _run_script("reset_test_db.py")
    yield
    _run_script("drop_test_db.py")


@pytest_asyncio.fixture
async def db(setup_db):
    engine = create_async_engine(DB_URL, poolclass=NullPool)
    conn = await engine.connect()
    for table in reversed(Base.metadata.sorted_tables):
        await conn.execute(table.delete())
    await conn.commit()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    yield session
    await session.close()
    await conn.rollback()
    await conn.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
