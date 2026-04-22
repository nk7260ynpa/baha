#!/usr/bin/env bash
#
# baha 一鍵啟動腳本。
#
# 執行流程：
#   1. 確保專案 logs/ 目錄存在（由 docker-compose 掛載為 /app/logs）。
#   2. 透過 docker compose 啟動 mariadb service（背景執行）。
#   3. 輪詢 mariadb container 的 healthcheck，最多等待 30 秒。
#   4. 以 `docker compose run --rm app` 執行 `python -m baha`。
#
# 使用方式：於專案根目錄執行 `./run.sh`。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker/docker-compose.yaml"

mkdir -p "${SCRIPT_DIR}/logs"

echo "[run.sh] 啟動 mariadb service..."
docker compose -f "${COMPOSE_FILE}" up -d mariadb

echo "[run.sh] 等待 mariadb healthcheck..."
CONTAINER_NAME="baha-mariadb"
MAX_WAIT_SECONDS=30
elapsed=0
while true; do
  status="$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "starting")"
  if [[ "${status}" == "healthy" ]]; then
    echo "[run.sh] mariadb 已 healthy (等待 ${elapsed}s)"
    break
  fi
  if (( elapsed >= MAX_WAIT_SECONDS )); then
    echo "[run.sh] 等待 mariadb healthy 超時（${MAX_WAIT_SECONDS}s），狀態=${status}" >&2
    exit 1
  fi
  sleep 2
  elapsed=$(( elapsed + 2 ))
done

echo "[run.sh] 執行爬蟲 one-shot..."
docker compose -f "${COMPOSE_FILE}" run --rm app python -m baha
