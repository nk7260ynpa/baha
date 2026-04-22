"""HTTP 抓取模組。

對動畫瘋時刻表 URL 發送 GET 請求，遇非 2xx 或連線錯誤時以指數退避
（2、4、8 秒）最多重試 3 次（合計最多 4 次請求）。所有重試失敗時拋
:class:`FetchError`。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from requests import Session

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://ani.gamer.com.tw/animeList.php"
USER_AGENT = "baha-schedule-scraper/0.1 (+https://github.com/local/baha)"
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS: tuple[int, ...] = (2, 4, 8)
_REQUEST_TIMEOUT_SECONDS = 10


class FetchError(RuntimeError):
    """抓取錯誤：重試策略完全失敗時拋出。"""


def _build_session(session: Optional[Session]) -> Session:
    """建立或取用 Session，並確保 User-Agent header 含識別字串。"""
    sess = session if session is not None else requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    return sess


def fetch_schedule_html(
    url: str = DEFAULT_URL,
    session: Optional[Session] = None,
) -> str:
    """抓取時刻表 HTML。

    Args:
        url: 目標 URL，預設為 :data:`DEFAULT_URL`。
        session: 可選的 ``requests.Session``；未提供時自建一個。

    Returns:
        UTF-8 解碼後的 HTML 字串。

    Raises:
        FetchError: 所有重試皆失敗時拋出。
    """
    sess = _build_session(session)
    last_status: Optional[int] = None
    last_exc: Optional[BaseException] = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        start_ns = time.monotonic_ns()
        try:
            response = sess.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            logger.warning(
                "抓取發生連線錯誤，第 %d 次嘗試；error=%r",
                attempt, exc,
            )
        else:
            elapsed_ms = (time.monotonic_ns() - start_ns) // 1_000_000
            status = response.status_code
            if 200 <= status < 300:
                text = response.text
                logger.info(
                    "抓取成功；status=%d size=%d bytes elapsed=%d ms",
                    status, len(text.encode("utf-8")), elapsed_ms,
                )
                logger.debug(
                    "抓取 DEBUG：url=%s status=%d size=%d",
                    url, status, len(text.encode("utf-8")),
                )
                return text
            last_status = status
            logger.warning(
                "抓取回應非 2xx，第 %d 次嘗試；status=%d elapsed=%d ms",
                attempt, status, elapsed_ms,
            )

        # 若還有重試機會則退避等待。
        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_SECONDS[attempt - 1]
            logger.info("將在 %d 秒後進行第 %d 次重試", delay, attempt + 1)
            time.sleep(delay)

    # 全部失敗。
    if last_exc is not None:
        logger.error("抓取全部失敗；最後錯誤=%r", last_exc)
        raise FetchError(f"抓取失敗：{last_exc!r}") from last_exc
    logger.error("抓取全部失敗；最後狀態碼=%s", last_status)
    raise FetchError(f"抓取失敗：最後狀態碼={last_status}")
