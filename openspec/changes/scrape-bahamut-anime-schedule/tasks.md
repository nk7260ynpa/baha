## 1. 專案骨架與相依宣告

- [x] 1.1 建立 `requirements.txt`，列出 `requests`、`beautifulsoup4`、`lxml`、`PyMySQL`（或 `mysqlclient`，擇一）、`pytest`、`pytest-cov` 版本釘選。檔案範圍：`requirements.txt`。驗收：`pip install -r requirements.txt` 於 Docker build 內成功。
- [x] 1.2 建立 `src/baha/__init__.py`、`src/baha/__main__.py` 空殼（`__main__.py` 僅呼叫 `pipeline.main()`）。檔案範圍：`src/baha/__init__.py`、`src/baha/__main__.py`。驗收：`python -c "import baha"` 於 container 內不報錯。
- [x] 1.3 在 `.gitignore` 新增 `logs/`、`.env`、`__pycache__/`、`.pytest_cache/`、`*.pyc`、`.coverage`。檔案範圍：`.gitignore`。驗收：`git status` 不再列出這些檔案。

## 2. Docker 與執行入口

- [x] 2.1 撰寫 `docker/Dockerfile`：`FROM python:3.12-slim`，工作目錄 `/app`，先 `COPY requirements.txt` 再安裝，最後 `COPY src/ ./src/`，`ENV PYTHONPATH=/app/src`、`CMD ["python", "-m", "baha"]`。檔案範圍：`docker/Dockerfile`。驗收：`scraper-runtime` spec 中「Dockerfile 指定 Python 3.12」scenario 成立。
- [x] 2.2 撰寫 `docker/docker-compose.yaml`：定義 `mariadb`（含 healthcheck、volume、initdb 掛載）與 `app`（build context 指向專案根 `..`，envfile `../.env`，掛載 `../logs:/app/logs`）。檔案範圍：`docker/docker-compose.yaml`。驗收：`anime-schedule-storage` spec 與 `scraper-runtime` spec 中 compose 相關 scenario 成立。
- [x] 2.3 撰寫 `docker/build.sh`：`#!/usr/bin/env bash`、`set -euo pipefail`、`cd "$(dirname "$0")"`、`docker compose build`。加入執行權限。檔案範圍：`docker/build.sh`。驗收：`scraper-runtime` spec 中「執行 build.sh 成功建置」scenario 成立。
- [x] 2.4 撰寫 `docker/initdb/001_schema.sql`：以 `CREATE TABLE IF NOT EXISTS anime_schedule (...)` 建立表與 unique key，字元集 utf8mb4。檔案範圍：`docker/initdb/001_schema.sql`。驗收：`anime-schedule-storage` spec 中建表 scenario 成立。
- [x] 2.5 撰寫 `run.sh`：`set -euo pipefail`；`mkdir -p logs`；`docker compose -f docker/docker-compose.yaml up -d mariadb`；等待 healthy（以 `docker inspect` 輪詢，最多 30 秒）；`docker compose -f docker/docker-compose.yaml run --rm app python -m baha`。加入執行權限。檔案範圍：`run.sh`。驗收：`scraper-runtime` spec 中 `run.sh` 相關 scenario 成立。
- [x] 2.6 提供 `.env.example`（納入版控），列出 `DB_HOST=mariadb`、`DB_PORT=3306`、`DB_NAME=baha`、`DB_USER=baha`、`DB_PASSWORD=changeme`、`LOG_LEVEL=INFO`。檔案範圍：`.env.example`。驗收：檔案存在且不包含真實密碼。

## 3. Logging 與 Config

- [x] 3.1 實作 `src/baha/config.py`：讀取環境變數並提供 `AppConfig` dataclass（含 DB_* 與 LOG_LEVEL）；未設定必要欄位時拋 `ConfigError`。檔案範圍：`src/baha/config.py`。驗收：`anime-schedule-storage` spec 「環境變數缺失時拒絕啟動」scenario。
- [x] 3.2 實作 `src/baha/logging_setup.py`：同時輸出 stdout 與 `/app/logs/baha-YYYYMMDD.log`，格式 `%(asctime)s %(levelname)s %(name)s %(message)s`，level 由 `AppConfig.log_level` 決定。檔案範圍：`src/baha/logging_setup.py`。驗收：`scraper-runtime` spec 日誌相關三個 scenario 成立。

## 4. 時間工具（純函式優先）

- [x] 4.1 實作 `src/baha/time_utils.py`：`to_air_datetime(weekday: int, hhmm: str, now: datetime) -> datetime`，依 D3 規則推算；`weekday` 0=週一 … 6=週日；非法輸入拋 `ValueError`。檔案範圍：`src/baha/time_utils.py`。驗收：`scraper-runtime` spec 中 `to_air_datetime` 四個 scenario 全部通過。
- [x] 4.2 撰寫 `tests/test_time_utils.py`：涵蓋同週未來、同週已過（差距 > 12 h）、同週剛過（差距 <= 12 h）、非法格式四個 scenario。檔案範圍：`tests/test_time_utils.py`、`tests/__init__.py`。驗收：`pytest tests/test_time_utils.py -v` 全綠。

