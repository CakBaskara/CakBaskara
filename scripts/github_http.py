"""Retry idempotent GitHub GET requests with bounded exponential backoff."""
import os
import random
import time

import requests

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def api_headers(accept="application/vnd.github+json"):
    """REST API headers, authenticated when GITHUB_TOKEN is available."""
    headers = {"Accept": accept, "User-Agent": "profile-art-bot"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _is_retryable(response):
    if response.status_code in RETRYABLE_STATUS:
        return True
    return response.status_code == 403 and (
        response.headers.get("Retry-After") is not None
        or response.headers.get("X-RateLimit-Remaining") == "0"
    )


def _delay(response, attempt):
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        if response.headers.get("X-RateLimit-Remaining") == "0":
            try:
                reset = float(response.headers["X-RateLimit-Reset"])
                return min(30.0, max(0.0, reset - time.time()))
            except (KeyError, ValueError):
                pass
    return min(8.0, 2.0 ** attempt) + random.uniform(0.0, 0.25)


def get(url, *, headers=None, timeout=20, attempts=4):
    """GET a URL, retrying only connection failures and temporary responses."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error = None
    for attempt in range(attempts):
        response = None
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if not _is_retryable(response):
                response.raise_for_status()
                return response
            response.raise_for_status()
        except requests.HTTPError as error:
            if response is None or not _is_retryable(response):
                raise
            last_error = error
        except requests.RequestException as error:
            last_error = error

        if attempt + 1 < attempts:
            time.sleep(_delay(response, attempt))

    raise last_error
