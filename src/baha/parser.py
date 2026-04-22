r"""HTML 解析模組。

將動畫瘋首頁（<https://ani.gamer.com.tw/>）HTML 解析為 :class:`ScheduleCard`
物件清單。真實 DOM 結構如下：

```
.programlist-wrap
  .programlist-wrap_block
    .programlist-block
      .day-list
        h3.day-title              ← 文字「週一」…「週日」
        a.text-anime-info         ← 每張卡片
          span.text-anime-time    ← "HH:MM"
          .text-anime-detail
            p.text-anime-name     ← 片名
            p.text-anime-number   ← "第 N 集" / "特別篇" 等
```

解析策略：

* 以 ``soup.select_one(".programlist-wrap")`` 為入口；找不到即 ERROR log
  HTML 前 2048 字元並回傳 ``[]``。
* ``h3.day-title`` 文字以 ``{"週一":0 … "週日":6}`` 映射，未命中的 day-list
  整段略過並記 WARN。
* 每張 ``a.text-anime-info`` 卡片逐一擷取時段 / 片名 / 集數；缺任一子節點
  或時段不符 ``^\d{2}:\d{2}$`` 即 WARN 略過該卡片，不影響同 day-list
  其他卡片。
* 片名僅做 ``strip()``；集數形如「第 N 集」抽取中間數字，其餘（「特別篇」、
  「OVA」等）保留 ``strip()`` 後原字串。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleCard:
    """時刻表卡片的結構化表示。

    Attributes:
        title: 動畫片名（已 strip）。
        episode: 集數字串，如 ``"01"``、``"特別篇"``。
        weekday: 0=週一、6=週日，對應 Python ``datetime.weekday()``。
        hhmm: ``HH:MM`` 時段字串。
    """

    title: str
    episode: str
    weekday: int
    hhmm: str


_HHMM_PATTERN = re.compile(r"^\d{2}:\d{2}$")
# 「第 01 集」「第01集」「第 1 集」皆抽取中間的核心字串（可能含空白）。
_EPISODE_NUMBER_PATTERN = re.compile(r"^第\s*(\S+)\s*集$")

_WEEKDAY_MAP: dict[str, int] = {
    "週一": 0,
    "週二": 1,
    "週三": 2,
    "週四": 3,
    "週五": 4,
    "週六": 5,
    "週日": 6,
}


def _clean_episode(raw: str) -> str:
    """清洗集數字串。

    規則：

    * 「第 N 集」→ 取中間群組並去除內部空白（``"第 01 集"`` → ``"01"``）。
    * 其餘（「特別篇」「OVA」等）→ 保留 ``strip()`` 後原字串。
    """
    text = raw.strip()
    match = _EPISODE_NUMBER_PATTERN.match(text)
    if match:
        core = match.group(1)
        return re.sub(r"\s+", "", core)
    return text


def _extract_text(parent: Tag, selector: str) -> Optional[str]:
    """從 ``parent`` 底下以 CSS selector 抓第一個元素的文字。

    找不到元素時回傳 ``None``；元素存在則回傳原始文字（未 strip）。
    """
    found = parent.select_one(selector)
    if found is None:
        return None
    return found.get_text(strip=False)


def _parse_card(weekday: int, card: Tag) -> Optional[ScheduleCard]:
    """解析單張 ``a.text-anime-info`` 卡片。

    結構不完整或時段不合法時回傳 ``None`` 並記 WARN。
    """
    time_raw = _extract_text(card, "span.text-anime-time")
    name_raw = _extract_text(card, "p.text-anime-name")
    number_raw = _extract_text(card, "p.text-anime-number")

    if time_raw is None or name_raw is None or number_raw is None:
        snippet = card.decode()[:200]
        logger.warning("卡片結構不完整，已略過；片段=%s", snippet)
        return None

    hhmm = time_raw.strip()
    if not _HHMM_PATTERN.match(hhmm):
        logger.warning(
            "卡片時段不合法，已略過；hhmm=%r name=%r",
            hhmm, name_raw.strip(),
        )
        return None

    title = name_raw.strip()
    episode = _clean_episode(number_raw)

    if not title or not episode:
        snippet = card.decode()[:200]
        logger.warning(
            "卡片欄位清洗後為空，已略過；title=%r episode=%r 片段=%s",
            title, episode, snippet,
        )
        return None

    return ScheduleCard(
        title=title,
        episode=episode,
        weekday=weekday,
        hhmm=hhmm,
    )


def parse_schedule(html: str) -> list[ScheduleCard]:
    """解析首頁 HTML 為 :class:`ScheduleCard` 清單。

    Args:
        html: 動畫瘋首頁 HTML 原始字串。

    Returns:
        合法卡片清單；HTML 為空或不含 ``.programlist-wrap`` 時回傳 ``[]``
        並以 ERROR 等級記錄前 2048 字元以供除錯。
    """
    if not isinstance(html, str) or html.strip() == "":
        snippet = html[:2048] if isinstance(html, str) else ""
        logger.error(
            "解析失敗：找不到 .programlist-wrap 區塊（輸入為空）；前 2048 字元=%r",
            snippet,
        )
        return []

    soup = BeautifulSoup(html, "lxml")
    wrap = soup.select_one(".programlist-wrap")
    if wrap is None:
        logger.error(
            "解析失敗：找不到 .programlist-wrap 區塊；前 2048 字元=%s",
            html[:2048],
        )
        return []

    results: list[ScheduleCard] = []
    for day_list in wrap.select(".day-list"):
        title_tag = day_list.select_one("h3.day-title")
        day_text = title_tag.get_text(strip=True) if title_tag is not None else ""
        weekday = _WEEKDAY_MAP.get(day_text)
        if weekday is None:
            logger.warning("無法識別的 day-title=%r，略過該 day-list", day_text)
            continue

        cards = day_list.select("a.text-anime-info")
        for card in cards:
            parsed = _parse_card(weekday, card)
            if parsed is not None:
                results.append(parsed)

    logger.info("parse_schedule 解析完成；合法卡片數=%d", len(results))
    return results
