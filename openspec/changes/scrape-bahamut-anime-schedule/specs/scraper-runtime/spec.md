## ADDED Requirements

### Requirement: 以 Docker Compose 編排 app 與 MariaDB 服務

系統 SHALL 於 `docker/docker-compose.yaml` 定義兩個 service：

- `mariadb`：基於 `mariadb:11` image，使用 named volume 持久化資料，掛載 `./initdb` 為 `/docker-entrypoint-initdb.d`。
- `app`：基於 `docker/Dockerfile` 建置的 Python 3.12-slim image，包含本專案原始碼與依賴；`depends_on` 設為 `mariadb`（含 healthcheck 條件）。

兩個 service SHALL 在同一 Docker network，`app` 透過服務名稱 `mariadb` 連線。

#### Scenario: 啟動 compose 後 MariaDB 通過 healthcheck

- **WHEN** 執行 `docker compose -f docker/docker-compose.yaml up -d mariadb`
- **THEN** 30 秒內 `docker inspect --format='{{.State.Health.Status}}' <mariadb-container>` SHALL 回傳 `healthy`

#### Scenario: app service 可連線 mariadb

- **GIVEN** `mariadb` service 已 healthy
- **WHEN** 執行 `docker compose -f docker/docker-compose.yaml run --rm app python -c "import socket; socket.create_connection(('mariadb', 3306), timeout=5)"`
- **THEN** 指令 exit code SHALL 為 0

### Requirement: 提供 `run.sh` 作為宿主機入口

系統 SHALL 於專案根目錄提供可執行的 `run.sh`，單次執行 SHALL 完成以下動作：

1. 確保 `logs/` 目錄存在。
2. 啟動 `mariadb` service 並等待其 healthy。
3. 以 `docker compose run --rm` 執行 `app` service 的 `python -m baha`，並掛載 `logs/` 為 container 的 `/app/logs`。

`run.sh` SHALL 以 `set -euo pipefail` 啟動，失敗時以非 0 exit code 結束。

#### Scenario: 首次執行成功完成一輪抓取

- **GIVEN** Docker daemon 可用、網路可連 `ani.gamer.com.tw`
- **WHEN** 於專案根目錄執行 `./run.sh`
- **THEN** MariaDB container SHALL 啟動並 healthy
- **AND** `anime_schedule` 資料表 SHALL 至少有 2 筆資料
- **AND** `logs/` 下 SHALL 產生當次執行的 log 檔（檔名含日期）

#### Scenario: MariaDB 啟動失敗時不執行 app

- **WHEN** `mariadb` service 因 port 衝突無法啟動
- **THEN** `run.sh` SHALL 以非 0 exit code 結束
- **AND** 不嘗試呼叫 `docker compose run app`

### Requirement: 日誌輸出與持久化

系統 SHALL 使用 Python `logging` 套件輸出 log，同時輸出至 stdout 與 `/app/logs/baha-YYYYMMDD.log`；log level 預設為 `INFO`，可由環境變數 `LOG_LEVEL` 調整。Log 格式 SHALL 至少包含時間戳、等級、模組名、訊息四個欄位。

#### Scenario: 預設 INFO 等級輸出

- **WHEN** 未設定 `LOG_LEVEL` 即執行 `./run.sh`
- **THEN** stdout SHALL 含 INFO 等級以上的 log
- **AND** `logs/baha-YYYYMMDD.log`（以當天日期命名）SHALL 同步寫入相同內容

#### Scenario: DEBUG 等級覆蓋

- **WHEN** 設定 `LOG_LEVEL=DEBUG` 執行
- **THEN** stdout 與 log 檔 SHALL 含 DEBUG 等級訊息
- **AND** DEBUG 訊息中 SHALL 包含單次抓取的 HTTP 狀態碼與回應大小

#### Scenario: log 檔位於宿主機可讀取

- **GIVEN** `run.sh` 完成一次執行
- **WHEN** 於宿主機檢視 `logs/` 目錄
- **THEN** 當次 log 檔 SHALL 存在並可讀
- **AND** 檔案大小 > 0 bytes

### Requirement: 提供可重建的 Docker image

系統 SHALL 於 `docker/Dockerfile` 定義 app image，並於 `docker/build.sh` 提供一鍵建置指令，可於專案根或 `docker/` 目錄執行。

#### Scenario: 執行 build.sh 成功建置

- **WHEN** 執行 `bash docker/build.sh`
- **THEN** 指令 exit code SHALL 為 0
- **AND** `docker images` 中 SHALL 有對應的 app image

#### Scenario: Dockerfile 指定 Python 3.12

- **WHEN** 檢視 `docker/Dockerfile` 的 FROM 指令
- **THEN** base image SHALL 為 `python:3.12-slim` 或同等官方 3.12 系列 slim 變體

### Requirement: 時間工具可將「週幾 + HH:MM」轉為絕對 DATETIME

系統 SHALL 提供 `time_utils.to_air_datetime(weekday: int, hhmm: str, now: datetime) -> datetime` 函式，依 D3 規則將時刻表顯示的相對時間轉換為 Asia/Taipei 本地 naive `datetime`。

#### Scenario: 同週未來時間

- **GIVEN** `now = 2025-04-22 10:00`（週二）
- **WHEN** 呼叫 `to_air_datetime(weekday=3, hhmm="22:00", now=now)`（週四 22:00）
- **THEN** 回傳 `2025-04-24 22:00`

#### Scenario: 同週已過時間（差距 > 12 小時視為本週已播）

- **GIVEN** `now = 2025-04-22 20:00`（週二）
- **WHEN** 呼叫 `to_air_datetime(weekday=0, hhmm="22:00", now=now)`（週一 22:00）
- **THEN** 回傳 `2025-04-21 22:00`（上一個週一，即本週週一）

#### Scenario: 差距 <= 12 小時亦視為本週該日

- **GIVEN** `now = 2025-04-22 22:30`（週二）
- **WHEN** 呼叫 `to_air_datetime(weekday=1, hhmm="22:00", now=now)`（週二 22:00，剛過 30 分鐘）
- **THEN** 回傳 `2025-04-22 22:00`

#### Scenario: 非法 hhmm 格式

- **WHEN** 呼叫 `to_air_datetime(weekday=1, hhmm="25:00", now=now)`
- **THEN** 系統 SHALL 拋出 `ValueError`
- **AND** 不回傳任何 datetime
