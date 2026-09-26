"""Nazik HTTP istemcisi: tarayıcı başlıkları, zaman aşımı, alan adı başına bekleme, istek sayacı."""
from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


class Blocked(Exception):
    """Sitenin bot koruması isteği engelledi."""


class Http:
    def __init__(self, delay: float = 1.0, timeout: float = 20):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        })
        self.delay = delay
        self.timeout = timeout
        self.count = 0
        self._last: dict[str, float] = {}

    def get(self, url: str, **kw) -> requests.Response:
        host = urlparse(url).netloc
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.count += 1
        try:
            r = self.s.get(url, timeout=self.timeout, **kw)
        finally:
            self._last[host] = time.monotonic()
        if r.status_code in (403, 429) or looks_like_bot_wall(r):
            raise Blocked(f"{host}: bot koruması (HTTP {r.status_code})")
        r.raise_for_status()
        return r


def looks_like_bot_wall(r: requests.Response) -> bool:
    ct = r.headers.get("content-type", "")
    if "html" not in ct:
        return False
    head = r.text[:4000]
    return ("bm-verify" in head or "_Incapsula_Resource" in head or "cf-chl-" in head
            or ("Just a moment" in head and "cloudflare" in head.lower())
            or ("captcha" in head.lower() and len(r.text) < 20000))
