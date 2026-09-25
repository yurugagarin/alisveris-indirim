"""Kaynak keşif betiği: aday URL'leri dener ve yanıtın başını loglar (geliştirme amaçlı)."""
import re, sys, requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9",
                  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})

URLS = [a for a in sys.argv[1:]]
for u in URLS:
    try:
        r = S.get(u, timeout=20)
        body = r.text
        print(f"\n##### {u}\n# status={r.status_code} ct={r.headers.get('content-type')} len={len(body)} final={r.url}")
        if "rss" in u or "xml" in (r.headers.get("content-type") or ""):
            print(body[:3000])
        else:
            print(body[:600].replace("\n", " "))
            for pat in [r'"price"[^,]{0,80}', r'lowest[^<]{0,120}', r'niedrigst[^<]{0,160}', r'30 Tage[^<]{0,160}',
                        r'application/ld\+json[^<]{0,50}', r'data-product-price[^>]{0,120}', r'pip-temp-price[^<]{0,200}',
                        r'"nextBestPrice"[^,]{0,40}', r'"percentage"[^,]{0,40}', r'"merchant[^,]{0,80}']:
                m = re.findall(pat, body)
                if m:
                    print(f"  [{pat}] x{len(m)}: {m[:3]}")
    except Exception as e:
        print(f"\n##### {u}\n# ERROR {e!r}")
