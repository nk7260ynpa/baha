"""pipeline 模組的單元測試。

以 mock fetcher（回傳 fixture HTML）與真實 parser 驗證：

* 正常流程：回傳 >= 2 筆 ``AnimeScheduleRecord``。
* 部分解析錯誤不中斷：fixture 中的 1 筆結構不完整卡片被略過，其餘
  正常處理。
* 紀錄筆數不足：mock 出一個僅回傳 1 張卡片的 fixture → ``ScrapeEmptyError``。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from baha.parser import ScheduleCard
from baha.pipeline import ScrapeEmptyError, run_once
from baha.storage import AnimeScheduleRecord

_FIXTURE = Path(__file__).parent / "fixtures" / "animeList_sample.html"


def test_run_once_returns_records_with_fixture() -> None:
    html = _FIXTURE.read_text(encoding="utf-8")

    def fake_fetcher(url: str) -> str:
        return html

    now = datetime(2025, 4, 22, 10, 0)  # 週二
    records = run_once(now, fetcher=fake_fetcher)

    # fixture 有 12 筆合法動畫（1 筆缺集數 + 1 筆側欄被 parser 略過）
    assert len(records) >= 10
    for record in records:
        assert isinstance(record, AnimeScheduleRecord)
        assert isinstance(record.title, str) and record.title
        assert isinstance(record.episode, str) and record.episode
        assert isinstance(record.air_time, datetime)


def test_run_once_tolerates_parser_skips_and_continues() -> None:
    """fixture 中的結構不完整卡片被略過，流程仍回傳其餘合法紀錄。"""
    html = _FIXTURE.read_text(encoding="utf-8")
    records = run_once(datetime(2025, 4, 22, 10, 0), fetcher=lambda _u: html)
    titles = [r.title for r in records]
    assert "結構不完整的動畫" not in titles
    assert "測試動畫・一號" in titles


def test_run_once_raises_when_records_fewer_than_two() -> None:
    html = "<doesn't matter>"

    def fake_parser(_html: str) -> list[ScheduleCard]:
        return [ScheduleCard(title="孤狼", episode="01", weekday=0, hhmm="22:00")]

    with pytest.raises(ScrapeEmptyError):
        run_once(
            datetime(2025, 4, 22, 10, 0),
            fetcher=lambda _u: html,
            parser=fake_parser,
        )


def test_run_once_raises_when_parser_returns_empty() -> None:
    with pytest.raises(ScrapeEmptyError):
        run_once(
            datetime(2025, 4, 22, 10, 0),
            fetcher=lambda _u: "",
            parser=lambda _html: [],
        )


def test_run_once_skips_card_with_invalid_time_but_proceeds() -> None:
    """若某張卡片的 hhmm 非法，to_air_datetime 會拋 ValueError，pipeline 應略過該筆。"""
    def fake_parser(_html: str) -> list[ScheduleCard]:
        return [
            ScheduleCard(title="正常", episode="01", weekday=1, hhmm="22:00"),
            ScheduleCard(title="時間亂填", episode="01", weekday=1, hhmm="99:99"),
            ScheduleCard(title="也正常", episode="02", weekday=2, hhmm="23:00"),
        ]

    records = run_once(
        datetime(2025, 4, 22, 10, 0),
        fetcher=lambda _u: "ignored",
        parser=fake_parser,
    )
    titles = [r.title for r in records]
    assert titles == ["正常", "也正常"]
