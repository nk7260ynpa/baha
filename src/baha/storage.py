"""Storage 模組：MariaDB 的連線、upsert 寫入與時區設定。

設計依 design.md D2 / spec ``anime-schedule-storage``：

* 連線成功後即 ``SET time_zone='+08:00'``。
* 對 ``(title, episode)`` 以 ``INSERT ... ON DUPLICATE KEY UPDATE`` upsert。
* 以 MariaDB 的 ``ROW_COUNT()`` 區分 inserted / updated / unchanged：
  * 1 筆資料：``ROW_COUNT() == 1`` 表示 inserted；
  * ``ROW_COUNT() == 2`` 表示發生 update；
  * ``ROW_COUNT() == 0`` 表示內容不變（unchanged）。
* 連線錯誤 ``2003`` 最多重試 5 次、每次間隔 2 秒；全部失敗拋
  :class:`StorageConnectionError`。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional, Protocol

import pymysql
from pymysql.err import OperationalError

from baha.config import AppConfig

logger = logging.getLogger(__name__)

_CONNECT_MAX_ATTEMPTS = 5
_CONNECT_RETRY_DELAY_SECONDS = 2
_MYSQL_CANT_CONNECT_ERRNO = 2003

_UPSERT_SQL = (
    "INSERT INTO anime_schedule (title, episode, air_time) "
    "VALUES (%s, %s, %s) "
    "ON DUPLICATE KEY UPDATE air_time=VALUES(air_time)"
)


class StorageConnectionError(RuntimeError):
    """資料庫連線錯誤：重試用盡仍無法連線時拋出。"""


@dataclass(frozen=True)
class AnimeScheduleRecord:
    """寫入資料表的單筆紀錄。"""

    title: str
    episode: str
    air_time: datetime


@dataclass(frozen=True)
class UpsertStats:
    """upsert 結果統計；三者加總 == 輸入筆數。"""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    def total(self) -> int:
        """回傳 inserted + updated + unchanged。"""
        return self.inserted + self.updated + self.unchanged


class _Connector(Protocol):
    """``pymysql.connect`` 的最小型別介面，方便測試注入。"""

    def __call__(self, **kwargs: Any) -> Any: ...


class Storage:
    """MariaDB 儲存層。"""

    def __init__(
        self,
        config: AppConfig,
        *,
        connector: Optional[_Connector] = None,
        sleep_fn: Any = time.sleep,
    ) -> None:
        """建立 Storage 實例並連線。

        Args:
            config: 應用組態，提供連線資訊。
            connector: 可注入的 connect 函式，預設為 ``pymysql.connect``。
            sleep_fn: 可注入的 sleep 函式，主要供測試避免真正等待。
        """
        self._config = config
        self._connector = connector or pymysql.connect
        self._sleep_fn = sleep_fn
        self._conn = self._connect_with_retry()
        self._set_session_timezone()

    # -- 連線相關 --------------------------------------------------------

    def _connect_with_retry(self) -> Any:
        last_exc: Optional[BaseException] = None
        for attempt in range(1, _CONNECT_MAX_ATTEMPTS + 1):
            try:
                return self._connector(
                    host=self._config.db_host,
                    port=self._config.db_port,
                    user=self._config.db_user,
                    password=self._config.db_password,
                    database=self._config.db_name,
                    charset="utf8mb4",
                    autocommit=False,
                )
            except OperationalError as exc:
                last_exc = exc
                errno = exc.args[0] if exc.args else None
                if errno != _MYSQL_CANT_CONNECT_ERRNO:
                    logger.error("MariaDB 連線失敗（非可重試錯誤）：%r", exc)
                    raise StorageConnectionError(str(exc)) from exc
                logger.warning(
                    "MariaDB 暫不可連線，第 %d/%d 次；error=%r",
                    attempt, _CONNECT_MAX_ATTEMPTS, exc,
                )
                if attempt < _CONNECT_MAX_ATTEMPTS:
                    self._sleep_fn(_CONNECT_RETRY_DELAY_SECONDS)
        logger.error("MariaDB 連線重試用盡；最後錯誤=%r", last_exc)
        raise StorageConnectionError(
            f"MariaDB 連線失敗（重試 {_CONNECT_MAX_ATTEMPTS} 次皆失敗）"
        )

    def _set_session_timezone(self) -> None:
        """於連線上執行 ``SET time_zone='+08:00'``。"""
        with self._conn.cursor() as cursor:
            cursor.execute("SET time_zone='+08:00'")
        self._conn.commit()
        logger.info("已設定 MariaDB session time_zone=+08:00")

    def close(self) -> None:
        """關閉底層連線。"""
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001 — close 階段已無法挽救
            logger.debug("close 連線時發生錯誤，已忽略", exc_info=True)

    # -- 寫入相關 --------------------------------------------------------

    def upsert_records(
        self, records: Iterable[AnimeScheduleRecord]
    ) -> UpsertStats:
        """對每筆紀錄執行 upsert 並統計。

        Args:
            records: 待寫入的紀錄；可為 list、tuple 或其他 iterable。

        Returns:
            :class:`UpsertStats`，inserted/updated/unchanged 加總 == 輸入筆數。
        """
        items = list(records)
        if not items:
            logger.info("upsert_records 收到空清單，不發送任何 SQL")
            return UpsertStats()

        inserted = 0
        updated = 0
        unchanged = 0

        with self._conn.cursor() as cursor:
            for record in items:
                cursor.execute(
                    _UPSERT_SQL,
                    (record.title, record.episode, record.air_time),
                )
                affected = cursor.rowcount
                if affected == 1:
                    inserted += 1
                elif affected == 2:
                    updated += 1
                else:
                    # pymysql 對 ON DUPLICATE KEY UPDATE 內容不變回傳 0。
                    unchanged += 1
        self._conn.commit()

        stats = UpsertStats(inserted=inserted, updated=updated, unchanged=unchanged)
        logger.info(
            "upsert_records 完成；inserted=%d updated=%d unchanged=%d total=%d",
            stats.inserted, stats.updated, stats.unchanged, stats.total(),
        )
        return stats