## 5. HTML 解析模組

- [ ] 5.1 蒐集 `tests/fixtures/animeList_sample.html`：離線保存一份動畫瘋時刻表 HTML（含 >= 10 部動畫）；建議以瀏覽器另存 HTML 後放入。檔案範圍：`tests/fixtures/animeList_sample.html`。驗收：檔案大小 > 20 KB 且 `grep -c "animate-theme-list" fixtures` 命中多次（實際 selector 依 parser 設計）。**[2026-04-22 需依新 DOM 重做 — 由 Section 10.1 取代本項；原合成 fixture 與真實頁面結構不符]**
- [ ] 5.2 實作 `src/baha/parser.py`：提供 `parse_schedule(html: str) -> list[ScheduleCard]`，其中 `ScheduleCard` 含 `title: str`、`episode: str`、`weekday: int`、`hhmm: str`；結構不完整即略過並 WARN。檔案範圍：`src/baha/parser.py`。驗收：`anime-schedule-scraper` spec 中「正常解析」「清洗」「干擾區塊」「解析失敗」scenario 全部通過。**[2026-04-22 需依新 DOM 重做 — 由 Section 10.2 取代本項；原假設之 `.schedule-week` / `.animate-theme-list` / `.theme-list-block` 階層與真實首頁結構不符]**
- [ ] 5.3 撰寫 `tests/test_parser.py`：以 5.1 的 fixture 驗證至少回傳 10 筆；額外以手寫迷你 HTML 驗證「干擾略過」「片名清洗」「空 HTML 回傳空清單」。檔案範圍：`tests/test_parser.py`。驗收：`pytest tests/test_parser.py -v` 全綠，覆蓋率 >= 80%。**[2026-04-22 需依新 DOM 重做 — 由 Section 10.4 取代本項；期望值需依新 fixture 與新 parser 重算]**

## 6. 抓取模組（含重試）

- [ ] 6.1 實作 `src/baha/fetcher.py`：`fetch_schedule_html(url: str, session: Optional[Session]=None) -> str`；User-Agent 含 `baha-schedule-scraper`；失敗時指數退避重試（2/4/8 秒，最多 4 次），最終失敗拋 `FetchError`。檔案範圍：`src/baha/fetcher.py`。驗收：`anime-schedule-scraper` spec 「正常抓取」「非 2xx 重試」「網路錯誤重試」「User-Agent」四個 scenario 成立（以 mock `requests.Session` 於單元測試驗證）。**[2026-04-22 需依新 DOM 重做 — 由 Section 10.3 取代 `DEFAULT_URL` 設定；重試/UA 邏輯本身可保留]**
- [x] 6.2 撰寫 `tests/test_fetcher.py`：以 `unittest.mock` 模擬 `requests.Session`，驗證重試次數、退避時間（以 patch `time.sleep` 記錄呼叫）、User-Agent header。檔案範圍：`tests/test_fetcher.py`。驗收：`pytest tests/test_fetcher.py -v` 全綠。

## 7. Storage 模組（含 upsert）

- [x] 7.1 實作 `src/baha/storage.py`：`class Storage`，`__init__(config)` 建立連線並設 `time_zone='+08:00'`；`upsert_records(records) -> UpsertStats`；使用 `INSERT ... ON DUPLICATE KEY UPDATE air_time=VALUES(air_time)` 並依 `ROW_COUNT()` 區分 inserted/updated/unchanged。檔案範圍：`src/baha/storage.py`。驗收：`anime-schedule-storage` spec 全部 scenario 成立。
- [x] 7.2 撰寫 `tests/test_storage.py`：
  - 單元測試以 mock `pymysql.connect` 驗證「空清單不發 SQL」「缺少環境變數拋 `ConfigError`」。
  - 整合測試（`@pytest.mark.integration`）連到 compose 的 mariadb，驗證 insert / update / unchanged 計數與 `SET time_zone='+08:00'`。
  檔案範圍：`tests/test_storage.py`。驗收：`pytest -m "not integration"` 與 `pytest -m integration`（有 mariadb 時）皆綠。

## 8. Pipeline 組裝與入口

