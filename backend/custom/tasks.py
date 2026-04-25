import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.celery_app import celery_app
from core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="custom.expire_quotes")
def expire_quotes():
    """E12: 每 5 分鐘掃描已寄出但逾期的報價，標記為 quote_expired 並通知客戶。"""
    asyncio.run(_expire_quotes_async())


async def _expire_quotes_async():
    from custom.service import expire_quotes_async

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with AsyncSession(bind=engine, expire_on_commit=False) as db:
        try:
            count = await expire_quotes_async(db)
            logger.info(f"Expired {count} quote(s)")
        except Exception as e:
            logger.error(f"Failed to expire quotes: {e}")
            await db.rollback()
    await engine.dispose()


celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "expire-quotes-every-5-min": {
        "task": "custom.expire_quotes",
        "schedule": 300,
    },
}
