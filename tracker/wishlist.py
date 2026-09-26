"""İstek listesi: fiyat kontrolü, fiyat geçmişi, fırsat ve şüpheli indirim hesabı."""
from __future__ import annotations

import re
from datetime import timedelta

from . import mydealz
from .net import Blocked, Http
from .shops import check_ikea, check_zara
from .util import BERLIN, discount_pct, iso, norm, now_utc, parse_iso

HISTORY_DAYS = 365


def item_id(item: dict) -> str:
    return re.sub(r"\s+", "-", norm(item.get("name", "")))[:80] or "urun"


def page_kind(item: dict) -> str | None:
    url = (item.get("url") or "").lower()
    store = norm(item.get("store") or "")
    if "amazon" in store or "amazon." in url:
        return None  # Amazon asla doğrudan taranmaz
    if "ikea.com" in url:
        return "ikea"
    if "zara.com" in url or "zarahome.com" in url:
        return "zara"
    return None


class WishlistRunner:
    def __init__(self, http: Http, settings: dict, matchers: list, status, history: dict, state: dict):
        self.http = http
        self.threshold = float(settings.get("min_discount", 30))
        self.per_day = int(settings.get("product_checks_per_day", 4))
        start = int(str(settings.get("active_start", "07:00")).split(":")[0])
        end = int(str(settings.get("active_end", "23:00")).split(":")[0])
        # Günlük kontrolleri aktif saatlere eşit yay: 16 saat / 4 = 4 saatte bir (biraz tolerans)
        self.min_gap = timedelta(hours=max(1.0, (end - start) / max(1, self.per_day)) - 0.25)
        self.md_gap = timedelta(hours=float(settings.get("wishlist_mydealz_interval_hours", 2)) - 0.1)
        self.matchers = {norm(m.name): m for m in matchers}
        self.status = status
        self.history = history
        self.state = state
        self.now = now_utc()
        self.today = self.now.astimezone(BERLIN).strftime("%Y-%m-%d")
        self.page_stats = {"ikea": [0, 0, []], "zara": [0, 0, []]}  # deneme, başarı, hatalar
        self.md_stats = [0, 0, []]

    # ---- fiyat geçmişi -------------------------------------------------
    def _add_point(self, iid: str, price: float, src: str, force: bool = False):
        pts = self.history.setdefault(iid, [])
        if pts and not force:
            last = pts[-1]
            last_t = parse_iso(last["t"])
            if last["p"] == price and last_t and self.now - last_t < timedelta(hours=12):
                return
        pts.append({"t": iso(self.now), "p": price, "src": src})
        cutoff = self.now - timedelta(days=HISTORY_DAYS)
        self.history[iid] = [p for p in pts if (parse_iso(p["t"]) or self.now) >= cutoff]

    # ---- ürün sayfası --------------------------------------------------
    def _can_check_page(self, st: dict) -> tuple[bool, str]:
        pc = st.get("page_checks") or {}
        count = pc.get("count", 0) if pc.get("date") == self.today else 0
        if count >= self.per_day:
            return False, f"bugünkü {self.per_day} kontrol hakkı doldu"
        bu = parse_iso(st.get("blocked_until"))
        if bu and bu > self.now:
            return False, "mağaza engelledi; yarın yeniden denenecek"
        last = parse_iso(st.get("last_page_check"))
        if last and self.now - last < self.min_gap:
            return False, "sıradaki kontrol zamanı gelmedi"
        return True, ""

    def _check_page(self, kind: str, item: dict, st: dict, iid: str) -> str:
        """Dönüş: 'ok' | 'blocked' | 'error' | 'waiting'"""
        ok, why = self._can_check_page(st)
        if not ok:
            if st.get("blocked_until") and (parse_iso(st["blocked_until"]) or self.now) > self.now:
                return "blocked"
            return "waiting"
        pc = st.get("page_checks") or {}
        st["page_checks"] = {"date": self.today, "count": (pc.get("count", 0) if pc.get("date") == self.today else 0) + 1}
        st["last_page_check"] = iso(self.now)
        stats = self.page_stats[kind]
        stats[0] += 1
        try:
            res = (check_ikea if kind == "ikea" else check_zara)(self.http, item["url"])
        except Blocked as e:
            st["blocked_until"] = iso(self.now + timedelta(hours=20))
            st["last_error"] = f"Engellendi: {e}"
            stats[2].append(f"{item['name']}: {e}")
            return "blocked"
        except Exception as e:  # noqa: BLE001 — her hata durum sayfasına yazılır
            st["last_error"] = f"{type(e).__name__}: {e}"[:300]
            stats[2].append(f"{item['name']}: {st['last_error']}")
            return "error"
        stats[1] += 1
        st.pop("blocked_until", None)
        st.pop("last_error", None)
        res["checked_at"] = iso(self.now)
        st["page"] = res
        self._add_point(iid, res["price"], "ikea.com" if kind == "ikea" else "zara.com")
        return "ok"

    # ---- mydealz anahtar kelime araması --------------------------------
    def _mydealz(self, item: dict, st: dict, iid: str, force: bool) -> None:
        last = parse_iso(st.get("last_mydealz"))
        if not force and last and self.now - last < self.md_gap:
            return
        query = item.get("keywords") or item["name"]
        tokens = norm(query).split()
        matcher = self.matchers.get(norm(item.get("store") or ""))
        self.md_stats[0] += 1
        try:
            threads = mydealz.parse_listing(self.http.get(mydealz.listing_url(query=query)).text)
        except Exception as e:  # noqa: BLE001
            self.md_stats[2].append(f"{item['name']}: {type(e).__name__}: {e}"[:300])
            return
        self.md_stats[1] += 1
        st["last_mydealz"] = iso(self.now)
        best = None
        cutoff = self.now - timedelta(days=30)
        for th in threads:
            raw = mydealz.thread_to_raw(th)
            title = norm(raw["title"])
            pub = parse_iso(raw.get("published_at"))
            if raw["expired"] or not raw.get("price") or not all(t in title for t in tokens):
                continue
            if pub and pub < cutoff:
                continue
            if matcher and not matcher.matches(raw):
                continue
            if best is None or raw["price"] < best["price"]:
                best = raw
        if best:
            st["mydealz_match"] = {k: best.get(k) for k in ("thread_id", "title", "price", "old_price", "url", "published_at", "image")}
            seen = st.setdefault("mydealz_seen", [])
            if best["thread_id"] not in seen:
                seen.append(best["thread_id"])
                st["mydealz_seen"] = seen[-50:]
                self._add_point(iid, best["price"], "mydealz", force=True)
        else:
            st.pop("mydealz_match", None)

    # ---- tek ürün ------------------------------------------------------
    def process(self, item: dict) -> dict:
        iid = item_id(item)
        st = self.state.setdefault(iid, {})
        kind = page_kind(item)
        page_state = None
        if kind:
            page_state = self._check_page(kind, item, st, iid)
        page = st.get("page")
        page_fresh = page and (parse_iso(page.get("checked_at")) or self.now) > self.now - timedelta(days=2)
        needs_md = kind is None or not page_fresh
        if needs_md:
            self._mydealz(item, st, iid, force=page_state in ("blocked", "error") and not st.get("last_mydealz"))
        match = st.get("mydealz_match")
        if match and (parse_iso(match.get("published_at")) or self.now) < self.now - timedelta(days=30):
            match = None

        if page_fresh:
            current, old, src = page["price"], page.get("old_price"), ("ikea.com" if kind == "ikea" else "zara.com")
        elif match:
            current, old, src = match["price"], match.get("old_price"), "mydealz"
        else:
            current, old, src = None, None, None

        if kind is None:
            status = "mydealz"
        elif st.get("blocked_until") and (parse_iso(st["blocked_until"]) or self.now) > self.now:
            status = "blocked"
        elif st.get("last_error"):
            status = "error"
        elif page:
            status = "ok"
        else:
            status = "pending"

        return self._evaluate(item, iid, st, current, old, src, status, page if page_fresh else None, match)

    def _evaluate(self, item, iid, st, current, old, src, status, page, match) -> dict:
        pts = self.history.get(iid, [])
        prices = [p["p"] for p in pts]
        c30 = self.now - timedelta(days=30)
        last30 = [p for p in pts if (parse_iso(p["t"]) or self.now) >= c30]
        # Kendi geçmişime göre referans: güncel fiyat seviyesinden ÖNCEKİ son 30 günün en düşüğü
        own_ref = None
        if current is not None and last30:
            i = len(last30)
            while i > 0 and last30[i - 1]["p"] == current:
                i -= 1
            prior = [p["p"] for p in last30[:i]]
            own_ref = min(prior) if prior else None
        shop30 = page.get("shop_lowest_30d") if page else None
        refs = [x for x in (own_ref, shop30) if x]
        ref = min(refs) if refs else None
        target = item.get("target_price")
        target = float(target) if target not in (None, "") else None

        claimed = discount_pct(old, current)
        real = discount_pct(ref, current) if ref else None
        reasons, highlight, suspicious, sus_reason = [], False, False, None
        if target is not None and current is not None and current <= target:
            highlight = True
            reasons.append(f"Hedef fiyatın ({target:.2f} €) altında")
        if real is not None and real >= self.threshold:
            highlight = True
            reasons.append(f"Son 30 günün en düşük fiyatına ({ref:.2f} €) göre %{real:.0f} ucuz")
        if claimed is not None and claimed >= self.threshold:
            if ref is not None and (real or 0) < self.threshold:
                suspicious = True
                sus_reason = (f"Gösterilen indirim %{claimed:.0f}, ama son 30 günün en düşük fiyatı "
                              f"{ref:.2f} € — gerçek indirim %{(real or 0):.0f}")
            elif src == "mydealz" and ref is None:
                highlight = True
                reasons.append(f"mydealz fiyat karşılaştırmasına göre %{claimed:.0f} ucuz (kendi geçmişimle henüz doğrulanamadı)")

        message = st.get("last_error")
        if status == "blocked":
            message = "Mağaza sayfası bot korumasıyla engellendi; fiyat mydealz aramasından izleniyor."
        elif status == "mydealz" and not match:
            message = "mydealz'da son 30 günde eşleşen aktif fırsat yok (güncel fiyat bilinmiyor)."
        elif status in ("blocked", "error") and not match:
            message = (message or "") + " · mydealz'da da eşleşen aktif fırsat yok."
        return {
            "id": iid,
            "name": item["name"],
            "store": item.get("store"),
            "url": item.get("url"),
            "image": (page or {}).get("image") or (st.get("page") or {}).get("image") or (match or {}).get("image"),
            "target_price": target,
            "current_price": current,
            "old_price": old,
            "price_source": src,
            "lowest_price": min(prices) if prices else None,
            "lowest_30d": min(p["p"] for p in last30) if last30 else None,
            "shop_lowest_30d": shop30,
            "discount": claimed,
            "real_discount": real,
            "highlight": highlight,
            "reasons": reasons,
            "suspicious": suspicious,
            "suspicious_reason": sus_reason,
            "status": status,
            "message": message,
            "mydealz_match": ({"title": match["title"], "url": match["url"], "price": match["price"]} if match else None),
            "last_checked": st.get("last_page_check") or st.get("last_mydealz"),
            "history": pts,
        }
