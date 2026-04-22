# anime-schedule-scraper Specification

## Purpose
TBD - created by archiving change scrape-bahamut-anime-schedule. Update Purpose after archive.
## Requirements
### Requirement: 從動畫瘋首頁抓取週期表 HTML

系統 SHALL 對 <https://ani.gamer.com.tw/> 發送 HTTP GET 請求，取得首頁的 HTML 內容（其中包含 `.programlist-wrap` 週期表區塊），並在成功時回傳 UTF-8 解碼後的字串。

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

### Requirement: 解析週期表 HTML 取得多部動畫資訊

系統 SHALL 將抓取的 HTML 解析為結構化物件清單，每個物件至少包含「片名」「集數」「週幾」「HH:MM 時段」四個欄位。資料來源 DOM 結構如下：

```
.programlist-wrap
  .programlist-wrap_block
    .programlist-block
      .day-list
        h3.day-title              ← 文字「週一」…「週日」
        a.text-anime-info         ← 每張卡片
          span.text-anime-time    ← "HH:MM"
          .text-anime-detail
            p.text-anime-name     ← 片名
            p.text-anime-number   ← "第 N 集" / "特別篇" 等
```

`weekday` 由 `h3.day-title` 文字映射：`{"週一":0, "週二":1, "週三":2, "週四":3, "週五":4, "週六":5, "週日":6}`。系統 SHALL 在單次執行中擷取「多部」動畫，即回傳清單長度 MUST >= 2（當時刻表本身僅有 0 或 1 部動畫時除外）。

#### Scenario: 正常解析涵蓋一週七天的動畫

- **GIVEN** 輸入 HTML 為 `tests/fixtures/animeList_sample.html`（擷取自動畫瘋首頁真實樣本），其中包含 `.programlist-wrap` 區塊並覆蓋週一至週日共 7 個 `.day-list`，每日至少 1 張 `a.text-anime-info` 卡片，總卡片數 >= 10
- **WHEN** 呼叫 `parse_schedule(html)`
- **THEN** 系統回傳長度 >= 10 的 `ScheduleCard` 清單
- **AND** 清單中每個物件的 `title` 為非空字串、`episode` 為非空字串、`weekday` 為 0 至 6 的整數（0 = 週一、6 = 週日）、`hhmm` 為符合 `^\d{2}:\d{2}$` 的字串
- **AND** 對每個 `weekday` 值（0 至 6），清單中至少有一筆對應紀錄

#### Scenario: 週別標題無法辨識時略過整個 day-list

- **GIVEN** 某個 `.day-list` 的 `h3.day-title` 文字不屬於 `"週一"`…`"週日"`（例：為空、為「本週特別企劃」、為英文「Mon」）
- **WHEN** 呼叫 `parse_schedule(html)`
- **THEN** 系統 SHALL 略過該 `.day-list` 底下所有卡片
- **AND** 以 WARN 等級記錄 `無法識別的 day-title=<原始文字>`

#### Scenario: 忽略結構不完整的卡片

- **GIVEN** `.day-list` 內的某個 `a.text-anime-info` 缺少 `span.text-anime-time`、`p.text-anime-name`、或 `p.text-anime-number` 任一子節點
- **WHEN** 呼叫 `parse_schedule(html)`
- **THEN** 系統 SHALL 僅略過該單一卡片，不影響同 `.day-list` 內其他卡片
- **AND** 以 WARN 等級記錄該卡片的前 200 字原始片段

#### Scenario: HH:MM 格式不合即略過該卡片

- **GIVEN** 某張 `a.text-anime-info` 的 `span.text-anime-time` 文字不符合 `^\d{2}:\d{2}$`（例：`"待定"`、`"25:00"`、`"1:00"`）
- **WHEN** 呼叫 `parse_schedule(html)`
- **THEN** 系統 SHALL 略過該單一卡片並以 WARN 等級記錄不合法的時間字串

#### Scenario: 片名與集數清洗

- **GIVEN** `p.text-anime-name` 文字含前後空白、`p.text-anime-number` 文字形如 `"第 01 集"`
- **WHEN** 呼叫 `parse_schedule(html)`
- **THEN** 系統 SHALL 對片名執行 `strip()` 並保留其餘文字原樣（不自行翻譯、不轉換全半形）
- **AND** 集數形如 `"第 N 集"` 時 SHALL 去除「第」「集」與內部空白後保留核心編號（`"第 01 集"` → `"01"`、`"第 12 集"` → `"12"`）
- **AND** 集數若為 `"特別篇"`、`"OVA"` 等非「第 N 集」格式，SHALL 保留 `strip()` 後的原字串

#### Scenario: 找不到 programlist-wrap 時回傳空清單並記錄樣本

- **WHEN** 輸入 HTML 為空字串，或整份 HTML 不含任何 `.programlist-wrap` 節點
- **THEN** 系統 SHALL 回傳空清單
- **AND** 以 ERROR 等級記錄「解析失敗：找不到 .programlist-wrap 區塊」並將 HTML 前 2048 字元寫入 log 供除錯

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

