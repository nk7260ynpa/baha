# Issues

本檔記錄 `scrape-bahamut-anime-schedule` change 在實作過程中發現的
阻塞、疑問或需 Coordinator 協調的事項。

---

## [Specialist] [2026-04-22] [MED] Task 9.3 手動冒煙未執行

Task 9.3 要求執行 `./run.sh` 後驗證 MariaDB 中
`SELECT COUNT(*) FROM anime_schedule >= 2`，且 `logs/baha-YYYYMMDD.log` 存在。

**現況**：

1. Specialist 的執行環境受沙盒限制，無法保證對外網（ani.gamer.com.tw）
   的實際抓取會成功，且無法確認真實網站目前的 DOM 結構是否符合
   `parser.py` 假設的 `.schedule-week .animate-theme-list .theme-list-block`
   階層。`tests/fixtures/animeList_sample.html` 為仿真樣本，其 DOM 結構
   是依 design.md 文字描述與常見 HTML 慣例推導，未經真實頁面比對。

2. 因此 Specialist 已**完成**所有單元測試（45 passed、parser / time_utils
   覆蓋率 >= 80%），但**未執行** `./run.sh` 的端到端冒煙。

**建議**：

* 由 Verifier 或使用者在具有網路的宿主環境執行 `./run.sh` 進行驗收。
* 若真實 HTML 的 selector 與 fixture 不同，需回報給 Coordinator 更新
  parser selector 與 fixture 的 task（屬於新一輪 change 或 FAIL 修復迭代
  的範疇）。

**Specialist 觀察到的風險**：parser 目前以 `.schedule-week[data-week="N"]`
推導 weekday，若真實動畫瘋頁面不採此屬性，parser 會回傳空清單而
pipeline 拋 `ScrapeEmptyError`。這屬於 spec 未能涵蓋的實作細節；若冒煙
失敗，應視為「spec 與真實世界的落差」交由 Coordinator 決定後續。

Tasks.md 中對應 checkbox（9.3）尚未勾選。
