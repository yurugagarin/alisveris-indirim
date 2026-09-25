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

# 1) mydealz search: one thread JSON
r = get("https://www.mydealz.de/search?q=ikea")
t = r.text
i = t.find('"nextBestPrice"')
print("CTX:", html.unescape(t[max(0, i-2500):i+1500]))
m = re.findall(r'data-vue3=\'(\{"name":"ThreadMainListItemNormalizer".*?)\'', t)
print("vue3 count", len(m))
if m:
    d = json.loads(html.unescape(m[0]))
    print(json.dumps(d, ensure_ascii=False)[:4000])
print("vue names:", sorted(set(re.findall(r'data-vue3=\'\{"name":"(\w+)"', t))))
# groups list
r = get("https://www.mydealz.de/gruppe")
print(sorted(set(re.findall(r'mydealz\.de/gruppe/([a-z0-9\-]+)', r.text)))[:300])
for u in ["https://www.mydealz.de/rss/gruppe/wohnen", "https://www.mydealz.de/rss/gruppe/moebel-wohnen",
          "https://www.mydealz.de/rss/gruppe/moebel-einrichtung", "https://www.mydealz.de/rss/gruppe/home-living",
          "https://www.mydealz.de/rss/haendler/ikea-com", "https://www.mydealz.de/rss/deals/ikea-com",
          "https://www.mydealz.de/rss/merchant/ikea-com", "https://www.mydealz.de/deals-ikea-com",
          "https://www.mydealz.de/search/deals?merchant-id=50", "https://www.mydealz.de/gutscheine/ikea-com",
          "https://www.mydealz.de/rss/gutscheine/ikea-com", "https://www.mydealz.de/rss/alles?q=ikea",
          "https://www.mydealz.de/search/deals?q=ikea&sortBy=new", "https://www.mydealz.de/search?q=zara%20home"]:
    try:
        rr = get(u)
        if "xml" in (rr.headers.get("content-type") or ""):
            print(rr.text[:600])
        else:
            print(" names:", len(re.findall(r'"merchantName":"([^"]+)"', rr.text)), set(re.findall(r'"merchantName":"([^"]+)"', rr.text)))
    except Exception as e:
        print("ERR", e)

# 2) IKEA product: price related JSON keys
r = get("https://www.ikea.com/de/de/p/billy-buecherregal-weiss-00263850/")
t = r.text
for pat in [r'id="pip-range-json-ld">(.{0,1500})', r'"(?:previous|lowest|was|regular|former)\w*"\s*:\s*[^,]{0,80}',
            r'data-hydration-props="(.{0,200})', r'pip-price-module[^"]{0,60}', r'"isBreathTakingItem[^,]*', r'"priceInfo.{0,400}']:
    print(pat, "=>", re.findall(pat, t)[:4])
i = t.find('data-hydration-props')
print("HYD:", html.unescape(t[i:i+3000]))
# 3) IKEA second-hand page: API hints
r = get("https://www.ikea.com/de/de/second-hand/buy-from-ikea/")
t = r.text
print(sorted(set(re.findall(r'https?://[a-z0-9\.\-]*ikea[a-z0-9\.\-]*/[A-Za-z0-9_\-/\.]{0,80}', t)))[:120])
for pat in [r'circular[^"\s]{0,100}', r'storeId[^,]{0,60}', r'Berlin[^"<]{0,80}', r'api[a-zA-Z]*Url[^,]{0,120}']:
    print(pat, "=>", sorted(set(re.findall(pat, t)))[:30])
# 4) Zara: product link from search, then product page and ajax
r = get("https://www.zara.com/de/de/search?searchTerm=hemd")
t = r.text
links = sorted(set(re.findall(r'https://www\.zara\.com/de/de/[a-z0-9\-]+-p\d+\.html', t)))
print("zara links", len(links), links[:5])
print("zara price ctx", re.findall(r'"price":\s*\d+', t)[:5], t.count("bm-verify"))
if links:
    get(links[0]); rr = get(links[0] + "?ajax=true"); print(rr.text[:500])
