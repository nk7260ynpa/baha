"""parser 模組的單元測試。

涵蓋 spec ``anime-schedule-scraper`` 的 parser 相關 scenario：

* 正常解析：fixture 至少回傳 10 筆。
* 干擾區塊略過（側欄、廣告、結構不完整的卡片）。
* 片名與集數清洗（strip、「第 XX 集」→ ``"XX"``、特別篇保留）。
* 解析失敗（空 HTML、無 schedule-week 結構）回傳空清單。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from baha.parser import ScheduleCard, parse_schedule

_FIXTURE = Path(__file__).parent / "fixtures" / "animeList_sample.html"


def _load_fixture() -> str:
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
            assert len(card.hhmm) == 5 and card.hhmm[2] == ":"

    def test_skips_sidebar_and_login_hint(self) -> None:
        """側欄的 theme-list-block 與 login-hint 應被忽略。"""
        cards = parse_schedule(_load_fixture())
        titles = [c.title for c in cards]
        assert "側欄廣告測試" not in titles
        assert "結構不完整的動畫" not in titles  # 缺集數被略過

    def test_title_stripped(self) -> None:
        """fixture 中「  測試動畫・一號  」前後空白應被 strip。"""
        cards = parse_schedule(_load_fixture())
        titles = [c.title for c in cards]
        assert "測試動畫・一號" in titles

    def test_episode_number_cleaned(self) -> None:
        """「第 01 集」應被清洗為 "01"，「特別篇」應保留。"""
        cards = parse_schedule(_load_fixture())
        by_title = {c.title: c for c in cards}
        assert by_title["測試動畫・一號"].episode == "01"
        assert by_title["深夜測試少女"].episode == "特別篇"


class TestParseScheduleMinimalHtml:
    """以手寫迷你 HTML 驗證邊界條件。"""

    def test_empty_html_returns_empty_list(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.ERROR, logger="baha.parser")
        result = parse_schedule("")
        assert result == []

    def test_non_schedule_html_returns_empty_list(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="baha.parser")
        html = "<html><body><h1>不是時刻表</h1></body></html>"
        assert parse_schedule(html) == []
        # 至少 1 條 ERROR log
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_skip_card_missing_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """結構不完整的卡片應略過並記 WARN。"""
        caplog.set_level(logging.WARNING, logger="baha.parser")
        html = """
        <html><body>
        <section class="schedule-week" data-week="1">
          <div class="animate-theme-list">
            <div class="theme-list-block">
              <p class="theme-time">22:00</p>
              <p class="theme-name">完整動畫</p>
              <p class="theme-number">第 01 集</p>
            </div>
            <div class="theme-list-block">
              <p class="theme-time">23:00</p>
              <p class="theme-name">缺集數</p>
            </div>
          </div>
        </section>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 1
        assert cards[0].title == "完整動畫"
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_title_strip_and_episode_cleaning(self) -> None:
        html = """
        <html><body>
        <section class="schedule-week" data-week="3">
          <div class="animate-theme-list">
            <div class="theme-list-block">
              <p class="theme-time">20:30</p>
              <p class="theme-name">   前後有空白的片名   </p>
              <p class="theme-number">第 12 集</p>
            </div>
            <div class="theme-list-block">
              <p class="theme-time">21:00</p>
              <p class="theme-name">OVA 測試</p>
              <p class="theme-number">特別篇</p>
            </div>
          </div>
        </section>
        </body></html>
        """
        cards = parse_schedule(html)
        assert len(cards) == 2
        assert cards[0].title == "前後有空白的片名"
        assert cards[0].episode == "12"
        assert cards[0].weekday == 2  # data-week=3 → weekday=2（週三）
        assert cards[1].episode == "特別篇"

    def test_invalid_hhmm_card_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING, logger="baha.parser")
        html = """
        <html><body>
        <section class="schedule-week" data-week="1">
          <div class="animate-theme-list">
            <div class="theme-list-block">
              <p class="theme-time">亂七八糟</p>
              <p class="theme-name">時段錯誤</p>
              <p class="theme-number">第 01 集</p>
            </div>
          </div>
        </section>
        </body></html>
        """
        assert parse_schedule(html) == []
