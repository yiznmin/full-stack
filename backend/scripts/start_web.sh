#!/usr/bin/env bash
# backend-web entrypoint — Railway 部署用
#
# 流程：
#   1. alembic upgrade head（決議 #6: web service 跑 migration；worker 不跑）
#   2. 啟動 uvicorn（Railway 會給 PORT env var）

set -euo pipefail

cd /app

echo "[start_web] running alembic migrations..."
alembic upgrade head

echo "[start_web] starting uvicorn on port ${PORT:-8000}..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --log-level info
