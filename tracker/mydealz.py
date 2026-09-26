"""mydealz.de kaynakları: kategori RSS akışları ve mağaza/anahtar kelime listeleri.

- RSS (/rss/gruppe/<kategori>, /rss/alles, /rss/trending): mağaza adı ve fiyat verir, eski fiyat vermez.
- Arama/mağaza sayfası (/search/deals?merchant-id=..): her fırsat için yapılandırılmış JSON
  (fiyat, "nextBestPrice" = fiyat karşılaştırmasındaki bir sonraki en iyi fiyat, kategori, tarih).
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from .util import discount_pct, iso, norm, parse_price

BASE = "https://www.mydealz.de"
NS = {"pepper": "http://www.pepper.com/rss", "media": "http://search.yahoo.com/mrss/"}

THREAD_RE = re.compile(r"data-vue3='(\{\"name\":\"ThreadMainListItemNormalizer\".*?)'", re.S)
LOW30_RE = re.compile(
    r"(?:niedrigste[rn]?\s+(?:Gesamt)?preis\s+(?:der\s+)?(?:letzten\s+)?30\s+Tage|30[- ]Tage[- ](?:Best|Tiefst)preis)"
    r"[^0-9]{0,40}(\d[\d.,]*)", re.I)
STATT_RE = re.compile(r"(?:statt|UVP|PVG|vorher)\s*:?\s*(\d[\d.,]*)\s*(?:€|EUR|Euro)", re.I)
PCT_RE = re.compile(r"-\s?(\d{2})\s?%")


def listing_url(merchant_id=None, query=None, page=1) -> str:
    if merchant_id:
        u = f"{BASE}/search/deals?merchant-id={merchant_id}&sortBy=new"
    else:
        u = f"{BASE}/search?q={quote_plus(query)}&sortBy=new"
    return u + (f"&page={page}" if page > 1 else "")


def parse_listing(text: str) -> list[dict]:
    out = []
    for raw in THREAD_RE.findall(text):
        try:
            out.append(json.loads(html.unescape(raw))["props"]["thread"])
        except (ValueError, KeyError):
            continue
    return out


def image_url(img: dict | None) -> str | None:
    if not img or not img.get("path") or not img.get("name"):
        return None
    return f"https://static.mydealz.de/{img['path']}/{img['name']}/re/300x300/qt/60/{img['name']}.jpg"


def thread_to_raw(th: dict) -> dict:
    """Arama JSON'undaki bir 'thread' → ortak ham fırsat sözlüğü."""
    merchant = th.get("merchant") or {}
    group = th.get("mainGroup") or {}
    price = parse_price(th.get("price"))
    old = parse_price(th.get("nextBestPrice"))
    title = th.get("title") or ""
    return {
        "thread_id": str(th.get("threadId")),
        "title": title,
        "merchant": merchant.get("merchantName"),
        "merchant_id": merchant.get("merchantId"),
        "category": group.get("threadGroupName"),
        "price": price,
        "old_price": old if old and price and old > price else None,
        "percentage": th.get("percentage") or None,
        "discount_type": th.get("discountType"),
        "published_at": iso(datetime.fromtimestamp(th["publishedAt"], timezone.utc)) if th.get("publishedAt") else None,
        "expired": bool(th.get("isExpired")) or th.get("status") not in (None, "Activated"),
        "type": th.get("type"),
        "local": bool(th.get("isLocal")),
        "temperature": th.get("temperature"),
        "url": f"{BASE}/deals/{th.get('titleSlug')}-{th.get('threadId')}",
        "image": image_url(th.get("mainImage")),
        "description": "",
    }


