"""baha 套件的 logging 初始化模組。

同時將 log 輸出到 stdout 與 ``/app/logs/baha-YYYYMMDD.log``；log level 由
``AppConfig.log_level`` 決定，格式統一為
``%(asctime)s %(levelname)s %(name)s %(message)s``。
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from baha.config import AppConfig

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DEFAULT_LOG_DIR = "/app/logs"


def _resolve_log_dir() -> Path:
    """取得 log 目錄；若環境變數 ``BAHA_LOG_DIR`` 有設定則優先採用。

    測試於非 container 環境可設 ``BAHA_LOG_DIR`` 避免寫到 /app/logs。
    """
    raw = os.environ.get("BAHA_LOG_DIR", _DEFAULT_LOG_DIR)
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _today_filename(today: datetime | None = None) -> str:
    """回傳當日 log 檔名，如 ``baha-20250422.log``。"""
    now = today or datetime.now()
    return f"baha-{now:%Y%m%d}.log"


def setup_logging(config: AppConfig, *, today: datetime | None = None) -> logging.Logger:
    """依 ``AppConfig`` 設定 root logger。

    為避免重複呼叫時 handler 堆疊，會先清除既有 handlers。

    Args:
        config: 應用程式組態，取用 ``log_level``。
        today: 供測試注入「今天」的 datetime，預設為 ``datetime.now()``。

    Returns:
        已設定完成的 root logger。
    """
    level = getattr(logging, config.log_level, logging.INFO)

    log_dir = _resolve_log_dir()
    log_path = log_dir / _today_filename(today)

    formatter = logging.Formatter(_LOG_FORMAT)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(level)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root = logging.getLogger()
    # 清除既有 handler，避免測試或多次呼叫造成重複輸出。
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.setLevel(level)
    root.addHandler(stdout_handler)
    root.addHandler(file_handler)

    root.info("logging 初始化完成；level=%s, file=%s", config.log_level, log_path)
    return root
