import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.celery_app import celery_app
from core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="auth.cleanup_unverified_users")
def cleanup_unverified_users():
    """每小時掃描，刪除註冊 25h 仍未驗證 email 的客戶帳號。

    觸發案例：
    - Resend API 失敗 → 信沒寄出 → user 永遠驗證不了 → email 被佔
    - User 註冊後不點驗證連結 → email 被佔
    刪除後 email 釋出可重新註冊。
    """
    asyncio.run(_cleanup_async())


async def _cleanup_async():
    from auth.service import cleanup_unverified_users as cleanup_fn

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with AsyncSession(bind=engine, expire_on_commit=False) as db:
        try:
            count = await cleanup_fn(db)
            if count > 0:
                logger.info(f"cleanup_unverified_users task: deleted {count} stale account(s)")
        except Exception as e:
            logger.error(f"cleanup_unverified_users task failed: {e}")
            await db.rollback()
    await engine.dispose()


celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "cleanup-unverified-users-every-1h": {
        "task": "auth.cleanup_unverified_users",
        "schedule": 3600,  # 每小時跑一次
    },
}
