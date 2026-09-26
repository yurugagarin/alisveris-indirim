"""Ortak yardımcılar: zaman, fiyat ayrıştırma, metin normalleştirme, JSON dosyaları."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CONFIG = os.path.join(ROOT, "config")
BERLIN = ZoneInfo("Europe/Berlin")


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_price(text) -> float | None:
    """'1.299,99 €' → 1299.99, '49,80€' → 49.8, '4.99€' → 4.99, 176 → 176.0"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text) if text > 0 else None
    m = re.search(r"\d[\d.,]*", str(text))
    if not m:
        return None
    s = m.group(0).rstrip(".,")
    if "," in s and "." in s:
        # Hangisi sondaysa ondalık ayırıcıdır
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + "." + tail if len(tail) <= 2 else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.rpartition(".")[2]) == 3):
        s = s.replace(".", "")  # binlik ayırıcı: 1.299
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def norm(text: str) -> str:
    """Eşleştirme için: küçük harf, aksan/umlaut sadeleştirme (ö→o, ß→ss)."""
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s&+]", " ", text)).strip()


def discount_pct(old: float | None, new: float | None) -> float | None:
    if not old or not new or old <= 0 or new <= 0 or new >= old:
        return None
    return round((old - new) / old * 100, 1)


def load_json(name: str, default):
    path = os.path.join(DATA, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _strip(obj, volatile):
    if isinstance(obj, dict):
        return {k: _strip(v, volatile) for k, v in obj.items() if k not in volatile}
    if isinstance(obj, list):
        return [_strip(v, volatile) for v in obj]
    return obj


def save_json(name: str, obj, out_dirs=(), volatile=("generated_at",)) -> bool:
    """data/ altına yazar; yalnızca 'volatile' alanlar dışında bir şey değiştiyse dosyayı günceller
    (gereksiz commit'leri önler). out_dirs'e (ör. _site/data) her zaman en taze hâli yazılır.
    Dönüş: data/ dosyası değişti mi."""
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    for d in out_dirs:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(text)
    path = os.path.join(DATA, name)
    old = load_json(name, None)
    if old is not None and _strip(old, set(volatile)) == _strip(json.loads(text), set(volatile)):
        return False
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True
