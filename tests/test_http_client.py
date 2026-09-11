"""Verify GitHub reads retry temporary failures without hiding permanent errors."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import github_http


def response(status, headers=None):
    item = requests.Response()
    item.status_code = status
    item.headers.update(headers or {})
    item.url = "https://github.com/test"
    return item


class GitHubHttpTests(unittest.TestCase):
    @patch("github_http.time.sleep")
    @patch("github_http.requests.get")
    def test_temporary_failures_are_retried(self, request, sleep):
        expected = response(200)
        request.side_effect = [requests.Timeout("slow"), response(503), expected]
        self.assertEqual(github_http.get("https://github.com/test"), expected)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("github_http.time.sleep")
    @patch("github_http.requests.get", return_value=response(404))
    def test_permanent_client_error_is_not_retried(self, request, sleep):
        with self.assertRaises(requests.HTTPError):
            github_http.get("https://github.com/missing")
        request.assert_called_once()
        sleep.assert_not_called()

    @patch("github_http.time.sleep")
    @patch("github_http.requests.get")
    def test_retry_after_is_bounded(self, request, sleep):
        request.side_effect = [response(429, {"Retry-After": "120"}), response(200)]
        github_http.get("https://github.com/test")
        sleep.assert_called_once_with(30.0)


if __name__ == "__main__":
    unittest.main()
