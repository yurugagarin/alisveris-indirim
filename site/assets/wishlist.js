/* İstek listesi: güncel/hedef/en düşük fiyat ve kütüphanesiz SVG fiyat grafiği. */
(function () {
  "use strict";
  const { money, relTime, absTime, esc, loadJSON } = window.App;
  const grid = document.getElementById("grid");
  const meta = document.getElementById("meta");

  // Fiyat geçmişi grafiği: [{t: ISO, p: fiyat}] → inline SVG
  function chart(points, target) {
    const pts = (points || []).filter((x) => typeof x.p === "number");
    if (pts.length < 1) return '<div class="note">Henüz fiyat geçmişi yok.</div>';
    const W = 320, H = 140, L = 44, R = 8, T = 10, B = 22;
    const xs = pts.map((x) => new Date(x.t).getTime());
    const ys = pts.map((x) => x.p);
    if (typeof target === "number") ys.push(target);
    let minY = Math.min(...ys), maxY = Math.max(...ys);
    if (minY === maxY) { minY -= 1; maxY += 1; }
    const pad = (maxY - minY) * 0.1; minY -= pad; maxY += pad;
    let minX = Math.min(...xs), maxX = Math.max(...xs);
    if (minX === maxX) { minX -= 3600e3; maxX += 3600e3; }
    const X = (t) => L + (t - minX) / (maxX - minX) * (W - L - R);
    const Y = (v) => T + (1 - (v - minY) / (maxY - minY)) * (H - T - B);
    // Basamaklı çizgi: fiyat bir sonraki ölçüme kadar geçerli sayılır.
    let d = "";
    pts.forEach((x, i) => {
      const px = X(xs[i]).toFixed(1), py = Y(x.p).toFixed(1);
      if (i === 0) d += `M${px},${py}`;
      else d += `H${px}V${py}`;
    });
    const lastX = X(xs[xs.length - 1]).toFixed(1);
    const area = d + `V${H - B}H${X(xs[0]).toFixed(1)}Z`;
    const ticks = [maxY - pad, (minY + maxY) / 2, minY + pad];
    const fmtD = (t) => new Date(t).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" });
    const dots = pts.length <= 40 ? pts.map((x, i) => `<circle cx="${X(xs[i]).toFixed(1)}" cy="${Y(x.p).toFixed(1)}" r="2.5"><title>${esc(absTime(x.t))}: ${esc(money(x.p))}${x.src ? " (" + esc(x.src) + ")" : ""}</title></circle>`).join("") : "";
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Fiyat geçmişi">
      ${ticks.map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text x="${L - 4}" y="${(Y(v) + 3).toFixed(1)}" text-anchor="end">${esc(money(v).replace(/\s/g, " "))}</text>`).join("")}
      ${typeof target === "number" ? `<line class="target" x1="${L}" x2="${W - R}" y1="${Y(target).toFixed(1)}" y2="${Y(target).toFixed(1)}"><title>Hedef fiyat ${esc(money(target))}</title></line>` : ""}
      <path class="area" d="${area}"/>
      <path class="line" d="${d}H${lastX}"/>
      ${dots}
      <text x="${L}" y="${H - 6}">${esc(fmtD(minX))}</text>
      <text x="${W - R}" y="${H - 6}" text-anchor="end">${esc(fmtD(maxX))}</text>
    </svg>`;
  }

  const statusBadge = {
    ok: '<span class="badge ok">kontrol ediliyor</span>',
    blocked: '<span class="badge bad">mağaza engelledi → mydealz</span>',
    error: '<span class="badge bad">hata</span>',
    mydealz: '<span class="badge">mydealz araması</span>',
    pending: '<span class="badge">bekliyor</span>',
  };

  function card(it) {
    const badges = [];
    if (it.highlight) badges.push('<span class="badge disc">🎯 FIRSAT</span>');
    if (it.discount) badges.push(`<span class="badge disc">-%${Math.round(it.discount)}</span>`);
    if (it.suspicious) badges.push(`<span class="badge sus" title="${esc(it.suspicious_reason || "")}">⚠ şüpheli indirim</span>`);
    badges.push(`<span class="badge">${esc(it.store)}</span>`);
    badges.push(statusBadge[it.status] || "");
    const reasons = (it.reasons || []).map((r) => `<div class="note">✔ ${esc(r)}</div>`).join("");
    return `<article class="card wl-item${it.highlight ? " hl" : ""}">
      <div class="wl-head">
        ${it.image ? `<img class="thumb" loading="lazy" src="${esc(it.image)}" alt="">` : ""}
        <div class="body">
          <div class="badges">${badges.join("")}</div>
          <h3><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.name)}</a></h3>
          <div class="meta">son kontrol: ${esc(relTime(it.last_checked))}${it.price_source ? " · kaynak: " + esc(it.price_source) : ""}</div>
        </div>
      </div>
      <div class="kv">
        <div><span>Güncel fiyat</span><b>${money(it.current_price)}</b></div>
        <div><span>Hedef fiyat</span><b>${money(it.target_price)}</b></div>
        <div><span>En düşük (kendi kaydım)</span><b>${money(it.lowest_price)}</b></div>
        <div><span>Son 30 gün en düşük</span><b>${money(it.lowest_30d)}</b></div>
        ${it.shop_lowest_30d ? `<div><span>Mağazanın beyanı (30 gün)</span><b>${money(it.shop_lowest_30d)}</b></div>` : ""}
        ${it.old_price ? `<div><span>Mağazanın eski fiyatı</span><b>${money(it.old_price)}</b></div>` : ""}
      </div>
      ${reasons}
      ${it.suspicious_reason ? `<div class="note">⚠ ${esc(it.suspicious_reason)}</div>` : ""}
      ${it.message ? `<div class="note">ℹ ${esc(it.message)}</div>` : ""}
      ${it.mydealz_match ? `<div class="note">mydealz: <a href="${esc(it.mydealz_match.url)}" target="_blank" rel="noopener">${esc(it.mydealz_match.title)}</a> — ${money(it.mydealz_match.price)}</div>` : ""}
      ${chart(it.history, it.target_price)}
    </article>`;
  }

  loadJSON("data/wishlist.json").then((data) => {
    const items = (data.items || []).slice().sort((a, b) => (b.highlight === true) - (a.highlight === true));
    meta.textContent = `Son güncelleme: ${absTime(data.generated_at)} · ${items.length} ürün · ${items.filter((i) => i.highlight).length} fırsat`;
    grid.innerHTML = items.length ? items.map(card).join("") :
      '<div class="empty">İstek listen boş. <code>config/wishlist.yaml</code> dosyasına ürün ekle.</div>';
  }).catch((e) => { grid.innerHTML = `<div class="empty">Veri yüklenemedi: ${esc(e.message)}</div>`; });
})();
