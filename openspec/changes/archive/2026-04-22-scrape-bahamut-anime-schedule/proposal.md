## Why

目前團隊缺少對巴哈姆特動畫瘋（<https://ani.gamer.com.tw/>）新番上片時間的結構化追蹤管道，需要人工瀏覽網頁才能確認當季多部動畫的上片時間與集數。本變更將導入自動化抓取與本地資料庫儲存，為後續通知、分析、排程等下游功能建立資料基礎。

## What Changes

- 新增以 Docker Compose 啟動的 MariaDB 服務，提供單一動畫上片紀錄資料表。
- 新增 Python 爬蟲程式（於 Docker container 內執行），週期性抓取動畫瘋新番時刻表中「多部」動畫的上片時間、片名、集數。
- 爬蟲對每筆紀錄以「片名 + 集數」為唯一鍵進行 upsert，避免重覆。
- 新增 `docker/`（含 `build.sh`、`Dockerfile`、`docker-compose.yaml`）、`logs/` 目錄與 `run.sh` 啟動入口。
- 新增單元測試（於 Docker container 內以 pytest 執行）覆蓋解析、資料存取、時間處理三個主要模組。
- 以 `logging` 套件輸出結構化 log 至 `logs/`。
- 更新 `README.md`，記錄啟動方式、資料表 schema、環境變數。

## Capabilities

### New Capabilities

- `anime-schedule-scraper`: 從動畫瘋新番時刻表擷取多部動畫的上片時間、片名、集數，並以結構化欄位輸出。
- `anime-schedule-storage`: 於 MariaDB 持久化動畫上片紀錄，提供去重的 upsert 寫入與可被下游查詢的資料表。
- `scraper-runtime`: 以 Docker Compose 編排爬蟲與 MariaDB，提供 `run.sh` 一鍵啟動與 log 持久化的執行環境。

### Modified Capabilities

<!-- 無：此為全新專案的首個 change，無既有 spec 被修改。 -->

## Impact

- **新增程式碼**：`src/`（爬蟲、資料存取、entrypoint）、`tests/`（pytest 單元測試）。
- **新增基礎設施**：`docker/Dockerfile`、`docker/build.sh`、`docker/docker-compose.yaml`、`logs/`、`run.sh`。
- **新增資料庫**：MariaDB service 與初始化 SQL（建立 `anime_schedule` 資料表）。
- **外部相依**：Python requests / BeautifulSoup（或同等 HTML 解析套件）、PyMySQL 或 mysqlclient、pytest。
- **外部系統**：對 `https://ani.gamer.com.tw/` 發出 HTTP 請求；需遵守合理的抓取頻率。
- **文件**：`README.md` 更新專案架構、資料表欄位、啟動方式說明。
