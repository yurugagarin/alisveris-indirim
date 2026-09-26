/* Ana sayfa: güncel indirimler, filtreler, YENİ etiketi, görüldü/gizle/favori. */
(function () {
  "use strict";
  const { store, idSet, money, relTime, absTime, esc, loadJSON } = window.App;

  const seen = idSet("seen");
  const hidden = idSet("hidden");
  const favs = idSet("favorites");

  // "Son ziyaret": bu oturumda sabit kalsın ki sayfayı yenileyince YENİ etiketleri kaybolmasın.
  let lastVisit = null;
  try { lastVisit = sessionStorage.getItem("sessionLastVisit"); } catch (e) { /* yok say */ }
  if (lastVisit === null) {
    lastVisit = store.get("lastVisit", "");
    try { sessionStorage.setItem("sessionLastVisit", lastVisit); } catch (e) { /* yok say */ }
  }
  store.set("lastVisit", new Date().toISOString());
  const lastVisitMs = lastVisit ? new Date(lastVisit).getTime() : 0;

  const els = {
    grid: document.getElementById("grid"),
    store: document.getElementById("f-store"),
    cat: document.getElementById("f-cat"),
    min: document.getElementById("f-min"),
    minVal: document.getElementById("f-min-val"),
    q: document.getElementById("f-q"),
    onlyNew: document.getElementById("f-new"),
    onlyFav: document.getElementById("f-fav"),
    showHidden: document.getElementById("f-hidden"),
    hideSus: document.getElementById("f-sus"),
    meta: document.getElementById("meta"),
    count: document.getElementById("count"),
    markAll: document.getElementById("mark-all"),
  };

  let deals = [];
  let threshold = 30;

  const saved = store.get("filters", {});
  function saveFilters() {
    store.set("filters", {
      store: els.store.value, cat: els.cat.value, min: els.min.value,
      onlyNew: els.onlyNew.getAttribute("aria-pressed") === "true",
      onlyFav: els.onlyFav.getAttribute("aria-pressed") === "true",
      showHidden: els.showHidden.getAttribute("aria-pressed") === "true",
      hideSus: els.hideSus.getAttribute("aria-pressed") === "true",
    });
  }

  function fillSelect(sel, values, allLabel, savedValue) {
    sel.innerHTML = `<option value="">${esc(allLabel)}</option>` +
      values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    if (savedValue && values.includes(savedValue)) sel.value = savedValue;
  }

  function isNew(d) { return lastVisitMs > 0 && new Date(d.found_at).getTime() > lastVisitMs; }

  function card(d) {
    const nw = isNew(d) && !seen.has(d.id);
    const cls = ["card"];
    if (seen.has(d.id)) cls.push("seen");
    const badges = [];
    if (nw) badges.push('<span class="badge new">YENİ</span>');
    if (d.discount !== null && d.discount !== undefined) badges.push(`<span class="badge disc">-%${Math.round(d.discount)}</span>`);
    if (d.suspicious) badges.push(`<span class="badge sus" title="${esc(d.suspicious_reason || "")}">⚠ şüpheli indirim</span>`);
    if (d.expired) badges.push('<span class="badge bad">süresi doldu</span>');
    if (favs.has(d.id)) badges.push('<span class="badge">★ favori</span>');
    badges.push(`<span class="badge">${esc(d.store)}</span>`);
    if (d.category) badges.push(`<span class="badge">${esc(d.category)}</span>`);
    const img = d.image ? `<img class="thumb" loading="lazy" src="${esc(d.image)}" alt="">` : "";
    return `<article class="${cls.join(" ")}" data-id="${esc(d.id)}">
      ${img}
      <div class="body">
        <div class="badges">${badges.join("")}</div>
        <h3><a href="${esc(d.url)}" target="_blank" rel="noopener" data-act="open">${esc(d.title)}</a></h3>
        <div class="prices">
          <span class="price-new">${money(d.price)}</span>
          ${d.old_price ? `<span class="price-old">${money(d.old_price)}</span>` : ""}
        </div>
        <div class="meta" title="${esc(absTime(d.found_at))}">${esc(d.store)} · bulundu: ${esc(relTime(d.found_at))}${d.source_label ? " · " + esc(d.source_label) : ""}</div>
        ${d.suspicious_reason ? `<div class="note">${esc(d.suspicious_reason)}</div>` : ""}
        <div class="actions">
          <a class="btn" href="${esc(d.url)}" target="_blank" rel="noopener" data-act="open">Aç ↗</a>
          <button class="btn" data-act="seen">${seen.has(d.id) ? "Görülmedi yap" : "Görüldü"}</button>
          <button class="btn" data-act="fav" aria-pressed="${favs.has(d.id)}">${favs.has(d.id) ? "★" : "☆"} Favori</button>
          <button class="btn" data-act="hide">${hidden.has(d.id) ? "Göster" : "Gizle"}</button>
        </div>
      </div>
    </article>`;
  }

  function render() {
    const st = els.store.value, cat = els.cat.value, min = Number(els.min.value), q = els.q.value.trim().toLowerCase();
    const onlyNew = els.onlyNew.getAttribute("aria-pressed") === "true";
    const onlyFav = els.onlyFav.getAttribute("aria-pressed") === "true";
    const showHidden = els.showHidden.getAttribute("aria-pressed") === "true";
    const hideSus = els.hideSus.getAttribute("aria-pressed") === "true";
    els.minVal.textContent = "%" + min + "+";
    const list = deals.filter((d) =>
      (!st || d.store === st) &&
      (!cat || d.category === cat) &&
      (d.discount || 0) >= min &&
      (!q || d.title.toLowerCase().includes(q)) &&
      (!onlyNew || (isNew(d) && !seen.has(d.id))) &&
      (!onlyFav || favs.has(d.id)) &&
      (!hideSus || !d.suspicious) &&
      (showHidden || !hidden.has(d.id)));
    els.count.textContent = `${list.length} indirim gösteriliyor` +
      (hidden.size() && !showHidden ? ` · ${hidden.size()} gizli` : "");
    els.grid.innerHTML = list.length ? list.map(card).join("") :
      '<div class="empty">Bu filtrelere uyan indirim yok. Filtreleri gevşetmeyi dene.</div>';
    saveFilters();
  }

  els.grid.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.closest(".card").dataset.id;
    const act = btn.dataset.act;
    if (act === "open") { seen.add(id); setTimeout(render, 50); return; }
    ev.preventDefault();
    if (act === "seen") seen.toggle(id);
    if (act === "fav") favs.toggle(id);
    if (act === "hide") hidden.toggle(id);
    render();
  });
  [els.store, els.cat, els.min].forEach((el) => el.addEventListener("input", render));
  els.q.addEventListener("input", render);
  [els.onlyNew, els.onlyFav, els.showHidden, els.hideSus].forEach((b) => b.addEventListener("click", () => {
    b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
    render();
  }));
  els.markAll.addEventListener("click", () => { deals.forEach((d) => seen.add(d.id)); render(); });

  loadJSON("data/deals.json").then((data) => {
    threshold = data.threshold || 30;
    deals = (data.deals || []).slice().sort((a, b) => (b.published_at || b.found_at || "").localeCompare(a.published_at || a.found_at || ""));
    fillSelect(els.store, [...new Set(deals.map((d) => d.store))].sort(), "Tüm mağazalar", saved.store);
    fillSelect(els.cat, [...new Set(deals.map((d) => d.category).filter(Boolean))].sort(), "Tüm kategoriler", saved.cat);
    els.min.min = threshold;
    els.min.value = Math.max(threshold, Number(saved.min) || threshold);
    if (saved.onlyNew) els.onlyNew.setAttribute("aria-pressed", "true");
    if (saved.onlyFav) els.onlyFav.setAttribute("aria-pressed", "true");
    if (saved.showHidden) els.showHidden.setAttribute("aria-pressed", "true");
    if (saved.hideSus) els.hideSus.setAttribute("aria-pressed", "true");
    const newCount = deals.filter((d) => isNew(d) && !seen.has(d.id)).length;
    els.meta.textContent = `Son güncelleme: ${absTime(data.generated_at)} (${relTime(data.generated_at)}) · eşik %${threshold}` +
      (lastVisitMs ? ` · son ziyaretinden beri ${newCount} yeni` : "");
    render();
  }).catch((e) => {
    els.grid.innerHTML = `<div class="empty">Veri yüklenemedi: ${esc(e.message)}</div>`;
  });
})();
