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

---

## [使用者] [2026-04-22 21:28] [HIGH] 冒煙失敗：host port 3306 衝突

**現象**：使用者於宿主機執行 `./run.sh` 時，`docker compose up -d mariadb`
失敗，錯誤訊息：

```
Error response from daemon: failed to set up container networking: driver
failed programming external connectivity on endpoint baha-mariadb:
Bind for 127.0.0.1:3306 failed: port is already allocated
```

**根因**：`docker/docker-compose.yaml` 中 `mariadb` service 硬寫
`ports: "3306:3306"`。使用者宿主機上已有其他 project（`tw_stock_database`）
長期佔用 127.0.0.1:3306，導致本專案 mariadb 無法啟動。

**範圍判斷**：
本專案 app service 透過 compose 內部網路連線 mariadb（`DB_HOST=mariadb`），
**不需要** host port binding；host port 僅用於宿主機直接連 DB 做除錯／驗收。
因此兩種修法都可行：

1. **移除 host port binding**（最無衝突；但失去宿主直連能力）。
2. **改為可由 `.env` 覆寫的變數**（例如 `MARIADB_HOST_PORT`，預設空字串
   代表不綁；或預設 3307），兼顧多環境彈性。

**建議修法**：採方案 2——`docker-compose.yaml` 改為
`"${MARIADB_HOST_PORT:-3307}:3306"`，並在 `.env.example` 加入
`MARIADB_HOST_PORT=3307` 註解說明可依需求調整（或留空以完全不綁 host port）。
同步更新 `design.md` 與 `specs/scraper-runtime/spec.md` 相關描述
（若 spec 明確寫 3306 才需動；若僅說「host port 暴露」則僅 compose 調整即可）。

**受影響檔案（預期）**：
- `docker/docker-compose.yaml`
- `.env.example`
- （若 spec 提及特定 port）`design.md`、`specs/scraper-runtime/spec.md`
- `README.md`（環境變數清單與測試方法段落需同步）

**驗收條件**：
1. `./run.sh` 在已有 3306 佔用者的宿主上仍能成功啟動 mariadb。
2. `docker compose exec mariadb mariadb -ubaha -p baha -e "SELECT COUNT(*) FROM anime_schedule;"` 可取得資料。
3. 單元測試繼續全綠。
