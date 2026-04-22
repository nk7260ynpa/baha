"""time_utils 模組的單元測試。

涵蓋 spec 中 ``to_air_datetime`` 四個 scenario：
* 同週未來時間。
* 同週已過時間（差距 > 12 小時）。
* 差距 <= 12 小時亦視為本週該日。
* 非法 ``hhmm`` 格式。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from baha.time_utils import to_air_datetime


class TestToAirDatetime:
    """``to_air_datetime`` 的規格驗證。"""

    def test_future_time_in_same_week(self) -> None:
        """同週未來時間：now=週二 10:00 → 週四 22:00 為本週週四。"""
        now = datetime(2025, 4, 22, 10, 0)  # 週二
        assert to_air_datetime(weekday=3, hhmm="22:00", now=now) == datetime(
            2025, 4, 24, 22, 0
        )

    def test_past_time_gap_over_12_hours(self) -> None:
        """同週已過且差距 > 12 小時仍回傳本週該日。

        now=週二 20:00，目標週一 22:00（差距 > 12h）→ 本週週一 22:00。
        """
        now = datetime(2025, 4, 22, 20, 0)  # 週二
        assert to_air_datetime(weekday=0, hhmm="22:00", now=now) == datetime(
            2025, 4, 21, 22, 0
        )

    def test_past_time_gap_within_12_hours(self) -> None:
        """剛過 30 分鐘（<=12 小時）同樣視為本週該日。"""
        now = datetime(2025, 4, 22, 22, 30)  # 週二
        assert to_air_datetime(weekday=1, hhmm="22:00", now=now) == datetime(
            2025, 4, 22, 22, 0
        )

    def test_invalid_hhmm_format_raises(self) -> None:
        """非法 hhmm 應拋出 ValueError 且不回傳任何 datetime。"""
        now = datetime(2025, 4, 22, 10, 0)
        with pytest.raises(ValueError):
            to_air_datetime(weekday=1, hhmm="25:00", now=now)

    @pytest.mark.parametrize(
        "bad_hhmm",
        ["", "2500", "24:00", "12:60", "ab:cd", "9:00", "12:3"],
    )
    def test_invalid_hhmm_various(self, bad_hhmm: str) -> None:
        """多種非法 hhmm 格式皆應拋出 ValueError。"""
        now = datetime(2025, 4, 22, 10, 0)
        with pytest.raises(ValueError):
            to_air_datetime(weekday=1, hhmm=bad_hhmm, now=now)

    @pytest.mark.parametrize("bad_weekday", [-1, 7, 10])
    def test_invalid_weekday_raises(self, bad_weekday: int) -> None:
        """weekday 越界應拋出 ValueError。"""
        now = datetime(2025, 4, 22, 10, 0)
        with pytest.raises(ValueError):
            to_air_datetime(weekday=bad_weekday, hhmm="20:00", now=now)

    def test_sunday_weekday_six(self) -> None:
        """週日（weekday=6）以 now=週二為基準 → 本週週日。"""
        now = datetime(2025, 4, 22, 10, 0)  # 週二
        assert to_air_datetime(weekday=6, hhmm="00:30", now=now) == datetime(
            2025, 4, 27, 0, 30
        )
