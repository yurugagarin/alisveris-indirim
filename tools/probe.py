"""Kaynak keşif betiği (geliştirme amaçlı, geçici)."""
import re, json, html, requests
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})
r = S.get("https://www.ikea.com/de/de/asisonline/", timeout=20)
chunks = sorted(set(re.findall(r'/de/de/asisonline/_next/static/chunks/[A-Za-z0-9_\-\.]+\.js', r.text)))
for c in chunks:
    js = S.get("https://www.ikea.com" + c, timeout=20).text
    for m in re.findall(r'.{0,200}(?:offerNumber\}|/offer/|/offers/\$|router\.push|href:`).{0,200}', js)[:15]:
        print("JS", c[-18:], m[:400])
    for m in re.findall(r'.{0,120}(?:sortBy|sort=|"sort"|sort:).{0,160}', js)[:6]:
        print("SORT", c[-18:], m[:300])
d = S.get("https://web-api.ikea.com/circular/circular-asis/offers/grouped/search?languageCode=de&size=2&page=0&storeIds=324,394,421,129", timeout=20).json()
print("TOP", {k: v for k, v in d.items() if k != "content"})
it = d["content"][0]
print("ITEM", json.dumps({k: v for k, v in it.items() if k not in ("media", "technicalMedia")}, ensure_ascii=False)[:2500])
t = S.get("https://www.ikea.com/de/de/p/droena-fach-dunkelgrau-10443974/", timeout=20).text
for pat in [r'.{0,300}Vorher.{0,400}', r'.{0,300}30 Tage.{0,300}', r'.{0,200}previous.{0,300}', r'data-product-price[^>]{0,100}', r'"offers":\{.{0,300}']:
    hits = re.findall(pat, t)
    print("DRONA", pat, len(hits))
    for h in hits[:4]:
        print("   ->", html.unescape(re.sub(r"<[^>]+>", "|", h))[:600])