- [x] 8.1 實作 `src/baha/pipeline.py`：`run_once(fetched_at: datetime)` 呼叫 fetcher → parser → time_utils → 組出 `AnimeScheduleRecord` 清單。`main()` 讀 config、設 log、呼叫 `run_once(datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None))` 並交給 `Storage.upsert_records`，最後以 INFO log 輸出 `UpsertStats`。檔案範圍：`src/baha/pipeline.py`。驗收：`anime-schedule-scraper` spec 中 pipeline 兩個 scenario 成立。
- [ ] 8.2 撰寫 `tests/test_pipeline.py`：以 mock fetcher + 使用 fixture HTML + mock storage，驗證「部分解析錯誤不中斷」「紀錄筆數 < 2 時拋 `ScrapeEmptyError`」。檔案範圍：`tests/test_pipeline.py`。驗收：`pytest tests/test_pipeline.py -v` 全綠。**[2026-04-22 需依新 DOM 重做 — 由 Section 10.5 驗證；使用新 fixture 後期望筆數／分佈需重算，必要時微調 pipeline 測試 seam]**

## 9. 文件與收尾

- [x] 9.1 更新 `README.md`：加入「環境需求」「如何啟動（`./run.sh`）」「資料表 schema」「環境變數清單」「測試方法（`docker compose run --rm app pytest`）」「已知限制（不跨週推算、不處理付費章節）」段落。檔案範圍：`README.md`。驗收：文件內容涵蓋以上六段且為繁體中文。
- [x] 9.2 執行完整測試：於 container 內 `pytest -m "not integration" --cov=baha --cov-report=term-missing`，確保 parser、time_utils 覆蓋率 >= 80%。檔案範圍：無（僅執行）。驗收：log 顯示覆蓋率達標。
- [ ] 9.3 手動冒煙：執行 `./run.sh`，確認 MariaDB 中 `SELECT COUNT(*) FROM anime_schedule` >= 2，且 `logs/baha-YYYYMMDD.log` 存在。檔案範圍：無。驗收：以上兩條件成立。

## 10. 依真實 DOM 重做解析層（2026-04-22 修訂）

> 背景：冒煙測試確認原 `/animeList.php` 實為 A–Z 全動畫清單頁，真正的週期表位於首頁 `/` 之 `.programlist-wrap`。
> Specialist 須依 design.md 的 D1 / D8 與 spec.md 的新 Requirement 2 全面重做下列工作。原 5.1 / 5.2 / 5.3 / 6.1（`DEFAULT_URL` 部分）/ 8.2 已回退為未完成，Specialist 應視 Section 10 為其取代版，逐項完成後再回頭勾選。

- [x] 10.1 以宿主偵察樣本 `/tmp/ani_root.html`（360 KB，Specialist 可於宿主讀取）為來源，擷取 `.programlist-wrap` 整段 HTML 作為新 fixture，清理下列內容後保存為 `tests/fixtures/animeList_sample.html`：
  - 移除 `<script>`、`<style>`、廣告 `<iframe>` 與追蹤相關 `<img>`（Google Analytics / FB Pixel 等）。
  - 清除任何 session token、cookie 值、CSRF token、會員 id、使用者暱稱、追蹤參數（例：URL query 中的 `uid`、`token`、`sid`、`_ga`、`fbclid` 等），必要時將 `<a href>` 改為 `animeVideo.php?sn=<僅保留 sn 數字>`。
  - 確認保留 7 個 `.day-list`（週一至週日）、總計 >= 10 張 `a.text-anime-info`；若樣本當日資料不足 10 張，可保留全部可見卡片並於檔頭註記實際筆數。
  - 檔頭加入 HTML comment：`<!-- source: https://ani.gamer.com.tw/ 擷取於 2026-04-22；已清理 script/style/ads/tracking token -->`。

  檔案範圍：`tests/fixtures/animeList_sample.html`。驗收：
  - 檔案於 repo 內不含任何 token/session id/個資。
  - `grep -c 'class="day-list"' tests/fixtures/animeList_sample.html` >= 7。
  - `grep -c 'class="text-anime-info"' tests/fixtures/animeList_sample.html` >= 10。
  - 檔頭註解存在且指出來源與清理動作。

- [x] 10.2 重寫 `src/baha/parser.py`，完全對齊 spec.md Requirement 2 的新 DOM 結構：
  - 入口：定位 `soup.select_one(".programlist-wrap")`，找不到時以 ERROR log HTML 前 2048 字元並回傳 `[]`。
  - 迭代 `.programlist-wrap .day-list`，對每個 `.day-list`：
    - 讀 `h3.day-title` 文字，依 `{"週一":0, "週二":1, "週三":2, "週四":3, "週五":4, "週六":5, "週日":6}` 映射；未命中 → WARN（含原始文字）並略過該 `.day-list`。
    - 迭代其內 `a.text-anime-info`，各自擷取 `span.text-anime-time`、`p.text-anime-name`、`p.text-anime-number`。
  - HH:MM 驗證：正則 `^\d{2}:\d{2}$`，不合法 → WARN 並略過該卡片。
  - 片名清洗：`strip()`，不做全半形轉換。
  - 集數清洗：若符合 `^第\s*(\S+)\s*集$` 取第 1 群組並去除內部空白；否則保留 `strip()` 後原字串（覆蓋「特別篇」「OVA」等）。
  - 結構不完整（缺任一子節點）→ WARN 輸出前 200 字原始片段並略過該卡片，不影響同 `.day-list` 其他卡片。
  - `ScheduleCard` 維持 `title: str`、`episode: str`、`weekday: int`、`hhmm: str` 四欄位介面，與 `time_utils` 上下游合約不變（見 D3「上下游假設」）。

  檔案範圍：`src/baha/parser.py`。驗收：
  - `anime-schedule-scraper` spec Requirement 2 的全部 5 個 scenario 通過。
  - 不修改範圍外檔案。

