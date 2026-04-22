# baha — 巴哈姆特動畫瘋上片時間爬蟲

本專案從巴哈姆特動畫瘋（<https://ani.gamer.com.tw/>）抓取多部動畫的「上片時間、片名、集數」，
並寫入以 Docker 啟動的 MariaDB 資料庫。

## 專案架構

```
baha/
├── README.md                 # 本檔
├── docker/                   # Docker 相關檔案（由 change 產出）
│   ├── build.sh              # 建立 image 的腳本
│   ├── Dockerfile            # app container 定義
│   └── docker-compose.yaml   # app + MariaDB 服務編排
├── run.sh                    # 啟動主程式入口（掛載 logs/）
├── logs/                     # 執行 log（gitignore）
├── openspec/                 # 規格（spec-driven development）
│   └── changes/              # 進行中的變更提案
└── ...（其餘原始碼將於 apply 階段由 Specialist 建立）
```

## 現況

專案處於 spec 規劃階段，詳見：

- `openspec/changes/scrape-bahamut-anime-schedule/` — 初始變更提案

下一步：由使用者 Review `openspec/changes/scrape-bahamut-anime-schedule/` 中的 artifact，
確認無誤後交由 Specialist 執行 `/opsx:apply` 進入實作階段。
