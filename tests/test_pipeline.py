"""pipeline 模組的單元測試（依新 DOM 結構調整）。

以 mock fetcher + 真實 parser + fixture HTML 驗證：

* 正常流程：回傳 >= 2 筆 ``AnimeScheduleRecord``，欄位型別正確。
* 部分解析錯誤不中斷：在 fixture 後面注入一張故意缺欄位的
  ``a.text-anime-info``，parser 應跳過該卡片但流程仍回傳其餘合法紀錄。
* ``ScrapeEmptyError``：fetcher 回傳不含 ``.programlist-wrap`` 的 HTML 時，
  parser 會回傳空清單，pipeline 需因 records < 2 而拋 ``ScrapeEmptyError``。
* 時間轉換錯誤：to_air_datetime 拋 ValueError 的卡片被略過但流程續行。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from baha.parser import ScheduleCard
from baha.pipeline import ScrapeEmptyError, run_once
from baha.storage import AnimeScheduleRecord

_FIXTURE = Path(__file__).parent / "fixtures" / "animeList_sample.html"


def _load_fixture() -> str:
    """讀取真實 DOM 樣本 fixture。"""
    return _FIXTURE.read_text(encoding="utf-8")


def test_run_once_returns_records_with_fixture() -> None:
    html = _load_fixture()

    def fake_fetcher(url: str) -> str:
        return html

    now = datetime(2026, 4, 22, 10, 0)  # 週三
    records = run_once(now, fetcher=fake_fetcher)

    # 新 fixture 包含 59 張卡片，全部為合法結構，故應接近該數字；至少 >= 10。
    assert len(records) >= 10
    for record in records:
        assert isinstance(record, AnimeScheduleRecord)
        assert isinstance(record.title, str) and record.title
        assert isinstance(record.episode, str) and record.episode
        assert isinstance(record.air_time, datetime)


def test_run_once_tolerates_parser_skips_and_continues() -> None:
    """注入一張故意缺 p.text-anime-name 的卡片，parser 應跳過該卡片但流程續行。"""
    base_html = _load_fixture()
    # 將缺欄位的卡片注入第一個 day-list 結尾；parser 應跳過它。
    injected_card = (
        '<a class="text-anime-info" href="#">'
        '<span class="text-anime-time">23:59</span>'
        '<div class="text-anime-detail">'
        '<p class="text-anime-number">第 99 集</p>'
        "</div>"
        "</a>"
    )
    marker = '<div class="day-list">'
    idx = base_html.find(marker)
    assert idx >= 0, "fixture 須至少含一個 day-list"
    end_marker = "</div>"
    # 在第一個 day-list 的結束前插入（找到 <div class="day-list"> 後第一個
    # 最外層 </div> 的位置即可，這裡採近似作法：把卡片接在開始 tag 後）。
    html = base_html[: idx + len(marker)] + injected_card + base_html[idx + len(marker) :]
    del end_marker  # 未使用；保留註解意圖說明

    records = run_once(datetime(2026, 4, 22, 10, 0), fetcher=lambda _u: html)
    # 缺名字的卡片不會出現在結果中。
    titles = [r.title for r in records]
    assert "" not in titles
    # 期望與原 fixture 回傳筆數相等（缺欄位卡片被 parser 略過）。
    base_records = run_once(datetime(2026, 4, 22, 10, 0), fetcher=lambda _u: base_html)
    assert len(records) == len(base_records)


def test_run_once_raises_when_html_has_no_programlist_wrap() -> None:
    """fetcher 回傳不含 .programlist-wrap 的 HTML 時應拋 ScrapeEmptyError。"""
    html = "<html><body><h1>首頁改版了</h1></body></html>"
    with pytest.raises(ScrapeEmptyError):
        run_once(datetime(2026, 4, 22, 10, 0), fetcher=lambda _u: html)


def test_run_once_raises_when_parser_returns_single_card() -> None:
    """mock parser 只回傳 1 筆 → ScrapeEmptyError。"""
    def fake_parser(_html: str) -> list[ScheduleCard]:
        return [ScheduleCard(title="孤狼", episode="01", weekday=0, hhmm="22:00")]

    with pytest.raises(ScrapeEmptyError):
        run_once(
            datetime(2026, 4, 22, 10, 0),
            fetcher=lambda _u: "ignored",
            parser=fake_parser,
        )


def test_run_once_skips_card_with_invalid_time_but_proceeds() -> None:
    """若某張卡片的 hhmm 讓 to_air_datetime 拋 ValueError，pipeline 應略過該筆。"""
    def fake_parser(_html: str) -> list[ScheduleCard]:
        return [
            ScheduleCard(title="正常", episode="01", weekday=1, hhmm="22:00"),
            ScheduleCard(title="時間亂填", episode="01", weekday=1, hhmm="99:99"),
            ScheduleCard(title="也正常", episode="02", weekday=2, hhmm="23:00"),
        ]

    records = run_once(
        datetime(2026, 4, 22, 10, 0),
        fetcher=lambda _u: "ignored",
        parser=fake_parser,
    )
    titles = [r.title for r in records]
    assert titles == ["正常", "也正常"]
