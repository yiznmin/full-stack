#!/usr/bin/env bash
# backend-worker entrypoint — Railway 部署用
#
# 不跑 alembic migration（避免兩個 service 同時 alembic upgrade race；
# 雖然 alembic 內部有 advisory lock，但 web 已負責 migration、worker 啟動時 schema 已就緒）。

set -euo pipefail

cd /app

echo "[start_worker] starting celery worker..."
exec celery -A core.celery_app worker \
    --loglevel=info \
    --concurrency=1 \
    --pool=solo
