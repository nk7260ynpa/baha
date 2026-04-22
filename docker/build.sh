#!/usr/bin/env bash
#
# 建置 baha app Docker image。
#
# 使用方式：於專案任意位置執行 `bash docker/build.sh`；腳本會切換至
# 本身所在目錄（docker/）後呼叫 `docker compose build`。
set -euo pipefail

cd "$(dirname "$0")"

docker compose build
