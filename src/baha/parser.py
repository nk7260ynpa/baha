"""HTML 解析模組。

將動畫瘋新番時刻表 HTML 解析為 :class:`ScheduleCard` 物件清單。

解析策略：

* 僅在 ``.schedule-week .animate-theme-list`` 範圍內搜尋卡片，避開側欄、
  廣告、登入提示等含類似 class 但非時刻表的區塊。
* 透過 ``.schedule-week[data-week]`` 取得週幾（1=週一 … 7=週日，內部減一
  轉為 Python weekday 慣例 0..6）。
* 片名透過 ``strip()`` 去除前後空白；集數若形如「第 01 集」則抽取出 ``"01"``，
  若為「特別篇」等非數字標籤則原樣保留。
* 結構不完整（缺任一必要欄位）的卡片略過並以 WARN 記錄前 200 字原始片段；
  輸入 HTML 完全不像時刻表時回傳空清單並以 ERROR 記錄前 2048 字以供除錯。
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
# 「第 01 集」「第01集」「第 1 集」皆抽取中間的數字字串。
_EPISODE_NUMBER_PATTERN = re.compile(r"^第\s*(\d+)\s*集$")


def _clean_episode(raw: str) -> str:
    """清洗集數字串：「第 XX 集」→ ``"XX"``；特別篇／OVA 等原樣保留。"""
    text = raw.strip()
    match = _EPISODE_NUMBER_PATTERN.match(text)
    if match:
        return match.group(1)
    return text


def _extract_text(tag: Optional[Tag], selector: str) -> Optional[str]:
    """從 ``tag`` 之下以 CSS selector 抓第一個元素的文字，找不到回傳 None。"""
    if tag is None:
        return None
    found = tag.select_one(selector)
    if found is None:
        return None
    return found.get_text(strip=False)


def _parse_weekday(section: Tag) -> Optional[int]:
    """從 ``.schedule-week[data-week]`` 取得 1..7，轉為 0..6；失敗回傳 None。"""
    raw = section.get("data-week")
    if raw is None:
        return None
    try:
        number = int(str(raw).strip())
    except ValueError:
        return None
    if not 1 <= number <= 7:
        return None
    return number - 1


def _parse_card(section_weekday: int, card: Tag) -> Optional[ScheduleCard]:
    """解析單張卡片；結構不完整回傳 None 並記 WARN。"""
    title_raw = _extract_text(card, ".theme-name")
    number_raw = _extract_text(card, ".theme-number")
    time_raw = _extract_text(card, ".theme-time")

    if title_raw is None or number_raw is None or time_raw is None:
        snippet = card.decode()[:200]
        logger.warning("卡片結構不完整，已略過；片段=%r", snippet)
        return None

    title = title_raw.strip()
    episode = _clean_episode(number_raw)
    hhmm = time_raw.strip()

    if not title or not episode or not _HHMM_PATTERN.match(hhmm):
        snippet = card.decode()[:200]
        logger.warning(
            "卡片欄位不合法已略過；title=%r episode=%r hhmm=%r 片段=%s",
            title, episode, hhmm, snippet,
        )
        return None

    return ScheduleCard(
        title=title,
        episode=episode,
        weekday=section_weekday,
        hhmm=hhmm,
    )


def parse_schedule(html: str) -> list[ScheduleCard]:
    """解析時刻表 HTML 為 :class:`ScheduleCard` 清單。

    Args:
        html: 時刻表 HTML 原始字串。

    Returns:
        合法卡片清單；若 HTML 為空或明顯不符合時刻表結構則回傳 ``[]``。
    """
    if not isinstance(html, str) or html.strip() == "":
        logger.error("解析失敗：輸入 HTML 為空；前 2048 字元=%r", html[:2048] if isinstance(html, str) else "")
        return []

    soup = BeautifulSoup(html, "lxml")
    sections = soup.select(".schedule-week")

    if not sections:
        logger.error(
            "解析失敗：找不到 .schedule-week 區塊；前 2048 字元=%s",
            html[:2048],
        )
        return []

    results: list[ScheduleCard] = []
    for section in sections:
        weekday = _parse_weekday(section)
        if weekday is None:
            logger.warning("schedule-week 缺少合法 data-week，略過整個 section")
            continue
        cards = section.select(".animate-theme-list .theme-list-block")
        for card in cards:
            parsed = _parse_card(weekday, card)
            if parsed is not None:
                results.append(parsed)

    logger.info("parse_schedule 解析完成；合法卡片數=%d", len(results))
    return results
