## Context

本變更為 baha 專案的第一個功能 change。目標是建立一個自動化的動畫上片時間抓取與儲存系統：

- **資料來源**：巴哈姆特動畫瘋 <https://ani.gamer.com.tw/>，主要參考新番時刻表（通常位於 `/animeList.php` 或首頁時刻表區塊）。時刻表每週更新，每集播出時間亦以「週幾 + HH:MM」顯示，而不是絕對日期時間。
- **現況**：專案目錄僅含 `README.md`、`.gitignore`、`openspec/` 與 `.claude/`，尚無任何原始碼、測試、Docker 檔案。
- **執行環境約束**：全域偏好要求 Python 程式與測試皆於 Docker container 內執行，且需包含 `docker/`、`logs/`、`run.sh`。
- **利害關係人**：本專案使用者（資料消費者）、Specialist（實作者）、Verifier（驗證者）。

## Goals / Non-Goals

**Goals:**

- 能以單一指令（`./run.sh`）完成：啟動 MariaDB、執行爬蟲一次、將多部動畫的上片資訊寫入資料庫。
- 資料表欄位包含「時間、片名、集數」三個核心欄位，並具備避免重複的唯一鍵設計。
- 抓取「多部」動畫（>= 2 筆），而非單一 id 的抓取。
- 解析、儲存、時間處理三大模組皆有單元測試覆蓋。
- 所有執行過程透過 `logging` 輸出至 `logs/`，可於 container 外查閱。

**Non-Goals:**

- 不建構 Web UI、API server、通知系統（留作後續 change）。
- 不實作排程（cron / systemd timer / Airflow）；本次僅提供 one-shot 執行，排程由使用者於宿主機決定。
- 不抓取播放連結、番劇海報、詳細介紹文字；僅抓「時間、片名、集數」。
- 不處理登入、付費章節；公開時刻表即足夠。
- 不負責歷史補抓；只抓「當下」時刻表顯示的內容。

## Decisions

### D1：資料來源頁面選擇 — 新番時刻表 HTML 解析

**選擇**：抓取 <https://ani.gamer.com.tw/animeList.php>（或首頁時刻表區塊）的 HTML，以 BeautifulSoup 解析 DOM。

**理由**：

- 新番時刻表列出「當週」所有動畫的週幾、時間、片名、集數，一次抓取即可取得多部動畫。
- 不需要登入、不需 JS 渲染（時刻表為 server-side render）。
- HTML 結構公開、穩定度高於爬詳細頁。

**否決的替代方案**：

- 對每部動畫的詳細頁 `/animeVideo.php?sn=<id>` 逐一爬取：需先取得 sn 清單，且每部動畫需多次請求，對伺服器負擔與抓取成本較高。
- 抓取逆向分析後的 JSON API：未公開，違反條款風險高，且格式變動難以追蹤。
- 使用 headless browser (Playwright)：時刻表不需 JS，導入瀏覽器徒增 container 體積與不穩定性。

### D2：資料庫選型與 schema — MariaDB 單表 `anime_schedule`

**選擇**：以 Docker Compose 啟動 `mariadb:11` 官方 image。資料表如下：

