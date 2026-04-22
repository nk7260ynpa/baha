-- anime_schedule 資料表初始化 SQL。
--
-- MariaDB 官方 image 於首次啟動時，會自動執行 /docker-entrypoint-initdb.d
-- 目錄下的 *.sql；使用 IF NOT EXISTS 讓同一 volume 第二次啟動時不會報錯。
--
-- 欄位設計參考 design.md D2；字元集 utf8mb4 以支援日韓文動畫片名。

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
