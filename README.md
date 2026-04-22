# baha — 巴哈姆特動畫瘋上片時間爬蟲

本專案從巴哈姆特動畫瘋（<https://ani.gamer.com.tw/>）抓取多部動畫的
「上片時間、片名、集數」，並寫入以 Docker Compose 啟動的 MariaDB 資料庫。
設計與規格追蹤於 `openspec/` 目錄，遵循 Spec-Driven Development（SDD）流程。

## 專案架構

```
baha/
├── README.md                 # 本檔
├── run.sh                    # 宿主機入口；啟動 MariaDB 並執行 python -m baha
├── requirements.txt          # Python 相依套件版本釘選
├── .env.example              # 環境變數範本（複製為 .env 使用）
├── docker/
│   ├── Dockerfile            # python:3.12-slim app image
│   ├── build.sh              # docker compose build 的包裝腳本
│   ├── docker-compose.yaml   # app + mariadb 編排
│   └── initdb/
│       └── 001_schema.sql    # MariaDB 首次啟動自動建立 anime_schedule 資料表
├── logs/                     # 執行 log（gitignore）
├── src/baha/
│   ├── __init__.py
│   ├── __main__.py           # 允許 python -m baha
│   ├── config.py             # 從環境變數建立 AppConfig
│   ├── logging_setup.py      # 同時輸出 stdout 與 logs/baha-YYYYMMDD.log
│   ├── fetcher.py            # HTTP 抓取（含指數退避重試）
│   ├── parser.py             # HTML 解析為 ScheduleCard
│   ├── time_utils.py         # 「週幾 + HH:MM」轉絕對 datetime
│   ├── storage.py            # MariaDB upsert 與連線重試
│   └── pipeline.py           # 組合 fetcher/parser/time_utils/storage 的 one-shot
├── tests/
│   ├── fixtures/animeList_sample.html
│   ├── test_parser.py
│   ├── test_time_utils.py
│   ├── test_fetcher.py
│   ├── test_storage.py       # 含 @pytest.mark.integration 標記的整合測試
│   └── test_pipeline.py
└── openspec/                 # Spec-driven development artifact
```

## 環境需求

* Docker 與 Docker Compose v2（`docker compose` 指令）。
* 宿主機可存取網路以連線 <https://ani.gamer.com.tw/>。
* 不需在宿主機安裝 Python；所有程式與測試皆於 container 內執行。

## 環境變數

複製 `.env.example` 為 `.env` 後依需求調整。`.env` 不會被納入版控。

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `DB_HOST` | 是 | `mariadb` | MariaDB 主機；使用 docker compose 時為服務名稱。 |
| `DB_PORT` | 是 | `3306` | MariaDB 連線埠。 |
| `DB_NAME` | 是 | `baha` | 資料庫名稱。 |
| `DB_USER` | 是 | `baha` | 連線使用者名稱。 |
| `DB_PASSWORD` | 是 | `changeme` | 連線密碼；缺失時啟動立即 exit。 |
| `DB_ROOT_PASSWORD` | 否 | `rootchangeme` | MariaDB container 初始化 root 密碼。 |
| `MARIADB_HOST_PORT` | 否 | `3307` | MariaDB 對宿主機暴露的 port；僅供宿主直連除錯使用，不影響 app 與 mariadb container 之間的連線。若宿主機已有其他 MariaDB/MySQL 佔用 3306，維持預設 3307 或改為其他空閒 port 即可。 |
| `LOG_LEVEL` | 否 | `INFO` | Python logging level，可選 `DEBUG`/`INFO`/`WARNING`/`ERROR`。 |

## 如何啟動（`./run.sh`）

1. `cp .env.example .env` 並修改密碼。
2. `./run.sh`。腳本會：
   1. 建立 `logs/` 目錄（若不存在）。
   2. 以 `docker compose -f docker/docker-compose.yaml up -d mariadb` 啟動資料庫。
   3. 輪詢 MariaDB 的 healthcheck，最多等待 30 秒。
   4. 以 `docker compose run --rm app python -m baha` 執行一次抓取。

log 會同時輸出至 stdout 與 `logs/baha-YYYYMMDD.log`。

> 預設 `MARIADB_HOST_PORT=3307`；若宿主機上有其他服務佔用該 port，請於
> `.env` 改為未被占用的 port（例如 `MARIADB_HOST_PORT=33070`）。app 與
> mariadb 之間為 compose 內部網路連線（`DB_HOST=mariadb`、`DB_PORT=3306`），
> 不受此 host 綁定影響。

首次建置 image 可先執行：

```bash
bash docker/build.sh
```

## 資料表 schema

`docker/initdb/001_schema.sql` 在 MariaDB 首次啟動時自動建立：

```sql
CREATE TABLE IF NOT EXISTS anime_schedule (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title      VARCHAR(255) NOT NULL,
  episode    VARCHAR(32)  NOT NULL,
  air_time   DATETIME     NOT NULL,
  source_url VARCHAR(512) NULL,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_title_episode (title, episode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

* `title + episode` 為業務唯一鍵；同一集若重抓會以 `ON DUPLICATE KEY UPDATE`
  的方式僅更新 `air_time`。
* `air_time` 以 Asia/Taipei 本地 naive datetime 儲存；連線會執行
  `SET time_zone='+08:00'`。

## 測試方法

全部單元測試（於 container 內執行，不需啟動 MariaDB）：

```bash
docker compose -f docker/docker-compose.yaml run --rm --no-deps app \
  pytest -m "not integration"
```

加上覆蓋率報告：

```bash
docker compose -f docker/docker-compose.yaml run --rm --no-deps app \
  pytest -m "not integration" --cov=baha --cov-report=term-missing
```

整合測試（需 MariaDB service 已啟動）：

```bash
docker compose -f docker/docker-compose.yaml up -d mariadb
docker compose -f docker/docker-compose.yaml run --rm app \
  pytest -m integration
```

## 已知限制

* **不跨週推算**：動畫瘋時刻表以「週幾 + HH:MM」表示，本工具一律以
  `fetched_at` 所在週解析為絕對時間，不會推算為上週或下週。跨週邊界
  （週日深夜 / 週一凌晨）可能造成時間語意偏差。
* **不處理付費章節**：僅解析公開時刻表，不處理登入後才可見的付費內容、
  番組詳細頁、播放連結與海報。
* **不內建排程**：本工具為 one-shot 執行；週期性抓取請由宿主機 cron
  或其他排程系統呼叫 `./run.sh`。
* **HTML 結構依賴**：parser 依 `.schedule-week .animate-theme-list
  .theme-list-block` 的結構抽取資料；動畫瘋改版時需更新 parser 與
  `tests/fixtures/animeList_sample.html`。
* **時區單一**：資料表與連線固定使用 Asia/Taipei 時區（`+08:00`）；
  若未來需支援多時區，需另開新 change。
