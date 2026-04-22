"""fetcher 模組的單元測試。

以 ``unittest.mock`` 模擬 ``requests.Session``，驗證：

* 正常抓取：單次 200 成功回傳解碼後的字串。
* 非 2xx 重試：503 後最終成功或最終失敗。
* 連線錯誤重試：ConnectionError / Timeout 重試。
* 退避時間正確（2、4、8 秒）。
* User-Agent header 含 ``baha-schedule-scraper``。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from baha.fetcher import USER_AGENT, FetchError, fetch_schedule_html


def _mock_response(status: int, text: str = "OK") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


class TestFetchScheduleHtml:
    def test_success_first_try(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response(200, "<html>ok</html>")

        with patch("baha.fetcher.time.sleep") as sleep_mock:
            result = fetch_schedule_html("https://example.test/", session=session)

        assert result == "<html>ok</html>"
        session.get.assert_called_once()
        # 成功不應睡眠
        sleep_mock.assert_not_called()

    def test_user_agent_contains_marker(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response(200, "x")

        with patch("baha.fetcher.time.sleep"):
            fetch_schedule_html("https://example.test/", session=session)

        assert "baha-schedule-scraper" in session.headers["User-Agent"]
        assert session.headers["User-Agent"] == USER_AGENT

    def test_retry_on_503_then_success(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.side_effect = [
            _mock_response(503),
            _mock_response(503),
            _mock_response(200, "final"),
        ]

        with patch("baha.fetcher.time.sleep") as sleep_mock:
            result = fetch_schedule_html("https://example.test/", session=session)

        assert result == "final"
        assert session.get.call_count == 3
        # 兩次睡眠：2 秒、4 秒
        sleep_mock.assert_any_call(2)
        sleep_mock.assert_any_call(4)
        assert sleep_mock.call_count == 2

    def test_retry_exhausted_all_503_raises_fetch_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response(503)

        with patch("baha.fetcher.time.sleep") as sleep_mock:
            with pytest.raises(FetchError):
                fetch_schedule_html("https://example.test/", session=session)

        # 4 次嘗試
        assert session.get.call_count == 4
        # 三次退避：2、4、8
        sleep_calls = [c.args[0] for c in sleep_mock.call_args_list]
        assert sleep_calls == [2, 4, 8]

    def test_retry_on_connection_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.side_effect = [
            requests.ConnectionError("net down"),
            requests.Timeout("too slow"),
            _mock_response(200, "recovered"),
        ]

        with patch("baha.fetcher.time.sleep"):
            result = fetch_schedule_html("https://example.test/", session=session)
        assert result == "recovered"
        assert session.get.call_count == 3

    def test_connection_error_exhausted_raises_fetch_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get.side_effect = requests.ConnectionError("net down")

        with patch("baha.fetcher.time.sleep") as sleep_mock:
            with pytest.raises(FetchError):
                fetch_schedule_html("https://example.test/", session=session)
        assert session.get.call_count == 4
        assert [c.args[0] for c in sleep_mock.call_args_list] == [2, 4, 8]
