#!/usr/bin/env bash
# 容器啟動 dispatcher — 根據 SERVICE_TYPE env var 分流到 web / worker。
#
# Railway dashboard 各 service 設：
#   paint-web    → Variables → SERVICE_TYPE=web      （或不設，預設 web）
#   paint-worker → Variables → SERVICE_TYPE=worker
#
# 這樣兩個 service 共用同一個 Docker image + 同一個 CMD，
# 不需要 Railway 的 startCommand / Custom Start Command / RAILWAY_RUN_COMMAND 任一個。

set -euo pipefail

case "${SERVICE_TYPE:-web}" in
  web)
    echo "[start] SERVICE_TYPE=web → start_web.sh"
    exec bash scripts/start_web.sh
    ;;
  worker)
    echo "[start] SERVICE_TYPE=worker → start_worker.sh"
    exec bash scripts/start_worker.sh
    ;;
  *)
    echo "[start] ERROR: unknown SERVICE_TYPE='${SERVICE_TYPE}', expected web|worker" >&2
    exit 1
    ;;
esac
