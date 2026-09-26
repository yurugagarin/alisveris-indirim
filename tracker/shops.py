"""Mağaza kaynakları: IKEA / Zara ürün sayfaları (yalnızca istek listesi için) ve IKEA Circular Hub."""
from __future__ import annotations

import html
import json
import re
import uuid
from datetime import datetime, timezone

import requests

from .net import Blocked, Http
from .util import discount_pct, iso, parse_price


def _meta(text: str, prop: str) -> str | None:
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), text)
    return html.unescape(m.group(1)) if m else None


def _jsonld_products(text: str) -> list[dict]:
    out = []
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', text, re.S):
        try:
            d = json.loads(raw.strip())
        except ValueError:
            continue
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and x.get("@type") == "Product":
                out.append(x)
    return out


def check_ikea(http: Http, url: str) -> dict:
    """IKEA ürün sayfası → {price, old_price, shop_lowest_30d, name, image}.

    IKEA indirimli üründe "Vorher: X €" gösterir. Almanya'da PAngV §11 gereği bu "vorher" fiyatı
    indirimden önceki son 30 günün en düşük fiyatıdır; bu yüzden mağaza beyanı olarak kullanılır."""
    t = http.get(url).text
    price = None
    m = re.search(r'data-product-price="([\d.]+)"', t)
    if m:
        price = float(m.group(1))
    prods = _jsonld_products(t)
    if price is None:
        for p in prods:
            offers = p.get("offers") or {}
            price = parse_price(offers.get("lowPrice") or offers.get("price"))
            if price:
                break
    if price is None:
        raise ValueError("fiyat sayfada bulunamadı (sayfa yapısı değişmiş olabilir)")
    prev = None
    m = re.search(r'"previousPriceText"\s*:\s*"([^"]+)"', t)
    if m:
        prev = parse_price(m.group(1))
    low30 = None
    m = re.search(r'(?:[Nn]iedrigste[rn]? Preis[^"<]{0,40}30 Tage[^"<\d]{0,30}|"lowestPrice30Days"\s*:\s*"?)(\d[\d.,]*)', t)
    if m:
        low30 = parse_price(m.group(1))
    if prev and not low30:
        low30 = prev  # PAngV §11: "Vorher" = son 30 günün en düşüğü
    name = _meta(t, "og:title") or (prods[0].get("name") if prods else None)
    return {
        "price": price,
        "old_price": prev if prev and prev > price else None,
        "shop_lowest_30d": low30,
        "name": name,
        "image": _meta(t, "og:image"),
    }


def check_zara(http: Http, url: str) -> dict:
    """Zara / Zara Home ürün sayfası. Akamai bot koruması varsa http.Blocked fırlatır."""
    t = http.get(url).text
    prods = _jsonld_products(t)
    price = None
    for p in prods:
        offers = p.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = parse_price(offers.get("price") or offers.get("lowPrice"))
        if price:
            break
    if price is None:
        m = re.search(r'"price"\s*:\s*(\d{3,7})\b', t)  # Zara JSON'da sent cinsinden
        if m:
            price = int(m.group(1)) / 100
    if price is None:
        raise ValueError("fiyat sayfada bulunamadı")
    old = None
    m = re.search(r'"oldPrice"\s*:\s*(\d{3,7})\b', t)
    if m:
        old = int(m.group(1)) / 100
    return {"price": price, "old_price": old if old and old > price else None, "shop_lowest_30d": None,
            "name": _meta(t, "og:title"), "image": _meta(t, "og:image")}


CIRCULAR_API = "https://web-api.ikea.com/circular/circular-asis/offers/grouped/search"
CIRCULAR_PAGE = "https://www.ikea.com/de/de/second-hand/buy-from-ikea/"


def _uuid7_time(u: str | None) -> str | None:
    """Circular Hub ilan UUID'leri v7: ilk 48 bit ilan oluşturulma zamanı (ms)."""
    try:
        x = uuid.UUID(u)
        if x.version != 7:
            return None
        return iso(datetime.fromtimestamp((x.int >> 80) / 1000, timezone.utc))
    except (TypeError, ValueError):
        return None


def fetch_circular(http: Http, stores: dict[str, str], threshold: float, max_items: int) -> tuple[list[dict], int]:
    """Berlin IKEA mağazalarının ikinci el / Fundgrube ilanları. Dönüş: (fırsatlar, toplam ilan)."""
    deals, total, page, pages = [], 0, 0, 1
    ids = ",".join(stores)
    headers = {"Accept": "application/json", "Origin": "https://www.ikea.com", "Referer": CIRCULAR_PAGE}
    sizes = [64, 48, 32, 16]  # API'nin kabul ettiği en büyük sayfa boyutunu bul (100 → HTTP 400)
    while page < pages and page < 25:
        try:
            r = http.get(f"{CIRCULAR_API}?languageCode=de&size={sizes[0]}&page={page}&storeIds={ids}", headers=headers)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400 and page == 0 and len(sizes) > 1:
                sizes.pop(0)
                continue
            raise
        d = r.json()
        pages = int(d.get("totalPages") or 1)
        total = int(d.get("totalElements") or 0)
        for g in d.get("content") or []:
            orig = parse_price(g.get("originalPrice"))
            branch = stores.get(str(g.get("storeId")), str(g.get("storeId")))
            for o in g.get("offers") or []:
                price = parse_price(o.get("price"))
                disc = discount_pct(orig, price)
                if disc is None or disc < threshold:
                    continue
                extra = " · ".join(x for x in (o.get("productConditionTitle"), o.get("reasonDiscount")) if x)
                deals.append({
                    "id": f"ikea-circ-{o.get('offerNumber') or o.get('id')}",
                    "title": f"{g.get('title', '')} – {o.get('description') or g.get('description') or ''}".strip(" –"),
                    "store": "IKEA Fundgrube Berlin",
                    "category": "İkinci el / Fundgrube",
                    "price": price,
                    "old_price": orig,
                    "discount": disc,
                    "url": CIRCULAR_PAGE,
                    "image": g.get("heroImage"),
                    "published_at": _uuid7_time(o.get("offerUuid")),
                    "source": "ikea-circular",
                    "source_label": f"IKEA {branch}" + (f" · {extra}" if extra else ""),
                    "suspicious": False,
                    "suspicious_reason": None,
                })
        page += 1
    deals.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return deals[:max_items], total


__all__ = ["Blocked", "check_ikea", "check_zara", "fetch_circular"]
