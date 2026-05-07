#!/usr/bin/env bash
# backend-web entrypoint — Railway 部署用
#
# 流程：
#   1. python scripts/init_db.py
#      → Base.metadata.create_all（建 schema，含 alembic 漏掉的 production_jobs）
#      + alembic stamp head（記錄 schema version）
#      idempotent：DB 已有 schema 時不會重建
#   2. 啟動 uvicorn（Railway 會給 PORT env var）
#
# 註：暫時不跑 alembic upgrade head — alembic migrations 內部缺 production_jobs
# create_table，會在 product_variants FK 處炸掉。create_all 從 ORM models 一次建完整。
# TODO: 補 alembic migration 後改回 alembic upgrade head。

set -euo pipefail

cd /app

echo "[start_web] initializing schema..."
python scripts/init_db.py

echo "[start_web] initializing admin user (idempotent)..."
python scripts/init_admin.py

echo "[start_web] starting uvicorn on port ${PORT:-8000}..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips='*'
