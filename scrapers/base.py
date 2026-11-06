from __future__ import annotations

import time

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
REQUEST_DELAY = 1.0  # 요청 간 간격(초)
TIMEOUT = 30


class PoliteSession:
    """요청 사이에 간격을 두는 requests 세션."""

    def __init__(self, delay: float = REQUEST_DELAY):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self.delay = delay
        self._last = 0.0

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        kwargs.setdefault("timeout", TIMEOUT)
        try:
            r = self.s.request(method, url, **kwargs)
        finally:
            self._last = time.monotonic()
        r.raise_for_status()
        return r

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self._request("POST", url, **kwargs)
