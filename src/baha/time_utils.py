"""時間工具模組。

將動畫瘋時刻表顯示的「週幾 + HH:MM」轉換為絕對 ``datetime``，規則
依 design.md D3 決定：

* 以 ``now`` 所在週為基準（週一為該週起點）。
* 不跨週推算：一律回傳該週對應週幾的 ``HH:MM`` 時間。
* 未來時間、已過 > 12 小時、已過 <= 12 小時皆採相同規則回傳本週該日。
* ``weekday`` 使用 Python ``datetime.weekday()`` 慣例：0=週一、6=週日。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_HHMM_PATTERN = re.compile(r"^(?P<hh>\d{2}):(?P<mm>\d{2})$")


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    """解析 ``HH:MM`` 字串，回傳 (hour, minute)。

    Raises:
        ValueError: 格式不符或數值越界。
    """
    if not isinstance(hhmm, str):
        raise ValueError(f"hhmm 必須為字串，實際為 {type(hhmm).__name__}")
    match = _HHMM_PATTERN.match(hhmm)
    if match is None:
        raise ValueError(f"hhmm 格式不合法（預期 HH:MM）：{hhmm!r}")
    hour = int(match.group("hh"))
    minute = int(match.group("mm"))
    if not 0 <= hour <= 23:
        raise ValueError(f"hhmm 小時越界（0-23）：{hhmm!r}")
    if not 0 <= minute <= 59:
        raise ValueError(f"hhmm 分鐘越界（0-59）：{hhmm!r}")
    return hour, minute


def to_air_datetime(weekday: int, hhmm: str, now: datetime) -> datetime:
    """將「週幾 + HH:MM」轉換為 ``now`` 所在週的絕對 ``datetime``。

    Args:
        weekday: 目標週幾；0=週一、1=週二、……、6=週日。
        hhmm: ``HH:MM`` 格式字串。
        now: 抓取當下的 ``datetime`` (Asia/Taipei naive)。

    Returns:
        ``now`` 所在週對應週幾與 ``HH:MM`` 的 ``datetime``。

    Raises:
        ValueError: ``weekday`` 越界、``hhmm`` 格式錯誤、或 ``now``
            不是 ``datetime`` 實例。
    """
    if not isinstance(now, datetime):
        raise ValueError(f"now 必須為 datetime 實例，實際為 {type(now).__name__}")
    if not isinstance(weekday, int) or isinstance(weekday, bool):
        raise ValueError(f"weekday 必須為 int，實際為 {type(weekday).__name__}")
    if not 0 <= weekday <= 6:
        raise ValueError(f"weekday 越界（0-6）：{weekday}")

    hour, minute = _parse_hhmm(hhmm)

    # 以 now 所在週的週一 00:00 為基準。
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    target = monday + timedelta(days=weekday, hours=hour, minutes=minute)
    logger.debug(
        "to_air_datetime weekday=%s hhmm=%s now=%s → %s",
        weekday, hhmm, now.isoformat(), target.isoformat(),
    )
    return target
