## ADDED Requirements

### Requirement: 從動畫瘋時刻表抓取 HTML

系統 SHALL 對 <https://ani.gamer.com.tw/animeList.php> 發送 HTTP GET 請求，取得新番時刻表的 HTML 內容，並在成功時回傳 UTF-8 解碼後的字串。

#### Scenario: 正常抓取成功

- **WHEN** 遠端伺服器以 HTTP 200 回應，且 Content-Type 為 `text/html`
- **THEN** 系統回傳解碼後的 HTML 字串（長度 > 0）
- **AND** 以 INFO 等級記錄「抓取成功、大小為 N bytes、耗時為 T 毫秒」

#### Scenario: 非 2xx 狀態碼時重試

- **WHEN** 第一次請求回應為 HTTP 503
- **THEN** 系統 SHALL 在 2 秒後重試，最多重試 3 次（合計最多 4 次請求），每次重試間隔以指數退避（2、4、8 秒）
- **AND** 若所有重試皆失敗，系統 SHALL 拋出 `FetchError` 並以 ERROR 等級記錄最後一次回應的狀態碼

#### Scenario: 網路連線錯誤

- **WHEN** 發生 `ConnectionError` 或 `Timeout`
- **THEN** 系統 SHALL 以 D7 所定的重試策略重試，最多 3 次
- **AND** 所有重試失敗時拋出 `FetchError` 並記錄錯誤原因

#### Scenario: User-Agent 識別

- **WHEN** 系統發送請求
- **THEN** HTTP header `User-Agent` SHALL 包含字串 `baha-schedule-scraper`，並以此與其他爬蟲區分

### Requirement: 解析時刻表 HTML 取得多部動畫資訊

系統 SHALL 將抓取的 HTML 解析為結構化物件清單，每個物件至少包含「片名」「集數」「週幾」「HH:MM 時段」四個欄位。系統 SHALL 在單次執行中擷取「多部」動畫，即回傳清單長度 MUST >= 2（當時刻表本身僅有 0 或 1 部動畫時除外）。

#### Scenario: 正常解析多部動畫

- **WHEN** 輸入 HTML 為 `tests/fixtures/animeList_sample.html`（內含至少 10 部動畫的時刻表區塊）
- **THEN** 系統回傳長度 >= 10 的清單
- **AND** 清單中每個物件的 `title` 為非空字串、`episode` 為非空字串、`weekday` 為 0 至 6 的整數（0 = 週一、6 = 週日）、`hhmm` 為 `HH:MM` 格式字串

#### Scenario: 忽略非動畫的干擾區塊

- **WHEN** HTML 含有廣告、登入提示等非時刻表卡片
- **THEN** 系統 SHALL 僅回傳符合時刻表卡片結構（含片名、集數、週幾、時段）的項目
- **AND** 對於結構不完整的卡片（缺任一必要欄位），SHALL 略過並以 WARN 等級記錄該卡片的前 200 字原始片段

#### Scenario: 片名與集數清洗

- **WHEN** 擷取到的片名含前後空白或全形/半形混用
- **THEN** 系統 SHALL 對片名執行 `strip()` 並保留其餘文字原樣（不自行翻譯或轉換字元）
- **AND** 集數若形如「第 01 集」，SHALL 保留為字串 `"01"`（去除「第」「集」等文字後的核心數字或特別篇標籤如 `"特別篇"`）

#### Scenario: 解析失敗時記錄樣本

- **WHEN** 輸入 HTML 為空字串或為明顯不符合時刻表結構的內容
- **THEN** 系統 SHALL 回傳空清單
- **AND** 以 ERROR 等級記錄「解析失敗」並將 HTML 前 2048 字元寫入 log 供除錯

### Requirement: 爬蟲一次執行即完成抓取—解析—回傳

系統 SHALL 提供單一入口函式（例如 `pipeline.run_once(fetched_at: datetime) -> list[AnimeScheduleRecord]`），在給定抓取時刻下完成「抓取 → 解析 → 產出帶絕對時間的紀錄清單」的流程，供上層 CLI 呼叫。

#### Scenario: one-shot 執行回傳紀錄

- **WHEN** 呼叫入口函式且網路正常
- **THEN** 系統 SHALL 回傳 `AnimeScheduleRecord` 物件清單，每個物件欄位包含 `title: str`、`episode: str`、`air_time: datetime`（已由 time_utils 轉換）
- **AND** 紀錄筆數 SHALL >= 2（否則抛出 `ScrapeEmptyError` 並記 WARN）

#### Scenario: 部分解析錯誤不中斷整體流程

- **WHEN** 時刻表中有 10 筆資料，其中 2 筆因結構不完整被略過
- **THEN** 系統 SHALL 回傳其餘 8 筆合法紀錄
- **AND** 記錄 WARN 等級 log 指出跳過的筆數與原因
