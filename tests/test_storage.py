"""Storage 模組的測試。

單元測試（預設）：

* 使用 mock 的 connector 驗證「連線後設 time_zone」與「空清單不發 SQL」。
* 驗證 inserted / updated / unchanged 計數邏輯（透過 mock cursor 的 rowcount）。
* 驗證連線失敗（errno 2003）重試 5 次與 StorageConnectionError。
* 驗證缺 DB_PASSWORD 時 load_config 拋 ConfigError（跨模組確認環境驗證鏈）。

整合測試（需 mariadb）以 ``@pytest.mark.integration`` 標記；預設跳過。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from pymysql.err import OperationalError

from baha.config import AppConfig, ConfigError, load_config
from baha.storage import (
    AnimeScheduleRecord,
    Storage,
    StorageConnectionError,
    UpsertStats,
)


def _make_config() -> AppConfig:
    return AppConfig(
        db_host="localhost",
        db_port=3306,
        db_name="baha",
        db_user="baha",
        db_password="pw",
        log_level="INFO",
    )


def _build_mock_connector(
    cursor_rowcounts: list[int] | None = None,
) -> tuple[Any, MagicMock, MagicMock]:
    """建立模擬的 connector 工廠，回傳 (connector, conn_mock, cursor_mock)。"""
    cursor_mock = MagicMock()
    cursor_mock.__enter__ = MagicMock(return_value=cursor_mock)
    cursor_mock.__exit__ = MagicMock(return_value=False)

    # 讓 rowcount 依序回傳。
    if cursor_rowcounts is not None:
        rowcount_iter = iter(cursor_rowcounts)

        def _execute_side_effect(*_args: Any, **_kwargs: Any) -> None:
            cursor_mock.rowcount = next(rowcount_iter)

        cursor_mock.execute.side_effect = _execute_side_effect

    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock

    def connector(**_kwargs: Any) -> Any:
        return conn_mock

    return connector, conn_mock, cursor_mock


class TestStorageConnectAndTimezone:
    def test_sets_session_timezone_on_connect(self) -> None:
        connector, conn_mock, cursor_mock = _build_mock_connector()
        Storage(_make_config(), connector=connector, sleep_fn=lambda _s: None)
        # 應至少呼叫過 SET time_zone。
        sql_calls = [c.args[0] for c in cursor_mock.execute.call_args_list]
        assert any("time_zone" in sql for sql in sql_calls)
        conn_mock.commit.assert_called()


class TestStorageUpsert:
    def test_empty_records_does_not_execute_dml(self) -> None:
        connector, conn_mock, cursor_mock = _build_mock_connector()
        storage = Storage(_make_config(), connector=connector, sleep_fn=lambda _s: None)
        # 重置在 __init__ 呼叫的紀錄，以便只觀察 upsert 本身的行為。
        cursor_mock.execute.reset_mock()
        conn_mock.commit.reset_mock()

        stats = storage.upsert_records([])

        assert stats == UpsertStats(inserted=0, updated=0, unchanged=0)
        cursor_mock.execute.assert_not_called()
        conn_mock.commit.assert_not_called()

    def test_all_new_rows_are_inserted(self) -> None:
        connector, conn_mock, cursor_mock = _build_mock_connector(
            cursor_rowcounts=[1, 1, 1]
        )
        storage = Storage(_make_config(), connector=connector, sleep_fn=lambda _s: None)
        cursor_mock.execute.reset_mock()
        conn_mock.commit.reset_mock()

        # 重新綁定 rowcount side effect，因 __init__ 已消耗 0 次。
        def _exec(*_a: Any, **_k: Any) -> None:
            cursor_mock.rowcount = 1
        cursor_mock.execute.side_effect = _exec

        records = [
            AnimeScheduleRecord("a", "01", datetime(2025, 1, 1, 22, 0)),
            AnimeScheduleRecord("b", "01", datetime(2025, 1, 2, 22, 0)),
            AnimeScheduleRecord("c", "01", datetime(2025, 1, 3, 22, 0)),
        ]
        stats = storage.upsert_records(records)
        assert stats == UpsertStats(inserted=3, updated=0, unchanged=0)
        assert cursor_mock.execute.call_count == 3
        conn_mock.commit.assert_called_once()

    def test_mixed_insert_update_unchanged(self) -> None:
        """rowcount 1=insert、2=update、0=unchanged。"""
        connector, conn_mock, cursor_mock = _build_mock_connector()
        storage = Storage(_make_config(), connector=connector, sleep_fn=lambda _s: None)
        cursor_mock.execute.reset_mock()
        conn_mock.commit.reset_mock()

        rowcounts = iter([1, 2, 0])

        def _exec(*_a: Any, **_k: Any) -> None:
            cursor_mock.rowcount = next(rowcounts)
        cursor_mock.execute.side_effect = _exec

        records = [
            AnimeScheduleRecord("a", "01", datetime(2025, 1, 1, 22, 0)),
            AnimeScheduleRecord("b", "01", datetime(2025, 1, 2, 22, 0)),
            AnimeScheduleRecord("c", "01", datetime(2025, 1, 3, 22, 0)),
        ]
        stats = storage.upsert_records(records)
        assert stats == UpsertStats(inserted=1, updated=1, unchanged=1)
        assert stats.total() == 3


class TestStorageConnectionRetry:
    def test_retries_on_errno_2003_then_raises(self) -> None:
        call_count = {"n": 0}

        def connector(**_kwargs: Any) -> Any:
            call_count["n"] += 1
            raise OperationalError(2003, "Can't connect")

        sleep_calls: list[float] = []
        with pytest.raises(StorageConnectionError):
            Storage(
                _make_config(),
                connector=connector,
                sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert call_count["n"] == 5
        # 最後一次失敗後不會再等待，故應 sleep 4 次（每次 2 秒）。
        assert sleep_calls == [2, 2, 2, 2]

    def test_non_retriable_error_raises_immediately(self) -> None:
        def connector(**_kwargs: Any) -> Any:
            raise OperationalError(1045, "Access denied")

        with pytest.raises(StorageConnectionError):
            Storage(_make_config(), connector=connector, sleep_fn=lambda _s: None)


class TestConfigMissingPassword:
    def test_missing_password_raises_config_error(self) -> None:
        env = {
            "DB_HOST": "mariadb",
            "DB_PORT": "3306",
            "DB_NAME": "baha",
            "DB_USER": "baha",
            # 故意缺 DB_PASSWORD
            "LOG_LEVEL": "INFO",
        }
        with pytest.raises(ConfigError) as exc_info:
            load_config(env)
        assert "DB_PASSWORD" in str(exc_info.value)

    def test_empty_password_raises_config_error(self) -> None:
        env = {
            "DB_HOST": "mariadb",
            "DB_PORT": "3306",
            "DB_NAME": "baha",
            "DB_USER": "baha",
            "DB_PASSWORD": "   ",
        }
        with pytest.raises(ConfigError):
            load_config(env)

    def test_invalid_port_raises(self) -> None:
        env = {
            "DB_HOST": "mariadb",
            "DB_PORT": "not-a-number",
            "DB_NAME": "baha",
            "DB_USER": "baha",
            "DB_PASSWORD": "pw",
        }
        with pytest.raises(ConfigError):
            load_config(env)


# ---- 整合測試（需 mariadb service） -----------------------------------
integration = pytest.mark.integration


@integration
class TestStorageIntegration:  # pragma: no cover - 需實際 DB 環境
    """整合測試：需啟動 docker compose 的 mariadb service。"""

    @pytest.fixture(autouse=True)
    def _require_env(self) -> None:
        if not os.environ.get("DB_HOST"):
            pytest.skip("未設定 DB_HOST，略過整合測試")

    def test_insert_update_unchanged_cycle(self) -> None:
        config = load_config()
        storage = Storage(config)
        # 清空 table（避免殘留資料干擾）
        with storage._conn.cursor() as c:  # noqa: SLF001
            c.execute("TRUNCATE TABLE anime_schedule")
        storage._conn.commit()  # noqa: SLF001

        record = AnimeScheduleRecord(
            title="整合測試動畫", episode="01",
            air_time=datetime(2025, 1, 1, 22, 0),
        )
        assert storage.upsert_records([record]) == UpsertStats(inserted=1)

        # 相同內容 → unchanged
        assert storage.upsert_records([record]) == UpsertStats(unchanged=1)

        # 變更 air_time → update
        updated = AnimeScheduleRecord(
            title="整合測試動畫", episode="01",
            air_time=datetime(2025, 1, 1, 23, 0),
        )
        assert storage.upsert_records([updated]) == UpsertStats(updated=1)

        # 驗證 session 時區
        with storage._conn.cursor() as c:  # noqa: SLF001
            c.execute("SELECT @@session.time_zone")
            row = c.fetchone()
        assert row[0] == "+08:00"
        storage.close()
