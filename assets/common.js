/* Ortak yardımcılar: tema, localStorage, biçimlendirme, veri yükleme. */
(function () {
  "use strict";

  // localStorage gizli pencerede veya engelli olabilir; her erişimi koru.
  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : JSON.parse(v);
      } catch (e) { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* yok say */ }
    },
  };

  // Görüldü / gizle / favori kümeleri
  function idSet(key) {
    const set = new Set(store.get(key, []));
    return {
      has: (id) => set.has(id),
      toggle(id) {
        if (set.has(id)) set.delete(id); else set.add(id);
        store.set(key, [...set].slice(-3000));
        return set.has(id);
      },
      add(id) { if (!set.has(id)) { set.add(id); store.set(key, [...set].slice(-3000)); } },
      size: () => set.size,
    };
  }

  // Tema: "auto" | "light" | "dark"
  function applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "light" || mode === "dark") root.setAttribute("data-theme", mode);
    else root.removeAttribute("data-theme");
  }
  applyTheme(store.get("theme", "auto"));

  function initThemeButton() {
    const btn = document.getElementById("theme-btn");
    if (!btn) return;
    const labels = { auto: "🌓", light: "☀️", dark: "🌙" };
    const names = { auto: "Tema: otomatik (sistem)", light: "Tema: açık", dark: "Tema: koyu" };
    const order = ["auto", "light", "dark"];
    const render = () => {
      const cur = store.get("theme", "auto");
      btn.textContent = labels[cur] || labels.auto;
      btn.title = names[cur] || names.auto;
      btn.setAttribute("aria-label", btn.title);
    };
    btn.addEventListener("click", () => {
      const cur = store.get("theme", "auto");
      const next = order[(order.indexOf(cur) + 1) % order.length];
      store.set("theme", next);
      applyTheme(next);
      render();
    });
    render();
  }

  const eur = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
  function money(v) { return v === null || v === undefined || isNaN(v) ? "—" : eur.format(v); }

  function relTime(iso) {
    if (!iso) return "—";
    const t = new Date(iso).getTime();
    const s = Math.round((Date.now() - t) / 1000);
    if (s < 60) return "az önce";
    const m = Math.round(s / 60);
    if (m < 60) return m + " dk önce";
    const h = Math.round(m / 60);
    if (h < 24) return h + " saat önce";
    const d = Math.round(h / 24);
    if (d < 30) return d + " gün önce";
    return new Date(iso).toLocaleDateString("tr-TR");
  }

  function absTime(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("tr-TR", {
      timeZone: "Europe/Berlin", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function loadJSON(path) {
    const r = await fetch(path + "?v=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error(path + " yüklenemedi (" + r.status + ")");
    return r.json();
  }

  document.addEventListener("DOMContentLoaded", initThemeButton);

  window.App = { store, idSet, money, relTime, absTime, esc, loadJSON };
})();