- [x] 10.3 更新 `src/baha/fetcher.py` 的 `DEFAULT_URL` 由 `https://ani.gamer.com.tw/animeList.php` 改為 `https://ani.gamer.com.tw/`；其餘重試、退避、User-Agent、錯誤型別維持不變。
  檔案範圍：`src/baha/fetcher.py`。驗收：
  - 常數值為 `https://ani.gamer.com.tw/`（結尾含斜線）。
  - `tests/test_fetcher.py` 既有 scenario（正常抓取、非 2xx 重試、網路錯誤重試、User-Agent）維持全綠；若測試寫死舊 URL，必須同步更新測試之期待值（檔案範圍加入 `tests/test_fetcher.py`）。

- [ ] 10.4 重寫 `tests/test_parser.py`，期望值完全依 10.1 新 fixture 與 10.2 新 parser 重算：
  - 以新 fixture 驗證：總筆數 >= 10；每個 weekday 值（0–6）至少出現一次；所有 `hhmm` 符合 `^\d{2}:\d{2}$`；所有 `title`、`episode` 為非空字串。
  - 以手寫迷你 HTML 驗證：
    - 不合法 `day-title`（例：「本週特別企劃」）整段 `.day-list` 被略過並有 WARN。
    - `span.text-anime-time` 為「待定」或「25:00」時僅該卡片被略過。
    - 缺 `p.text-anime-name` 的卡片被略過，同 `.day-list` 內其他卡片仍被回傳。
    - 片名前後空白被 `strip()`；「第 01 集」→ `"01"`、「第 12 集」→ `"12"`、「特別篇」→ `"特別篇"`。
    - 空字串輸入與不含 `.programlist-wrap` 的 HTML 皆回傳 `[]` 且記 ERROR log。
  - 覆蓋率：parser 行覆蓋率 >= 80%（可用 `pytest --cov=baha.parser`）。

  檔案範圍：`tests/test_parser.py`。驗收：`docker compose run --rm app pytest tests/test_parser.py -v` 全綠並達覆蓋率。

- [ ] 10.5 驗證 `tests/test_pipeline.py` 與新 fixture 相容：
  - 若既有測試以 fixture 計算期望筆數、抽樣特定片名／集數，須依新 fixture 重算期望值。
  - 「部分解析錯誤不中斷」scenario 若原本以舊 DOM 合成片段測試，改以「新 fixture 加上一張故意缺欄位的 `a.text-anime-info`」的變體覆蓋。
  - 「`ScrapeEmptyError`」scenario 可改以「mock fetcher 回傳不含 `.programlist-wrap` 的 HTML」觸發。
  - pipeline 本身若需為了測試 seam 微調介面（例：允許注入 parser / time provider），可連同 `src/baha/pipeline.py` 一併調整，但不得改變 `run_once` / `main` 對上層呼叫的行為合約。

  檔案範圍：`tests/test_pipeline.py`、必要時 `src/baha/pipeline.py`。驗收：`docker compose run --rm app pytest tests/test_pipeline.py -v` 全綠，且整體 `pytest -m "not integration"` 繼續全綠。

- [ ] 10.6 完成 10.1–10.5 後，回到 Section 5 / 6.1 / 8.2 將對應 checkbox 重新勾選並刪除「[2026-04-22 需依新 DOM 重做 …]」註記，同時重新執行 Section 9.2 完整測試覆蓋率檢查。檔案範圍：本 `tasks.md`、無程式碼變動。驗收：tasks.md 中不再有「需依新 DOM 重做」文字；`pytest --cov=baha` 覆蓋率報告符合 9.2 要求。

> 備註：本變更不得修改 `openspec/` 以外的現有檔案以外的範圍；若實作中發現需修改 `CLAUDE.md` 或本 tasks.md 未列之檔案，須依全域規範寫入 `openspec/changes/scrape-bahamut-anime-schedule/issues.md`，由 Coordinator 更新 tasks 後再繼續。
