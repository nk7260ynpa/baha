"""baha 套件的組態讀取模組。

從環境變數讀取必要設定並以 ``AppConfig`` dataclass 呈現；對必填欄位
若缺失則拋出 ``ConfigError`` 中斷啟動，避免後續 runtime 以模糊錯誤
回報問題。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """設定錯誤：必要環境變數缺失或格式不合法時拋出。"""


@dataclass(frozen=True)
class AppConfig:
    """應用程式組態。

    Attributes:
        db_host: MariaDB 主機名稱。
        db_port: MariaDB 連線埠。
        db_name: 資料庫名稱。
        db_user: 連線使用者名稱。
        db_password: 連線密碼（必填）。
        log_level: Python logging level 字串，如 ``INFO``、``DEBUG``。
    """

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    log_level: str


_REQUIRED_KEYS: tuple[str, ...] = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


def _collect_missing(env: dict[str, str], keys: Iterable[str]) -> list[str]:
    """找出環境中缺失（未設定或為空字串）的必填鍵。"""
    missing: list[str] = []
    for key in keys:
        value = env.get(key)
        if value is None or value.strip() == "":
            missing.append(key)
    return missing


def load_config(env: dict[str, str] | None = None) -> AppConfig:
    """從環境變數建立 AppConfig。

    Args:
        env: 環境變數字典，預設讀取 ``os.environ``。主要供測試注入。

    Returns:
        已驗證的 :class:`AppConfig` 實例。

    Raises:
        ConfigError: 必填環境變數缺失，或 ``DB_PORT`` 無法解析為整數。
    """
    source = dict(os.environ) if env is None else dict(env)

    missing = _collect_missing(source, _REQUIRED_KEYS)
    if missing:
        names = ", ".join(missing)
        logger.error("必要環境變數缺失：%s", names)
        raise ConfigError(f"必要環境變數缺失：{names}")

    try:
        port = int(source["DB_PORT"])
    except ValueError as exc:
        logger.error("DB_PORT 不是合法整數：%s", source["DB_PORT"])
        raise ConfigError(f"DB_PORT 不是合法整數：{source['DB_PORT']}") from exc

    log_level = source.get("LOG_LEVEL", "INFO").strip().upper() or "INFO"

    return AppConfig(
        db_host=source["DB_HOST"],
        db_port=port,
        db_name=source["DB_NAME"],
        db_user=source["DB_USER"],
        db_password=source["DB_PASSWORD"],
        log_level=log_level,
    )
