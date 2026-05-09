# ruff: noqa: I001
# _windows_compat MUST run before any module that imports asyncpg (WMI workaround for
# broken Windows dev machines). Ruff would resort imports otherwise.
import core._windows_compat  # noqa: F401

from celery import Celery

# 預先 import 全部 models，讓 SQLAlchemy 在 worker 啟動時就解析完所有 FK 關聯
# （production.tasks 操作 production_jobs，但其 FK 指向 custom_requests / images / users，
# 沒先註冊會在 db.add() 時 raise NoReferencedTableError）
import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402
import content.models  # noqa: F401, E402
import custom.models  # noqa: F401, E402
import discount.models  # noqa: F401, E402
import notifications.models  # noqa: F401, E402
import orders.models  # noqa: F401, E402
import palette.models  # noqa: F401, E402
import print_batch.models  # noqa: F401, E402
import product.models  # noqa: F401, E402
import production.models  # noqa: F401, E402
import users.models  # noqa: F401, E402
from core.config import settings

celery_app = Celery(
    "paintlearn",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["production.tasks", "custom.tasks", "orders.tasks", "auth.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Taipei",
)
