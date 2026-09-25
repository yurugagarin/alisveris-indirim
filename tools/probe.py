"""Kaynak keşif betiği (geliştirme amaçlı, geçici)."""
import re, json, html, requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9",
                  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})

def get(u, **kw):
    r = S.get(u, timeout=20, **kw)
    print(f"\n##### {u}\n# status={r.status_code} ct={r.headers.get('content-type')} len={len(r.text)} final={r.url}")
    return r

def threads(t):
    out = []
    for m in re.findall(r'data-vue3=\'(\{"name":"ThreadMainListItemNormalizer".*?)\'', t):
        out.append(json.loads(html.unescape(m))["props"]["thread"])
    return out

r = get("https://www.mydealz.de/search/deals?merchant-id=50")
i = r.text.find('"sortBy"'); print("SORT:", html.unescape(r.text[i:i+900]))
for th in threads(r.text)[:8]:
    print(th["publishedAt"], th["isExpired"], th["price"], th["nextBestPrice"], th["mainGroup"], th["title"][:60])
for u in ["https://www.mydealz.de/search/deals?merchant-id=50&sortBy=new", "https://www.mydealz.de/search?merchant-id=50&sortBy=new",
          "https://www.mydealz.de/search?q=zara", "https://www.mydealz.de/search?q=amazon", "https://www.mydealz.de/search?q=zara+home",
          "https://www.mydealz.de/search?q=billy+regal", "https://www.mydealz.de/search?q=ikea&sortBy=new"]:
    r = get(u); ts = threads(r.text)
    print(" merchants:", sorted({(t["merchant"] or {}).get("merchantName", "-") + "#" + str((t["merchant"] or {}).get("merchantId")) for t in ts}))
    print(" dates:", [t["publishedAt"] for t in ts[:10]])

# IKEA discounted product (DRÖNA)
r = get("https://www.ikea.com/de/de/search/?q=dr%C3%B6na")
links = sorted(set(re.findall(r'https://www\.ikea\.com/de/de/p/[a-z0-9\-]+-\d{8}/', r.text)))
print("ikea links", links[:10])
for l in links[:2]:
    t = get(l).text
    for pat in [r'.{0,200}30 Tage.{0,300}', r'.{0,200}[Nn]iedrigst.{0,300}', r'data-product-price[^>]{0,200}',
                r'"offers":\{.{0,400}', r'.{0,100}pip-price-package__previous.{0,300}', r'.{0,150}[Vv]orher.{0,200}',
                r'.{0,150}strikethrough.{0,200}', r'.{0,100}"previous.{0,200}']:
        hits = re.findall(pat, t)
        print("  ", pat, len(hits), [html.unescape(re.sub(r"<[^>]+>", " ", h))[:400] for h in hits[:3]])
    break

# IKEA asisonline
r = get("https://www.ikea.com/de/de/asisonline")
t = r.text
print("title", re.findall(r"<title>(.*?)</title>", t))
chunks = sorted(set(re.findall(r'/de/de/asisonline/_next/static/chunks/[A-Za-z0-9_\-\.]+\.js', t)))
print("chunks", len(chunks))
seen = set()
for c in chunks:
    js = S.get("https://www.ikea.com" + c, timeout=20).text
    for m in re.findall(r'.{0,160}(?:circular-asis|web-api\.ikea|/offers|storeIds|stores\?).{0,220}', js):
        k = m[:120]
        if k not in seen:
            seen.add(k); print("JS", c[-20:], m[:380])
for pat in [r'.{0,100}(?:circular-asis|web-api).{0,300}', r'"stores?".{0,300}', r'__NEXT_DATA__.{0,1500}']:
    print(pat, [h[:500] for h in re.findall(pat, t)[:4]])