def parse_rss(text: str) -> list[dict]:
    root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    out = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        m = re.search(r"-(\d+)$", link)
        if not m:
            continue
        title = re.sub(r"^-?\d+°\s*-\s*", "", (item.findtext("title") or "").strip())
        merch = item.find("pepper:merchant", NS)
        desc_html = item.findtext("description") or ""
        desc = html.unescape(re.sub(r"<[^>]+>", " ", desc_html))
        pub = item.findtext("pubDate")
        try:
            published = iso(parsedate_to_datetime(pub)) if pub else None
        except (TypeError, ValueError):
            published = None
        thumb = item.find("media:content", NS)
        price = parse_price(merch.get("price")) if merch is not None else None
        old = None
        for rx_src in (title, desc):
            sm = STATT_RE.search(rx_src)
            if sm:
                old = parse_price(sm.group(1))
                break
        pct = None
        pm = PCT_RE.search(title)
        if pm:
            pct = float(pm.group(1))
        out.append({
            "thread_id": m.group(1),
            "title": title,
            "merchant": merch.get("name") if merch is not None else None,
            "merchant_id": None,
            "category": (item.findtext("category") or "").strip() or None,
            "price": price,
            "old_price": old if old and price and old > price else None,
            "percentage": pct,
            "discount_type": None,
            "published_at": published,
            "expired": False,
            "type": "Deal",
            "local": False,
            "temperature": None,
            "url": link,
            "image": (thumb.get("url").replace("/re/150x150/qt/55/", "/re/300x300/qt/60/") if thumb is not None else None),
            "description": desc[:1500],
        })
    return out


def low30_from_text(*texts) -> float | None:
    for t in texts:
        m = LOW30_RE.search(t or "")
        if m:
            return parse_price(m.group(1))
    return None


class StoreMatcher:
    """config/stores.yaml'daki bir mağazaya ait mi?"""

    def __init__(self, cfg: dict):
        self.name = cfg["name"]
        self.merchant_id = cfg.get("mydealz_merchant_id")
        self.merchants = {norm(m) for m in (cfg.get("merchants") or [self.name])}
        self.include = [norm(x) for x in cfg.get("include") or []]
        self.exclude = [norm(x) for x in cfg.get("exclude") or []]
        self.search = cfg.get("search") or self.name
        self.pages = int(cfg.get("pages") or 1)

    def matches(self, raw: dict) -> bool:
        mid = raw.get("merchant_id")
        ok = (self.merchant_id and mid and int(mid) == int(self.merchant_id)) or \
             (norm(raw.get("merchant") or "") in self.merchants)
        if not ok:
            return False
        t = norm(raw.get("title") or "")
        if self.include and not any(x in t for x in self.include):
            return False
        if any(x in t for x in self.exclude):
            return False
        return True


def to_deal(raw: dict, store: str, threshold: float, source_label: str) -> dict | None:
    """Ham fırsat → ana sayfa kartı. Eşiği geçmiyorsa None."""
    if raw.get("expired") or raw.get("type") not in (None, "Deal"):
        return None
    disc = discount_pct(raw.get("old_price"), raw.get("price"))
    price, old = raw.get("price"), raw.get("old_price")
    if disc is None and raw.get("percentage") and not price:
        # "%40 Rabatt auf ..." gibi fiyatsız yüzde indirimleri
        disc, old = float(raw["percentage"]), None
    if disc is None or disc < threshold:
        return None
    deal = {
        "id": "md-" + raw["thread_id"],
        "title": raw["title"],
        "store": store,
        "category": raw.get("category"),
        "price": price,
        "old_price": old,
        "discount": round(disc, 1),
        "url": raw["url"],
        "image": raw.get("image"),
        "published_at": raw.get("published_at"),
        "source": "mydealz",
        "source_label": source_label + (" · yerel mağaza" if raw.get("local") else ""),
        "suspicious": False,
        "suspicious_reason": None,
    }
    low30 = low30_from_text(raw.get("title"), raw.get("description"))
    if low30 and price:
        real = discount_pct(low30, price) or 0
        if real < threshold:
            deal["suspicious"] = True
            deal["suspicious_reason"] = (f"Son 30 günün en düşük fiyatı {low30:.2f} € — buna göre indirim "
                                         f"yalnızca %{real:.0f}")
    return deal
