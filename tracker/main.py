"""Pipeline giriş noktası: python -m tracker.main [--out _site/data] [--force]

1. Aktif saat kontrolü (Berlin 07:00–23:00; --force ile atlanır)
2. mydealz mağaza listeleri + kategori RSS akışları → %eşik üstü fırsatlar
3. IKEA Circular Hub (Berlin) ikinci el ilanları
4. İstek listesi: ürün sayfaları (günde ≤4 istek) / mydealz anahtar kelime araması
5. data/*.json (commit'lenir) ve --out klasörü (site için) yazılır; durum kaydı tutulur
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import timedelta

import yaml

from . import mydealz
from .net import Blocked, Http
from .shops import fetch_circular
from .util import BERLIN, CONFIG, iso, load_json, norm, now_utc, parse_iso, save_json
from .wishlist import WishlistRunner, item_id

MAX_ERRORS = 10


def load_yaml(name: str) -> dict:
    with open(os.path.join(CONFIG, name), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Status:
    """Kaynak başına: durum, son başarılı çalışma, son deneme, son hatalar."""

    def __init__(self, prev: dict, now):
        self.sources = prev.get("sources") or {}
        self.now = now

    def _src(self, key, name, detail):
        s = self.sources.setdefault(key, {})
        s["name"], s["detail"] = name, detail
        s["last_run"] = iso(self.now)
        return s

    def ok(self, key, name, detail, items=None, message="", state="ok"):
        s = self._src(key, name, detail)
        s.update(state=state, last_success=iso(self.now), message=message)
        if items is not None:
            s["items"] = items

    def fail(self, key, name, detail, msg, state="error"):
        s = self._src(key, name, detail)
        s.update(state=state, message=msg)
        errs = s.setdefault("errors", [])
        errs.append({"t": iso(self.now), "msg": msg[:400]})
        s["errors"] = errs[-MAX_ERRORS:]
        print(f"[HATA] {name}: {msg}", file=sys.stderr)

    def skip(self, key, name, detail, message):
        s = self._src(key, name, detail)
        s.update(state="skipped", message=message)

    def prune(self, keep: set):
        for k in list(self.sources):
            if k not in keep:
                del self.sources[k]


def in_active_hours(settings: dict, now) -> bool:
    local = now.astimezone(BERLIN)
    hm = local.hour * 60 + local.minute
    sh, sm = map(int, str(settings.get("active_start", "07:00")).split(":"))
    eh, em = map(int, str(settings.get("active_end", "23:00")).split(":"))
    # Bitiş saatindeki çalışma gecikmeli başlayabilir (GitHub zamanlaması): 29 dk tolerans
    return sh * 60 + sm <= hm <= eh * 60 + em + 29


def resolve_merchants(http: Http, stores: list[dict], status: Status) -> None:
    """merchant kimliği verilmeyen mağazalar için mydealz'da otomatik bul (data/merchants.json'a önbellekle)."""
    cache = load_json("merchants.json", {})
    changed = False
    for st in stores:
        if st.get("mydealz_merchant_id") or st.get("search"):
            continue
        key = norm(st["name"])
        if key in cache:
            if cache[key]:
                st["mydealz_merchant_id"] = cache[key]
            continue
        try:
            threads = mydealz.parse_listing(http.get(mydealz.listing_url(query=st["name"])).text)
        except Exception as e:  # noqa: BLE001
            print(f"merchant araması başarısız ({st['name']}): {e}", file=sys.stderr)
            continue
        wanted = {norm(m) for m in (st.get("merchants") or [st["name"]])}
        found = None
        for th in threads:
            m = th.get("merchant") or {}
            if norm(m.get("merchantName") or "") in wanted:
                found = m.get("merchantId")
                break
        cache[key] = found
        changed = True
        if found:
            st["mydealz_merchant_id"] = found
            print(f"mydealz merchant bulundu: {st['name']} → {found}")
    if changed:
        save_json("merchants.json", cache)


def collect_deals(http, settings, stores, matchers, status, threshold) -> tuple[dict, set, set]:
    """Dönüş: (id→fırsat, süresi dolmuş id'ler, başarıyla taranan mağazalar)"""
    found: dict[str, dict] = {}
    expired: set[str] = set()
    scanned: set[str] = set()

    def add(raw, matcher, label):
        if raw.get("expired"):
            expired.add("md-" + raw["thread_id"])
            return
        d = mydealz.to_deal(raw, matcher.name, threshold, label)
        if not d:
            return
        prev = found.get(d["id"])
        if prev:  # liste verisi (eski fiyatlı) öncelikli; RSS kategoriyi tamamlar
            prev["category"] = prev.get("category") or d.get("category")
            return
        found[d["id"]] = d

    for m in matchers:
        key = "mydealz-store:" + norm(m.name).replace(" ", "-")
        detail = (f"mydealz mağaza listesi (merchant-id={m.merchant_id})" if m.merchant_id
                  else f"mydealz arama: \"{m.search}\"")
        try:
            n_threads, n_deals = 0, len(found)
            for page in range(1, m.pages + 1):
                url = mydealz.listing_url(merchant_id=m.merchant_id, query=m.search, page=page)
                threads = mydealz.parse_listing(http.get(url).text)
                if not threads:
                    break
                n_threads += len(threads)
                for th in threads:
                    raw = mydealz.thread_to_raw(th)
                    if m.matches(raw):
                        add(raw, m, "mydealz")
            if n_threads == 0:
                status.fail(key, f"mydealz · {m.name}", detail,
                            "Sayfada hiç fırsat verisi bulunamadı (mydealz sayfa yapısı değişmiş olabilir)")
            else:
                scanned.add(m.name)
                status.ok(key, f"mydealz · {m.name}", detail, items=len(found) - n_deals,
                          message=f"{n_threads} fırsat tarandı, %{threshold:.0f}+ olan {len(found) - n_deals} yeni kayıt")
        except Blocked as e:
            status.fail(key, f"mydealz · {m.name}", detail, str(e), state="blocked")
        except Exception as e:  # noqa: BLE001
            status.fail(key, f"mydealz · {m.name}", detail, f"{type(e).__name__}: {e}")

    for feed in (settings.get("mydealz") or {}).get("rss_feeds") or []:
        key = "mydealz-rss:" + feed["url"].rsplit("/", 1)[-1]
        try:
            items = mydealz.parse_rss(http.get(feed["url"]).text)
            hits = 0
            for raw in items:
                for m in matchers:
                    if m.matches(raw):
                        before = len(found)
                        add(raw, m, "mydealz RSS")
                        hits += len(found) - before
                        break
            if not items:
                status.fail(key, f"mydealz RSS · {feed['name']}", feed["url"], "Akış boş geldi")
            else:
                status.ok(key, f"mydealz RSS · {feed['name']}", feed["url"], items=len(items),
                          message=f"{len(items)} öğe; takip edilen mağazalardan %{threshold:.0f}+ ek {hits} fırsat")
        except Blocked as e:
            status.fail(key, f"mydealz RSS · {feed['name']}", feed["url"], str(e), state="blocked")
        except Exception as e:  # noqa: BLE001
            status.fail(key, f"mydealz RSS · {feed['name']}", feed["url"], f"{type(e).__name__}: {e}")
    return found, expired, scanned


def merge_deals(prev: list[dict], found: dict, expired: set, circular: list | None,
                now, keep_days: int, max_deals: int, first_run: bool) -> list[dict]:
    prev_by_id = {d["id"]: d for d in prev}
    out: dict[str, dict] = {}
    cutoff = now - timedelta(days=keep_days)

    def stamp(d):
        p = prev_by_id.get(d["id"])
        if p and p.get("found_at"):
            d["found_at"] = p["found_at"]
        else:
            d["found_at"] = (d.get("published_at") if first_run and d.get("published_at") else None) or iso(now)
        return d

    for d in found.values():
        out[d["id"]] = stamp(d)
    if circular is not None:
        for d in circular:
            out[d["id"]] = stamp(d)
    for d in prev:  # listeden düşmüş ama hâlâ geçerli olabilecek eski mydealz fırsatları
        if d["id"] in out or d["id"] in expired:
            continue
        if d.get("source") == "ikea-circular" and circular is not None:
            continue  # ilan artık yok (satıldı / rezerve edildi)
        t = parse_iso(d.get("published_at")) or parse_iso(d.get("found_at")) or now
        if t >= cutoff:
            out[d["id"]] = d
    deals = [d for d in out.values()
             if (parse_iso(d.get("published_at")) or parse_iso(d.get("found_at")) or now) >= cutoff
             or d.get("source") == "ikea-circular"]
    deals.sort(key=lambda d: d.get("published_at") or d.get("found_at") or "", reverse=True)
    return deals[:max_deals]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="site veri klasörü (ör. _site/data)")
    ap.add_argument("--force", action="store_true", help="aktif saat kontrolünü atla")
    ap.add_argument("--prev-status", default="", help="önceki status.json (yayındaki sitenin kopyası)")
    args = ap.parse_args()

    t0 = time.monotonic()
    now = now_utc()
    settings = load_yaml("settings.yaml")
    gh_out = os.environ.get("GITHUB_OUTPUT")

    def output(**kv):
        if gh_out:
            with open(gh_out, "a") as f:
                for k, v in kv.items():
                    f.write(f"{k}={v}\n")

    if not args.force and not in_active_hours(settings, now):
        print(f"Aktif saatler dışında (Berlin {now.astimezone(BERLIN):%H:%M}); çıkılıyor.")
        output(ran="false", deploy="false")
        return 0

    out_dirs = [args.out] if args.out else []
    threshold = float(settings.get("min_discount", 30))
    stores = (load_yaml("stores.yaml").get("stores") or [])
    wishlist_items = (load_yaml("wishlist.yaml").get("items") or [])

    prev_status = {}
    if args.prev_status and os.path.exists(args.prev_status):
        try:
            with open(args.prev_status, encoding="utf-8") as f:
                prev_status = json.load(f)
        except ValueError:
            prev_status = {}
    if not prev_status.get("sources"):
        prev_status = load_json("status.json", {})
    status = Status(prev_status, now)
    http = Http(delay=1.0)

    # 1) Genel indirimler
    resolve_merchants(http, stores, status)
    matchers = [mydealz.StoreMatcher(s) for s in stores]
    found, expired, _ = collect_deals(http, settings, stores, matchers, status, threshold)

    # 2) IKEA Circular Hub
    circ_cfg = settings.get("ikea_circular") or {}
    circular = None
    if circ_cfg.get("enabled", True):
        detail = "web-api.ikea.com circular-asis · " + ", ".join(circ_cfg.get("stores", {}).values())
        try:
            circular, total = fetch_circular(http, {str(k): v for k, v in circ_cfg.get("stores", {}).items()},
                                             threshold, int(circ_cfg.get("max_items", 100)))
            status.ok("ikea-circular", "IKEA Circular Hub (Fundgrube) Berlin", detail, items=len(circular),
                      message=f"Berlin mağazalarında {total} ilan; %{threshold:.0f}+ indirimli en yeni {len(circular)} tanesi gösteriliyor")
        except Blocked as e:
            status.fail("ikea-circular", "IKEA Circular Hub (Fundgrube) Berlin", detail, str(e), state="blocked")
        except Exception as e:  # noqa: BLE001
            status.fail("ikea-circular", "IKEA Circular Hub (Fundgrube) Berlin", detail, f"{type(e).__name__}: {e}")
    else:
        status.skip("ikea-circular", "IKEA Circular Hub (Fundgrube) Berlin", "", "config'te kapalı")

    prev_deals = load_json("deals.json", None)
    deals = merge_deals((prev_deals or {}).get("deals", []), found, expired, circular, now,
                        int(settings.get("keep_days", 14)), int(settings.get("max_deals", 500)),
                        first_run=prev_deals is None)

    # 3) İstek listesi
    history = load_json("history.json", {})
    wstate = load_json("wishlist_state.json", {})
    runner = WishlistRunner(http, settings, matchers, status, history, wstate)
    wl_items = []
    for it in wishlist_items:
        if not it or not it.get("name") or not it.get("url"):
            print(f"İstek listesinde eksik alanlı kayıt atlandı: {it}", file=sys.stderr)
            continue
        try:
            wl_items.append(runner.process(it))
        except Exception as e:  # noqa: BLE001
            status.fail("wishlist:" + item_id(it), f"İstek listesi · {it['name']}", it.get("url", ""),
                        f"{type(e).__name__}: {e}")
    keep_ids = {item_id(i) for i in wishlist_items if i and i.get("name")}
    history = {k: v for k, v in history.items() if k in keep_ids}
    wstate = {k: v for k, v in wstate.items() if k in keep_ids}

    names = {"ikea": ("page:ikea", "IKEA ürün sayfaları (istek listesi)", "ikea.com/de ürün sayfası, ürün başına günde ≤4 istek"),
             "zara": ("page:zara", "Zara / Zara Home ürün sayfaları (istek listesi)", "zara.com / zarahome.com ürün sayfası, ürün başına günde ≤4 istek")}
    for kind, (tried, okc, errs) in runner.page_stats.items():
        key, name, detail = names[kind]
        if not tried:
            continue
        if okc == tried:
            status.ok(key, name, detail, items=okc, message=f"{okc} ürün kontrol edildi")
        else:
            blocked = any("Engellendi" in e or "bot koruması" in e for e in errs)
            status.fail(key, name, detail, f"{tried - okc}/{tried} kontrol başarısız: " + " | ".join(errs)[:350]
                        + (" → bu ürünler için mydealz anahtar kelime aramasına geçildi" if blocked else ""),
                        state="blocked" if blocked else "error")
    tried, okc, errs = runner.md_stats
    if tried:
        if okc == tried:
            status.ok("mydealz-wishlist", "mydealz · istek listesi araması", "mydealz.de/search?q=<anahtar kelime>",
                      items=okc, message=f"{okc} ürün için arama yapıldı")
        else:
            status.fail("mydealz-wishlist", "mydealz · istek listesi araması", "mydealz.de/search?q=<anahtar kelime>",
                        " | ".join(errs)[:400])
    if any(norm(i.get("store") or "") == "amazon" for i in wishlist_items if i):
        status.skip("amazon", "Amazon (doğrudan)", "amazon.de",
                    "Kullanım koşulları ve bot engeli nedeniyle doğrudan taranmıyor; mydealz araması kullanılıyor")

    keep_src = {k for k in status.sources if not k.startswith("mydealz-store:") and not k.startswith("mydealz-rss:")
                and not k.startswith("wishlist:")}
    keep_src |= {"mydealz-store:" + norm(m.name).replace(" ", "-") for m in matchers}
    keep_src |= {"mydealz-rss:" + f["url"].rsplit("/", 1)[-1] for f in (settings.get("mydealz") or {}).get("rss_feeds") or []}
    keep_src |= {"wishlist:" + k for k in keep_ids}
    status.prune(keep_src)

    # 4) Yaz
    changed = False
    changed |= save_json("deals.json", {"generated_at": iso(now), "threshold": threshold, "deals": deals}, out_dirs)
    changed |= save_json("wishlist.json", {"generated_at": iso(now), "threshold": threshold, "items": wl_items}, out_dirs,
                         volatile=("generated_at", "last_checked"))
    changed |= save_json("history.json", history, out_dirs)
    changed |= save_json("wishlist_state.json", wstate, [])
    duration = round(time.monotonic() - t0, 1)
    status_obj = {"generated_at": iso(now),
                  "run": {"started_at": iso(now), "finished_at": iso(now_utc()), "duration_s": duration,
                          "http_requests": http.count},
                  "sources": status.sources}
    changed |= save_json("status.json", status_obj, out_dirs,
                         volatile=("generated_at", "run", "last_run", "last_success", "items", "message"))
    prev_run = parse_iso(((prev_status or {}).get("run") or {}).get("finished_at"))
    stale = prev_run is None or now - prev_run >= timedelta(hours=2)
    print(f"Bitti: {len(deals)} fırsat, {len(wl_items)} istek listesi ürünü, {http.count} HTTP isteği, {duration} sn; "
          f"veri değişti={changed}")
    output(ran="true", changed=str(changed).lower(), deploy=str(changed or stale).lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
