# 🏷️ Kişisel İndirim Takip (Berlin / Almanya)

IKEA, Zara, Zara Home ve Amazon indirimlerini **mydealz.de** üzerinden, istek listendeki ürünleri
de mağaza sayfaları ve mydealz üzerinden takip eden, tamamen ücretsiz çalışan kişisel bir site.

- **Site:** https://yurugagarin.github.io/alisveris-indirim/ (GitHub Pages bir kez açıldıktan sonra, aşağıya bak)
- **Maliyet:** 0 €. Python + GitHub Actions + GitHub Pages. Ücretli API, API anahtarı veya yapay zekâ servisi yok.
- **Arayüz:** sade HTML/CSS/JS (framework yok), mobil öncelikli, açık/koyu tema, Türkçe.
- **Kişisel tercihler** (görüldü, gizle, favori, filtreler, tema, son ziyaret) yalnızca tarayıcının `localStorage`'ında durur.

## Sayfalar

| Sayfa | İçerik |
|---|---|
| **İndirimler** (`index.html`) | %30+ indirimli güncel fırsatlar, en yeniler üstte. Mağaza / kategori / indirim oranı filtresi, arama. Son ziyaretinden sonra gelenler **YENİ** etiketli. Kartta ürün, mağaza, eski/yeni fiyat, indirim %, ne zaman bulunduğu, link ve varsa **⚠ şüpheli indirim** etiketi. Görüldü / Favori / Gizle düğmeleri. |
| **İstek listem** (`wishlist.html`) | Ürünler, güncel fiyat, hedef fiyat, kendi kaydımdaki en düşük fiyat, son 30 günün en düşüğü, mağazanın beyanı ve kütüphanesiz inline SVG fiyat geçmişi grafiği. Hedef fiyat veya %30 eşiği tutan ürünler **🎯 FIRSAT** olarak öne çıkar. |
| **Durum** (`status.html`) | Her kaynağın son başarılı çalışma zamanı, son denemesi ve son hataları. Bir kaynak bozulursa burada "hata" veya "engellendi" görünür. |

## İlk kurulum: GitHub Pages'i aç (tek seferlik)

Workflow siteyi `gh-pages` dalına yayınlar. GitHub, Pages'in Actions token'ıyla açılmasına izin
vermediği için bunu bir kez elle yapman gerekiyor:

1. Repo → **Settings** → **Pages**
2. **Build and deployment → Source:** `Deploy from a branch`
3. **Branch:** `gh-pages`, klasör `/ (root)` → **Save**

1–2 dakika içinde site https://yurugagarin.github.io/alisveris-indirim/ adresinde açılır.

> Zamanlanmış çalışmalar (cron) yalnızca **varsayılan dalda (`main`)** çalışır; tüm düzenlemeleri
> `main` dalında yap.

## İstek listesine ürün ekleme

`config/wishlist.yaml` dosyasını GitHub'da aç (kalem simgesi → düzenle) ve `items:` altına ekle:

```yaml
  - name: "IKEA POÄNG Sessel"
    store: IKEA
    url: "https://www.ikea.com/de/de/p/...-12345678/"   # ürün sayfasının adres çubuğundaki link
    target_price: 79        # opsiyonel, euro
    keywords: "poäng"       # opsiyonel, mydealz araması için
```

| Alan | Zorunlu | Açıklama |
|---|---|---|
| `name` | ✔ | Ürün adı. Fiyat geçmişi bu ada bağlıdır; adı değiştirirsen geçmiş sıfırlanır. |
| `store` | ✔ | `IKEA`, `Zara`, `Zara Home`, `Amazon` veya `stores.yaml`'daki başka bir mağaza |
| `url` | ✔ | Ürün linki |
| `target_price` | | Hedef fiyat (€). Fiyat bunun altına inerse ürün öne çıkar. |
| `keywords` | | mydealz'da aranacak kelimeler. Başlıkta **hepsi** geçen fırsatlar eşleşir. Boşsa ürün adı kullanılır; kısa ve ayırt edici kelimeler daha iyi sonuç verir (ör. `"kindle paperwhite"`). |

Commit'lediğinde workflow otomatik çalışır ve site birkaç dakika içinde güncellenir.

**Ürünler nasıl kontrol ediliyor?**

| Mağaza | Yöntem |
|---|---|
| IKEA | Ürün sayfası, **ürün başına günde en fazla 4 istek** (07:00–23:00 arasına ~4 saatte bir yayılır). Sayfa bozulur veya engellenirse mydealz aramasına geçer. |
| Zara / Zara Home | Ürün sayfası aynı limitle denenir. Şu an Akamai bot koruması engelliyor → ürün **"engellendi"** olarak raporlanır, 20 saat boyunca tekrar denenmez ve fiyat **mydealz anahtar kelime aramasından** izlenir. |
| Amazon | **Asla doğrudan taranmaz** (kullanım koşulları ve bot engeli). Yalnızca mydealz anahtar kelime araması, 2 saatte bir. Ek olarak aşağıdaki Keepa alarmını kur. |
| Diğer | mydealz anahtar kelime araması |

