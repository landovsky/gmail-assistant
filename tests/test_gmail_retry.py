"""Tests for Gmail API retry logic."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src.gmail.retry import (
    _is_retryable,
    execute_with_retry,
)


class TestIsRetryable:
    def test_socket_gaierror(self):
        assert _is_retryable(socket.gaierror("DNS resolution failed"))

    def test_connection_error(self):
        assert _is_retryable(ConnectionError("Connection refused"))

    def test_connection_reset(self):
        assert _is_retryable(ConnectionResetError("Connection reset by peer"))

    def test_timeout_error(self):
        assert _is_retryable(TimeoutError("timed out"))

    def test_os_error(self):
        assert _is_retryable(OSError("Network is unreachable"))

    def test_http_429(self):
        resp = Response({"status": 429})
        exc = HttpError(resp, b"Rate limited")
        assert _is_retryable(exc)

    def test_http_503(self):
        resp = Response({"status": 503})
        exc = HttpError(resp, b"Service unavailable")
        assert _is_retryable(exc)

    def test_http_500(self):
        resp = Response({"status": 500})
        exc = HttpError(resp, b"Internal server error")
        assert _is_retryable(exc)

    def test_http_404_not_retryable(self):
        resp = Response({"status": 404})
        exc = HttpError(resp, b"Not found")
        assert not _is_retryable(exc)

    def test_http_400_not_retryable(self):
        resp = Response({"status": 400})
        exc = HttpError(resp, b"Bad request")
        assert not _is_retryable(exc)

    def test_value_error_not_retryable(self):
        assert not _is_retryable(ValueError("bad value"))

    def test_chained_socket_error(self):
        """Exception wrapping a socket error should be retryable."""
        cause = socket.gaierror("DNS failed")
        exc = Exception("wrapper")
        exc.__cause__ = cause
        assert _is_retryable(exc)


class TestExecuteWithRetry:
    @patch("src.gmail.retry.time.sleep")
    def test_succeeds_first_try(self, mock_sleep):
        request = MagicMock()
        request.execute.return_value = {"id": "123"}

        result = execute_with_retry(request, operation="test")

        assert result == {"id": "123"}
        request.execute.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("src.gmail.retry.time.sleep")
    def test_retries_on_network_error_then_succeeds(self, mock_sleep):
        request = MagicMock()
        request.execute.side_effect = [
            socket.gaierror("DNS resolution failed"),
            {"id": "123"},
        ]

        result = execute_with_retry(request, operation="test", base_delay=1.0)

        assert result == {"id": "123"}
        assert request.execute.call_count == 2
        mock_sleep.assert_called_once_with(1.0)  # base_delay * 2^0

    @patch("src.gmail.retry.time.sleep")
    def test_retries_on_connection_error_then_succeeds(self, mock_sleep):
        request = MagicMock()
        request.execute.side_effect = [
            ConnectionError("refused"),
            {"messages": []},
        ]

        result = execute_with_retry(request, operation="test", base_delay=0.5)

        assert result == {"messages": []}
        assert request.execute.call_count == 2
        mock_sleep.assert_called_once_with(0.5)

    @patch("src.gmail.retry.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        request = MagicMock()
        request.execute.side_effect = [
            socket.gaierror("fail 1"),
            socket.gaierror("fail 2"),
            socket.gaierror("fail 3"),
            {"ok": True},
        ]

        result = execute_with_retry(request, max_retries=3, base_delay=1.0, operation="test")

        assert result == {"ok": True}
        assert request.execute.call_count == 4
        assert mock_sleep.call_args_list == [
            ((1.0,),),  # 1.0 * 2^0
            ((2.0,),),  # 1.0 * 2^1
            ((4.0,),),  # 1.0 * 2^2
        ]

    @patch("src.gmail.retry.time.sleep")
    def test_gives_up_after_max_retries(self, mock_sleep):
        request = MagicMock()
        dns_error = socket.gaierror("DNS resolution failed")
        request.execute.side_effect = dns_error

        with pytest.raises(socket.gaierror, match="DNS resolution failed"):
            execute_with_retry(request, max_retries=2, base_delay=0.1, operation="test")

        assert request.execute.call_count == 3  # 1 initial + 2 retries

    @patch("src.gmail.retry.time.sleep")
    def test_does_not_retry_client_error(self, mock_sleep):
        request = MagicMock()
        resp = Response({"status": 404})
        request.execute.side_effect = HttpError(resp, b"Not found")

        with pytest.raises(HttpError):
            execute_with_retry(request, max_retries=3, operation="test")

        request.execute.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("src.gmail.retry.time.sleep")
    def test_retries_on_http_503(self, mock_sleep):
        request = MagicMock()
        resp = Response({"status": 503})
        request.execute.side_effect = [
            HttpError(resp, b"Service unavailable"),
            {"result": "ok"},
        ]

        result = execute_with_retry(request, operation="test", base_delay=1.0)

        assert result == {"result": "ok"}
        assert request.execute.call_count == 2

    @patch("src.gmail.retry.time.sleep")
    def test_retries_on_http_429(self, mock_sleep):
        request = MagicMock()
        resp = Response({"status": 429})
        request.execute.side_effect = [
            HttpError(resp, b"Rate limited"),
            {"result": "ok"},
        ]

        result = execute_with_retry(request, operation="test", base_delay=1.0)

        assert result == {"result": "ok"}
        assert request.execute.call_count == 2