```sql
CREATE TABLE anime_schedule (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title        VARCHAR(255) NOT NULL,
  episode      VARCHAR(32)  NOT NULL,
  air_time     DATETIME     NOT NULL,
  source_url   VARCHAR(512) NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_title_episode (title, episode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**理由**：

- 使用者需求明確指定 MariaDB。
- 「片名 + 集數」為天然業務唯一鍵；同一集若重抓只會 upsert，不會產生重覆列。
- `air_time` 使用 `DATETIME`（Asia/Taipei 時區轉 UTC naive 或直接存 local，見 D3）保留可排序、可索引的時間語意。
- `episode` 用 `VARCHAR(32)` 而非 INT，因實務上有「第 01 集」「特別篇」「OVA」等非整數集數表示。
- `source_url` 為可選欄位，方便未來除錯與追溯，不屬核心需求欄位。
- `created_at` / `updated_at` 為稽核欄位，與核心三欄位並存，不違反「欄位包含：時間、片名、集數」的需求（該需求是最小集合，不禁止其他欄位）。

**否決的替代方案**：

- 使用 MySQL：與 MariaDB 語意接近，但需求明確指定 MariaDB。
- 使用 SQLite：不符需求，也不需要 Docker。
- `episode` 用 `SMALLINT`：無法表示特別篇、雙數字編號（如 1-2 合併集）。
- 以 `(title, episode, air_time)` 為唯一鍵：若動畫瘋調整播出時間，同一集會被視為新紀錄，無法去重。

### D3：時間解析策略 — 時刻表「週幾 + HH:MM」轉絕對時間

**選擇**：

- 抓取執行時記錄「抓取時刻」`fetched_at`（Asia/Taipei 時區）。
- 將時刻表中的「週幾 + HH:MM」以 `fetched_at` 所在週為基準，解析為該週對應週幾的 `DATETIME`（存為 Asia/Taipei 本地時間，資料庫設 `time_zone = '+08:00'`）。
- 若時刻表顯示的時間 < `fetched_at` 且差距 > 12 小時，視為「本週較早時段（已播）」，仍以本週該週幾解析。
- 不做跨週推算；當週無法推斷的資料直接略過並記 log。

**理由**：動畫瘋時刻表以「週幾」為單位，需求要求「時間」欄位需可排序可查詢，必須轉絕對時間點。

**否決的替代方案**：

- 以字串儲存「週三 22:00」：無法排序、無法用 `WHERE air_time > NOW()` 查詢。
- 一律轉 UTC：team 在台灣作業，直接存台灣時區較直觀；若未來需多時區，可在應用層再轉。

### D4：網頁專案骨架 — 遵循全域 CLAUDE.md

**選擇**：

```
baha/
├── README.md
├── run.sh                        # 宿主機入口；內部呼叫 docker compose
├── docker/
│   ├── build.sh                  # docker compose build
│   ├── Dockerfile                # Python 3.12-slim + 依賴
│   ├── docker-compose.yaml       # app + mariadb service
│   └── initdb/
│       └── 001_schema.sql        # 首次啟動自動匯入
├── logs/                         # .gitignore；由 run.sh 掛載進 container
├── src/
│   └── baha/
│       ├── __init__.py
│       ├── __main__.py           # 允許 python -m baha
│       ├── config.py             # 讀取環境變數
│       ├── logging_setup.py      # logging 設定
│       ├── fetcher.py            # HTTP 抓取
│       ├── parser.py             # HTML → domain object
│       ├── time_utils.py         # 週幾+HH:MM → DATETIME
│       ├── storage.py            # MariaDB upsert
│       └── pipeline.py           # 組合以上模組的 one-shot 任務
├── tests/
│   ├── __init__.py
│   ├── fixtures/                 # 離線 HTML 樣本
│   │   └── animeList_sample.html
│   ├── test_parser.py
│   ├── test_time_utils.py
│   └── test_storage.py           # 使用 docker compose 的 mariadb 或 pytest 跳過標記
├── requirements.txt
└── openspec/                     # 已存在
```

**理由**：對齊全域偏好；`src/baha/` 模組化讓單元測試易於 mock；`docker/initdb/` 是 MariaDB 官方 image 的約定資料夾，可於容器首次啟動自動載入 schema。

### D5：`run.sh` 的職責邊界

**選擇**：`run.sh` 僅做三件事：

1. 確保 `logs/` 存在。
2. 呼叫 `docker compose -f docker/docker-compose.yaml up -d mariadb` 啟動資料庫。
3. 呼叫 `docker compose -f docker/docker-compose.yaml run --rm app python -m baha`（掛載 `logs/` 到 container 內 `/app/logs`）。

**理由**：讓使用者不必記 docker compose 指令；同時保留「可直接用 docker compose 進行 pytest」的彈性（`docker compose run --rm app pytest` 即可）。

### D6：測試策略

**選擇**：

- `test_parser.py`：使用存於 `tests/fixtures/animeList_sample.html` 的離線 HTML 檔，完全不打網路。
- `test_time_utils.py`：純函式、以固定「now」參數注入。
- `test_storage.py`：標註 `@pytest.mark.integration`，在 `docker compose` 的 mariadb service 可連線時執行；CI/單元測試預設 `pytest -m "not integration"` 即可跳過。
- 涵蓋率目標：parser / time_utils 行覆蓋率 >= 80%；storage 以整合測試確保 upsert 行為正確。

**理由**：單元測試不應打外網，否則會被動畫瘋改版或網路狀況拖累。

### D7：抓取頻率與禮貌策略

**選擇**：

- 單次執行只對 `/animeList.php` 發一次 GET。
- User-Agent 設為識別度高的字串（如 `baha-schedule-scraper/0.1 (+contact)`）。
- 若回應非 2xx，retry 最多 3 次，每次間隔 2 秒（指數退避）。
- 執行週期交由使用者於宿主機決定（crontab 等），本 change 不內建排程。

**理由**：避免對動畫瘋造成負擔；同時讓錯誤可以恢復。

## Risks / Trade-offs

- **[Risk]** 動畫瘋 HTML 結構改版導致 parser 失效 → **Mitigation**：parser 模組化 + fixture 測試 + 失敗時 log 原始 HTML 前 2 KB 以便除錯；改版時只需更新 parser 與 fixture。
- **[Risk]** 「週幾 + HH:MM」跨週推算誤判（例如週日 23:50 抓到下週一 00:10 的集數） → **Mitigation**：D3 中明定「不跨週推算」，遇不確定即略過並記 WARN log；後續 change 可引入 `(fetched_at, day_of_week, hh_mm)` 原始欄位保留推算線索。
- **[Risk]** 對 ani.gamer.com.tw 過度抓取違反條款 → **Mitigation**：D7 的頻率控制 + User-Agent 識別 + 不抓付費/詳細頁；使用者於宿主機排程時以 1 天 1 次為建議頻率。
- **[Risk]** MariaDB container 啟動未就緒時 app 即連線失敗 → **Mitigation**：`pipeline.py` 連線以重試 + 短暫等待處理；docker-compose 使用 `depends_on` + healthcheck。
- **[Trade-off]** 不使用 headless browser，若未來時刻表改為 client-render，需要改寫 fetcher → 接受此風險，屆時再開新 change。
- **[Trade-off]** 不內建排程，首次使用者需自行設定 crontab → 接受；避免與既有排程系統衝突。

## Migration Plan

- **部署**：首次部署只需 `./run.sh`；MariaDB 首次啟動會執行 `docker/initdb/001_schema.sql` 建立資料表。
- **回滾**：
  - 若出現資料汙染：`docker compose down -v` 會清除 volume，下次啟動重新建表；合法性由業務方決定。
  - 若 parser 改壞：回滾 feature branch 的 merge commit (`git revert -m 1 <merge-sha>`)；由於資料表已持久化，回滾不影響已落地資料。
- **資料遷移**：本 change 為首次建表，無既有資料遷移議題。

## Open Questions

- Q1：MariaDB 帳號密碼的管理方式，採環境變數 + `.env.example` 即可，或需導入 secret manager？
  - **目前立場**：先用 `.env.example`（納入版控）+ `.env`（gitignore），簡單可行。若未來部署到雲端再升級。
- Q2：是否需要保留原始 HTML 快照以便未來 schema 調整時回放？
  - **目前立場**：不保留（out of scope）；若有需要再開 change。
- Q3：`air_time` 是否需保存時區資訊？
  - **目前立場**：本 change 將 MariaDB `time_zone` 設為 `+08:00`，`DATETIME` 不帶時區但語意上即台灣時間；若未來需要多時區，轉為 `TIMESTAMP` 或新增 `air_time_utc` 欄位。