Fiyat geçmişi `data/history.json` dosyasında, istek sayaçları `data/wishlist_state.json` dosyasında tutulur.

## Mağaza ekleme

`config/stores.yaml` dosyasına **tek satır** ekle:

```yaml
  - {name: H&M}
```

İlk çalışmada mydealz'daki mağaza kimliği otomatik bulunur (`data/merchants.json`) ve o mağazanın
%30+ fırsatları ana sayfaya gelmeye başlar. Bulunamazsa mydealz'da mağaza sayfasını açıp
kimliği elle verebilirsin: `- {name: H&M, mydealz_merchant_id: 1234}`.

İsteğe bağlı alanlar: `merchants` (mydealz'daki mağaza adları), `search` (kimlik yerine anahtar
kelime araması), `include` / `exclude` (başlıkta geçmesi / geçmemesi gereken kelimeler), `pages`
(taranacak sayfa sayısı, sayfa başı ~30 fırsat).

## Ayarlar (`config/settings.yaml`)

- `min_discount: 30`: indirim eşiği (%). Ana sayfa, fırsat ve şüpheli indirim hesabı bunu kullanır.
- `keep_days`, `max_deals`: fırsatların ana sayfada kalma süresi ve üst sınırı.
- `product_checks_per_day: 4`: mağaza ürün sayfası başına günlük istek limiti.
- `wishlist_mydealz_interval_hours: 2`: istek listesi için mydealz arama sıklığı.
- `mydealz.rss_feeds`: kategori bazlı RSS akışları (Home & Living, Fashion & Accessoires, tüm yeni fırsatlar, trend).
- `ikea_circular`: Berlin IKEA mağazalarının ikinci el ilanları (açık/kapalı, mağazalar, en fazla ilan).

## Kaynaklar

