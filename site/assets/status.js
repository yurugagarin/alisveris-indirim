/* Durum sayfası: kaynak başına son başarılı çalışma ve hatalar. */
(function () {
  "use strict";
  const { relTime, absTime, esc, loadJSON } = window.App;
  const body = document.getElementById("rows");
  const meta = document.getElementById("meta");
  const banner = document.getElementById("banner");

  const label = {
    ok: '<span class="badge ok">çalışıyor</span>',
    warn: '<span class="badge sus">kısmen</span>',
    error: '<span class="badge bad">hata</span>',
    blocked: '<span class="badge bad">engellendi</span>',
    skipped: '<span class="badge">atlandı</span>',
  };

  loadJSON("data/status.json").then((s) => {
    const run = s.run || {};
    meta.textContent = `Son çalışma: ${absTime(run.finished_at)} (${relTime(run.finished_at)}) · süre ${run.duration_s ?? "—"} sn · ${run.http_requests ?? "—"} HTTP isteği`;
    const ageH = (Date.now() - new Date(run.finished_at).getTime()) / 3600e3;
    const bad = Object.values(s.sources || {}).filter((x) => x.state === "error" || x.state === "blocked");
    const msgs = [];
    if (ageH > 3) msgs.push(`Pipeline ${Math.round(ageH)} saattir çalışmadı (gece 23:00–07:00 arası normal).`);
    if (bad.length) msgs.push(`${bad.length} kaynakta sorun var.`);
    if (msgs.length) { banner.hidden = false; banner.textContent = msgs.join(" "); }
    const rows = Object.entries(s.sources || {}).sort((a, b) => a[1].name.localeCompare(b[1].name, "tr"));
    body.innerHTML = rows.map(([key, x]) => `<tr>
      <td data-label="Kaynak"><b>${esc(x.name)}</b><div class="note">${esc(x.detail || key)}</div></td>
      <td data-label="Durum">${label[x.state] || esc(x.state)}</td>
      <td data-label="Son başarılı" title="${esc(absTime(x.last_success))}">${esc(x.last_success ? relTime(x.last_success) : "hiç")}</td>
      <td data-label="Son deneme">${esc(relTime(x.last_run))}${x.items !== undefined ? ` · ${esc(x.items)} kayıt` : ""}</td>
      <td data-label="Mesaj">${esc(x.message || "")}${(x.errors || []).length ? `<ul class="errors">${x.errors.slice(-5).reverse().map((e) => `<li>${esc(absTime(e.t))}: ${esc(e.msg)}</li>`).join("")}</ul>` : ""}</td>
    </tr>`).join("");
  }).catch((e) => { body.innerHTML = `<tr><td colspan="5">Veri yüklenemedi: ${esc(e.message)}</td></tr>`; });
})();
