# anime-schedule-storage Specification

## Purpose
TBD - created by archiving change scrape-bahamut-anime-schedule. Update Purpose after archive.
## Requirements
### Requirement: 建立 MariaDB 資料表 `anime_schedule`

系統 SHALL 於 MariaDB 中建立名為 `anime_schedule` 的資料表，欄位 MUST 至少包含以下三項核心欄位：

- `title`：動畫片名，型別 `VARCHAR(255) NOT NULL`。
- `episode`：集數或特別標籤，型別 `VARCHAR(32) NOT NULL`。
- `air_time`：上片時間（絕對 DATETIME，時區 Asia/Taipei 的 naive datetime），型別 `DATETIME NOT NULL`。

資料表 SHALL 具備以下唯一鍵與稽核欄位：

- 唯一鍵 `uk_title_episode` 建立於 `(title, episode)` 上。
- 主鍵 `id`：`INT UNSIGNED AUTO_INCREMENT PRIMARY KEY`。
- `created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP`。
- `updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`。

資料表字元集 SHALL 為 `utf8mb4` / collate `utf8mb4_unicode_ci`，儲存引擎為 `InnoDB`。

#### Scenario: 首次啟動 MariaDB container 時自動建表

- **WHEN** MariaDB container 首次啟動並執行 `docker/initdb/001_schema.sql`
- **THEN** `anime_schedule` 資料表 SHALL 被建立
- **AND** 以 `SHOW CREATE TABLE anime_schedule` 查詢時，輸出含 `UNIQUE KEY uk_title_episode (title, episode)`

#### Scenario: 重複啟動不會重建或破壞資料

- **WHEN** MariaDB container 第二次以同一 volume 啟動
- **THEN** 既有資料 SHALL 保留
- **AND** 建表 SQL 使用 `CREATE TABLE IF NOT EXISTS`，第二次啟動不會拋出錯誤

### Requirement: 將紀錄以 upsert 寫入，避免重複

系統 SHALL 提供 `storage.upsert_records(records: list[AnimeScheduleRecord]) -> UpsertStats` 函式，逐筆以「片名 + 集數」為唯一鍵進行 upsert：若不存在則 insert，若已存在則 update `air_time` 與 `updated_at`。

回傳的 `UpsertStats` SHALL 至少包含 `inserted: int`、`updated: int`、`unchanged: int` 三個欄位，三者加總等於輸入筆數。

#### Scenario: 全部為新紀錄時全部 insert

- **GIVEN** 資料表為空
- **WHEN** 呼叫 `upsert_records([R1, R2, R3])`（三筆 title+episode 皆為新值）
- **THEN** 資料表 SHALL 新增 3 列
- **AND** 回傳 `UpsertStats(inserted=3, updated=0, unchanged=0)`

#### Scenario: 既有紀錄且 air_time 改變時 update

- **GIVEN** 資料表已有 `(title="咒術迴戰", episode="12", air_time=2025-01-01 22:00)`
- **WHEN** 呼叫 `upsert_records([R])`，其中 R 為 `(title="咒術迴戰", episode="12", air_time=2025-01-01 23:00)`
- **THEN** 資料表該列的 `air_time` SHALL 更新為 `2025-01-01 23:00`
- **AND** 該列的 `updated_at` SHALL 被資料庫自動更新為當前時間
- **AND** 回傳 `UpsertStats(inserted=0, updated=1, unchanged=0)`

#### Scenario: 既有紀錄且 air_time 未變時不 update

- **GIVEN** 資料表已有 `(title="咒術迴戰", episode="12", air_time=2025-01-01 22:00)`
- **WHEN** 呼叫 `upsert_records([R])`，其中 R 與既有列完全相同
- **THEN** `updated_at` SHALL 不被修改
- **AND** 回傳 `UpsertStats(inserted=0, updated=0, unchanged=1)`

#### Scenario: 空清單視為無操作

- **WHEN** 呼叫 `upsert_records([])`
- **THEN** 系統 SHALL 不發出任何 SQL DML
- **AND** 回傳 `UpsertStats(inserted=0, updated=0, unchanged=0)`

### Requirement: 連線設定與時區

系統 SHALL 透過環境變數取得 MariaDB 連線資訊，包含 `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`；連線成功後 SHALL 將 session time zone 設為 `+08:00`（Asia/Taipei）。

#### Scenario: 環境變數缺失時拒絕啟動

- **WHEN** `DB_PASSWORD` 未設定
- **THEN** 系統 SHALL 於啟動時以 ERROR log 指出缺少的變數名稱並 exit code 非 0
- **AND** 不嘗試建立任何連線

#### Scenario: 連線後設定 session 時區

- **WHEN** 連線建立成功
- **THEN** 系統 SHALL 執行 `SET time_zone = '+08:00'`
- **AND** 後續 `SELECT @@session.time_zone` 回傳 `+08:00`

#### Scenario: 連線失敗時短暫等待後重試

- **WHEN** 連線失敗且錯誤為 `2003` (Can't connect)
- **THEN** 系統 SHALL 重試最多 5 次，每次間隔 2 秒
- **AND** 全部失敗時拋出 `StorageConnectionError` 並記 ERROR log