| Kaynak | Ne için | Durum (ilk kurulumda test edildi) |
|---|---|---|
| mydealz mağaza listeleri (`/search/deals?merchant-id=…`) | IKEA (50), Zara (945), Amazon (3) fırsatları; eski fiyat (mydealz fiyat karşılaştırması) ve kategori içeren yapılandırılmış veri | ✅ çalışıyor |
| mydealz arama (`/search?q=…`) | Zara Home (mydealz'da ayrı mağaza değil, ZARA altında) ve istek listesi anahtar kelime araması | ✅ çalışıyor |
| mydealz RSS (`/rss/gruppe/home-living`, `/rss/gruppe/fashion-accessoires`, `/rss/alles`, `/rss/trending`) | Kategori akışları. RSS eski fiyat vermediği için "statt X €" / "-%40" başlıktan okunur. | ✅ çalışıyor. mydealz'da mağaza bazlı RSS **yok** (`/rss/gruppe/ikea` vb. 404), bu yüzden mağaza verisi yukarıdaki listelerden geliyor. |
| IKEA ürün sayfaları | İstek listesi fiyatı, "Vorher" fiyatı | ✅ çalışıyor |
| IKEA Circular Hub / Fundgrube (Berlin-Lichtenberg, Spandau, Tempelhof, Waltersdorf) | İkinci el / indirimli ilanlar (online rezervasyon) | ✅ online erişim var, ana sayfada "IKEA Fundgrube Berlin" mağazası olarak görünür |
| Zara / Zara Home ürün sayfaları | İstek listesi | ❌ Akamai bot koruması engelliyor → mydealz aramasına geçiliyor |
| Amazon | — | ⏭ bilerek taranmıyor (mydealz + Keepa) |

Güncel durum her zaman **Durum** sayfasında.

## Sahte indirim kontrolü

Mağazanın gösterdiği "eski fiyat"a körü körüne güvenilmez:

1. **Mağazanın 30 günlük beyanı:** Sayfada "son 30 günün en düşük fiyatı" varsa o kullanılır.
   IKEA indirimde "Vorher: X €" gösterir. Almanya'da PAngV §11 gereği bu fiyat indirimden önceki
   **son 30 günün en düşük fiyatıdır**, bu yüzden 30 günlük beyan olarak alınır. mydealz açıklamasında
   "niedrigster Preis der letzten 30 Tage" geçiyorsa o da okunur.
2. **Kendi fiyat geçmişim:** İstek listesi ürünlerinde, güncel fiyat seviyesinden önceki son 30 günün en
   düşük kaydı hesaplanır. İki referans varsa **daha düşük olan** kullanılır.
3. Gösterilen indirim ≥ %30 ama 30 günlük en düşüğe göre gerçek indirim < %30 ise **⚠ şüpheli indirim**.

Not: mydealz'daki "eski fiyat", mağazanın üstü çizili fiyatı değil, mydealz'ın **fiyat karşılaştırmasındaki
bir sonraki en iyi fiyattır** (bağımsız bir referans).

## Zamanlama (GitHub Actions)

- `.github/workflows/update.yml`, Berlin saatiyle **07:00–23:00 arası 30 dakikada bir** çalışır.
  GitHub cron'u UTC olduğu için hem yaz (UTC+2) hem kış (UTC+1) saatini kapsayan UTC aralığında
  (`05:00–22:00 UTC`) tetiklenir. Pipeline Berlin saatine (`Europe/Berlin`, yaz/kış otomatik)
  bakar ve aralık dışındaki fazladan çalışmaları hiçbir istek atmadan hemen sonlandırır.
- Elle çalıştırma: **Actions → İndirimleri güncelle → Run workflow**.
- `config/`, `tracker/` veya `site/` değişince otomatik çalışır.
- Veri `data/*.json` olarak commit'lenir (yalnızca içerik gerçekten değiştiyse), site `gh-pages` dalına yayınlanır.
- **60 gün kuralına karşı önlem:** GitHub, 60 gün aktivite olmayan repolarda zamanlanmış workflow'ları
  durdurur. Veri commit'leri zaten sık olur; yine de son commit 40 günden eskiyse workflow
  `data/.keepalive` dosyasını güncelleyip commit'ler.

### Tahmini Actions dakika kullanımı

| Kalem | Hesap | Aylık |
|---|---|---|
| Güncelleme işi | günde 35 tetikleme (33'ü aktif saatte) × 1 dk (tek iş ~20–35 sn sürer; GitHub iş başına dakikayı yukarı yuvarlar) | **≈ 1.070 dk** |
| GitHub Pages yayını (`pages-build-deployment`, GitHub'ın kendi workflow'u) | yalnızca veri değiştiğinde veya 2 saatte bir, ≈ 15–30 yayın/gün × ~1 dk | ≈ 450–900 dk |
| **Toplam** | | **≈ 1.500–2.000 dk/ay** |

**Önemli:** Bu repo **public** olduğu için GitHub-hosted runner dakikaları **ücretsiz ve sınırsızdır**.
Free plandaki 2.000 dk/ay kotasından **düşmez**, yani aynı hesaptaki hisse analiz sitesinin kotasını
etkilemez. Repo private yapılırsa bu dakikalar kotadan düşer (aşağıya bak).

## Repo private olursa

- Free planda **private repolarda GitHub Pages kullanılamaz** (GitHub Pro gerekir).
- Dakikalar 2.000 dk/ay kotasından düşer. Hisse sitesiyle birlikte kotayı aşmamak için
  cron'u saatte bire indir (`"0 5-22 * * *"`, ≈ 540 dk/ay).
- **Ücretsiz alternatif:** [Cloudflare Pages](https://pages.cloudflare.com/) (private repo destekler,
  ücretsiz). Cloudflare Pages → Create project → GitHub reposunu bağla → Production branch:
  `gh-pages`, Build command: boş, Output directory: `/`. Workflow değişmeden çalışmaya devam eder.
  Netlify da aynı şekilde ücretsiz kullanılabilir.

## Amazon için Keepa ücretsiz fiyat alarmı

mydealz yalnızca birisi fırsat paylaştığında haber verir. Belirli bir Amazon ürünü için ek olarak:

1. https://keepa.com adresine git, sağ üstten **ücretsiz hesap** aç (e-posta yeterli).
2. Üstteki bayraktan **Amazon.de**'yi (🇩🇪) seç.
3. Arama kutusuna ürün adını, ASIN'i veya amazon.de linkini yapıştır ve ürünü aç.
4. Fiyat grafiğinin altındaki **"Produkt beobachten / Track product"** sekmesine geç.
5. **Amazon** (Amazon'un kendi sattığı) ve istersen **Neu** (üçüncü taraf) için istediğin fiyatı gir.
6. Bildirim kanalını seç (e-posta varsayılan; Keepa ayarlarından Telegram veya tarayıcı bildirimi de açılabilir) → **Beobachtung starten**.
7. İsteğe bağlı: Keepa tarayıcı eklentisi (Chrome/Firefox) amazon.de ürün sayfalarında fiyat geçmişi grafiğini gösterir. Sahte indirimleri görmek için çok faydalı.

Fiyat geçmişi grafikleri ve fiyat alarmları ücretsizdir. Ücretli abonelik yalnızca gelişmiş araçlar (Product Finder, API) için gerekir.

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
python -m tracker.main --force --out _site/data   # --force: aktif saat kontrolünü atla
cp -r site/. _site/ && python -m http.server -d _site 8000
```

## Dosya yapısı

```
config/stores.yaml      takip edilen mağazalar (her satır bir mağaza)
config/wishlist.yaml    istek listem
config/settings.yaml    eşik, sıklık, RSS akışları, Circular Hub
tracker/                Python pipeline (mydealz, IKEA/Zara, Circular Hub, istek listesi)
site/                   statik site (HTML/CSS/JS)
data/                   JSON veri: deals, wishlist, history, status (workflow commit'ler)
.github/workflows/update.yml   zamanlama, commit ve gh-pages yayını
```
