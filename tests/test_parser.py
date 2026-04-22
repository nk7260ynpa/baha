"""parser 模組的單元測試（依真實首頁 DOM 重寫）。

涵蓋 spec ``anime-schedule-scraper`` Requirement 2 全部 scenario：

* 正常解析：新 fixture 回傳 >= 10 筆，週一至週日皆至少一筆。
* 無法辨識的 day-title：整段 day-list 略過並 WARN。
* 卡片結構不完整：僅該張卡片略過，同 day-list 其他卡片正常回傳。
* HH:MM 不合法：僅該卡片略過並 WARN。
* 片名與集數清洗：``strip()``、「第 N 集」→ ``"N"``、「特別篇」保留。
* 解析失敗：空字串或無 ``.programlist-wrap`` 的 HTML 回傳 ``[]`` 並記 ERROR。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from baha.parser import ScheduleCard, parse_schedule

_FIXTURE = Path(__file__).parent / "fixtures" / "animeList_sample.html"
_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


def _load_fixture() -> str:
    """讀取新 DOM 結構的離線樣本 HTML。"""
    return _FIXTURE.read_text(encoding="utf-8")


class TestParseScheduleWithFixture:
    """以 tests/fixtures/animeList_sample.html 為輸入。"""

    def test_returns_at_least_ten_cards(self) -> None:
        cards = parse_schedule(_load_fixture())
        assert len(cards) >= 10

    def test_all_fields_valid(self) -> None:
        cards = parse_schedule(_load_fixture())
        for card in cards:
            assert isinstance(card, ScheduleCard)
            assert isinstance(card.title, str) and card.title
            assert isinstance(card.episode, str) and card.episode
            assert isinstance(card.weekday, int) and 0 <= card.weekday <= 6
            assert isinstance(card.hhmm, str)
            assert _HHMM_RE.match(card.hhmm)

    def test_every_weekday_covered(self) -> None:
        """週一至週日（0..6）每個值至少出現一次。"""
        cards = parse_schedule(_load_fixture())
        weekdays = {card.weekday for card in cards}
        assert weekdays == {0, 1, 2, 3, 4, 5, 6}


class TestParseScheduleDayTitleMapping:
    """驗證 h3.day-title 的映射與略過邏輯。"""

    def test_unknown_day_title_skips_entire_day_list(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="baha.parser")
        html = """
        <html><body>
        <div class="programlist-wrap">
          <div class="day-list">
            <h3 class="day-title">本週特別企劃</h3>
            <a class="text-anime-info" href="animeVideo.php?sn=1">
              <span class="text-anime-time">22:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">不該被回傳的卡片</p>
                <p class="text-anime-number">第 01 集</p>
              </div>
            </a>
          </div>
          <div class="day-list">
            <h3 class="day-title">週三</h3>
            <a class="text-anime-info" href="animeVideo.php?sn=2">
              <span class="text-anime-time">20:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">合法卡片</p>
                <p class="text-anime-number">第 05 集</p>
              </div>
            </a>
          </div>
        </div>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 1
        assert cards[0].title == "合法卡片"
        assert cards[0].weekday == 2
        # 至少一條 WARN 提到無法識別的 day-title
        warn_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("day-title" in msg for msg in warn_msgs)


class TestParseScheduleCardSkipping:
    """驗證單張卡片的略過條件。"""

    def test_skip_card_with_invalid_time_but_keep_siblings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="baha.parser")
        html = """
        <html><body>
        <div class="programlist-wrap">
          <div class="day-list">
            <h3 class="day-title">週一</h3>
            <a class="text-anime-info">
              <span class="text-anime-time">待定</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">時段待定</p>
                <p class="text-anime-number">第 01 集</p>
              </div>
            </a>
            <a class="text-anime-info">
              <span class="text-anime-time">25:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">超時時段</p>
                <p class="text-anime-number">第 02 集</p>
              </div>
            </a>
            <a class="text-anime-info">
              <span class="text-anime-time">22:30</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">合法卡片</p>
                <p class="text-anime-number">第 03 集</p>
              </div>
            </a>
          </div>
        </div>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 1
        assert cards[0].title == "合法卡片"
        assert cards[0].hhmm == "22:30"
        # 須有 WARN 紀錄
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_skip_card_missing_name_but_keep_siblings(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="baha.parser")
        html = """
        <html><body>
        <div class="programlist-wrap">
          <div class="day-list">
            <h3 class="day-title">週二</h3>
            <a class="text-anime-info">
              <span class="text-anime-time">20:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-number">第 01 集</p>
              </div>
            </a>
            <a class="text-anime-info">
              <span class="text-anime-time">21:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">完整卡片</p>
                <p class="text-anime-number">第 04 集</p>
              </div>
            </a>
          </div>
        </div>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 1
        assert cards[0].title == "完整卡片"
        assert cards[0].weekday == 1
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestParseScheduleTitleAndEpisodeCleaning:
    """驗證片名與集數清洗規則。"""

    def test_title_stripped_and_episode_number_cleaned(self) -> None:
        html = """
        <html><body>
        <div class="programlist-wrap">
          <div class="day-list">
            <h3 class="day-title">週四</h3>
            <a class="text-anime-info">
              <span class="text-anime-time">20:30</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">   前後有空白的片名   </p>
                <p class="text-anime-number">第 01 集</p>
              </div>
            </a>
            <a class="text-anime-info">
              <span class="text-anime-time">21:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">十二集動畫</p>
                <p class="text-anime-number">第 12 集</p>
              </div>
            </a>
            <a class="text-anime-info">
              <span class="text-anime-time">22:00</span>
              <div class="text-anime-detail">
                <p class="text-anime-name">OVA 動畫</p>
                <p class="text-anime-number">特別篇</p>
              </div>
            </a>
          </div>
        </div>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 3
        by_title = {c.title: c for c in cards}
        assert "前後有空白的片名" in by_title
        assert by_title["前後有空白的片名"].episode == "01"
        assert by_title["十二集動畫"].episode == "12"
        assert by_title["OVA 動畫"].episode == "特別篇"
        # 週四 → weekday = 3
        for card in cards:
            assert card.weekday == 3


class TestParseScheduleFailures:
    """驗證空輸入與非時刻表 HTML 的失敗路徑。"""

    def test_empty_html_returns_empty_and_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="baha.parser")
        assert parse_schedule("") == []
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_non_programlist_html_returns_empty_and_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="baha.parser")
        html = "<html><body><h1>不是時刻表</h1></body></html>"
        assert parse_schedule(html) == []
        error_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert any("programlist-wrap" in msg for msg in error_msgs)
