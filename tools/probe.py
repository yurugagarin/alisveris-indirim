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

r = get("https://www.ikea.com/de/de/asisonline/")
nd = json.loads(re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>', r.text).group(1))
pp = nd["props"]["pageProps"]
print("pageProps keys", list(pp.keys()))
stores = pp.get("stores") or []
print([s for s in stores if "Berlin" in s.get("name", "")])
chunks = sorted(set(re.findall(r'/de/de/asisonline/_next/static/chunks/[A-Za-z0-9_\-\.]+\.js', r.text)))
for c in chunks:
    js = S.get("https://www.ikea.com" + c, timeout=20).text
    for m in re.findall(r'.{0,250}(?:groupedOffers|storeIds|store_ids|"stores"|sortBy|sort:).{0,250}', js)[:12]:
        print("JS", c[-18:], m[:500])
berlin = [s for s in stores if "Berlin" in s.get("name", "")]
ids = [str(s["id"]) for s in berlin]; sids = [s["store_id"] for s in berlin]
base = "https://web-api.ikea.com/circular/circular-asis/offers/grouped/search?languageCode=de&size=4&page=0"
for extra in ["", "&storeIds=" + ",".join(ids), "&storeIds=" + ",".join(sids), "&stores=" + ",".join(ids), "&storeId=" + ids[0] if ids else ""]:
    rr = get(base + extra, headers={"Accept": "application/json", "Origin": "https://www.ikea.com", "Referer": "https://www.ikea.com/"})
    print(rr.text[:1800])
rr = get("https://web-api.ikea.com/circular/circular-asis/markets", headers={"Accept": "application/json"}); print(rr.text[:500])

# IKEA search API to find a discounted product
for q in ["dröna", "tjusig", "åsjordfly"]:
    rr = get("https://sik.search.blue.cdtapps.com/de/de/search-result-page?q=" + q + "&types=PRODUCT&size=3",
             headers={"Accept": "application/json"})
    try:
        d = rr.json()
        items = d["searchResultPage"]["products"]["main"]["items"]
        for it in items[:3]:
            p = it.get("product", {})
            print(p.get("pipUrl"), json.dumps({k: p.get(k) for k in ("salesPrice", "discount", "priceNumeral", "previous", "lowestPrice", "tag", "highlight")}, ensure_ascii=False)[:600])
    except Exception as e:
        print("ERR", e, rr.text[:300])
