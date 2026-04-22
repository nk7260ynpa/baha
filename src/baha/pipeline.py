"""Pipeline：組合 fetcher → parser → time_utils → storage 的 one-shot 流程。

提供兩個入口：

* :func:`run_once`：接收 ``fetched_at``，回傳 ``AnimeScheduleRecord`` 清單。
  單元測試可 mock fetcher 與 parser 以驗證流程。
* :func:`main`：``python -m baha`` 的 CLI 進入點；讀 config、設 log、
  執行 ``run_once``、呼叫 ``Storage.upsert_records`` 並 log 結果。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from baha.config import AppConfig, load_config
from baha.fetcher import DEFAULT_URL, fetch_schedule_html
from baha.logging_setup import setup_logging
from baha.parser import ScheduleCard, parse_schedule
from baha.storage import AnimeScheduleRecord, Storage
from baha.time_utils import to_air_datetime

logger = logging.getLogger(__name__)

_MIN_RECORDS = 2


class ScrapeEmptyError(RuntimeError):
    """當抓取後產生的合法紀錄筆數 < 2 時拋出。"""


FetcherFn = Callable[..., str]
ParserFn = Callable[[str], list[ScheduleCard]]


def run_once(
    fetched_at: datetime,
    *,
    url: str = DEFAULT_URL,
    fetcher: FetcherFn = fetch_schedule_html,
    parser: ParserFn = parse_schedule,
) -> list[AnimeScheduleRecord]:
    """執行一次完整抓取 → 解析 → 時間轉換流程。

    Args:
        fetched_at: 抓取當下的 Asia/Taipei naive ``datetime``。
        url: 目標 URL，預設為動畫瘋時刻表。
        fetcher: 可替換的抓取函式（供測試注入）。
        parser: 可替換的解析函式（供測試注入）。

    Returns:
        ``AnimeScheduleRecord`` 清單。

    Raises:
        ScrapeEmptyError: 合法紀錄筆數 < 2。
    """
    logger.info("pipeline.run_once 啟動；fetched_at=%s url=%s", fetched_at.isoformat(), url)

    html = fetcher(url)
    cards = parser(html)

    records: list[AnimeScheduleRecord] = []
    skipped = 0
    for card in cards:
        try:
            air_time = to_air_datetime(card.weekday, card.hhmm, fetched_at)
        except ValueError as exc:
            skipped += 1
            logger.warning(
                "時間轉換失敗，略過卡片 title=%r episode=%r error=%r",
                card.title, card.episode, exc,
            )
            continue
        records.append(
            AnimeScheduleRecord(
                title=card.title,
                episode=card.episode,
                air_time=air_time,
            )
        )

    if skipped:
        logger.warning("共略過 %d 張時間轉換失敗的卡片", skipped)

    if len(records) < _MIN_RECORDS:
        logger.warning(
            "紀錄筆數不足 %d（實際=%d），拋出 ScrapeEmptyError",
            _MIN_RECORDS, len(records),
        )
        raise ScrapeEmptyError(
            f"合法紀錄筆數 {len(records)} < {_MIN_RECORDS}"
        )

    logger.info("pipeline.run_once 完成；合法紀錄=%d", len(records))
    return records


def main(config: Optional[AppConfig] = None) -> None:
    """CLI 進入點：讀 config → 設 log → 執行 run_once → upsert。"""
    cfg = config if config is not None else load_config()
    setup_logging(cfg)

    fetched_at = datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None)
    records = run_once(fetched_at)

    storage = Storage(cfg)
    try:
        stats = storage.upsert_records(records)
        logger.info(
            "寫入完成；inserted=%d updated=%d unchanged=%d total=%d",
            stats.inserted, stats.updated, stats.unchanged, stats.total(),
        )
    finally:
        storage.close()
