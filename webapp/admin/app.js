(function () {
  "use strict";

  const app = document.getElementById("app");
  const tg = window.Telegram && window.Telegram.WebApp;

  function render(html) {
    app.innerHTML = html;
  }
  function showError(message) {
    render(`<div class="error">⚠️ ${escapeHtml(message)}</div>`);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  if (!tg) {
    showError("Bu sahifa Telegram ichidan ochilishi kerak.");
    return;
  }
  tg.ready();
  tg.expand();
  if (tg.colorScheme) document.documentElement.dataset.theme = tg.colorScheme;
  if (tg.onEvent) {
    tg.onEvent("themeChanged", () => {
      document.documentElement.dataset.theme = tg.colorScheme;
    });
  }

  const initData = tg.initData || "";
  if (!initData) {
    showError("Sessiya aniqlanmadi. Botni qayta oching.");
    return;
  }

  function authHeaders(extra) {
    return Object.assign({ Authorization: "tma " + initData }, extra || {});
  }
  async function apiGet(url) {
    const res = await fetch(url, { headers: authHeaders() });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Xatolik yuz berdi.");
    return data;
  }
  async function apiPost(url) {
    const res = await fetch(url, { method: "POST", headers: authHeaders() });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Xatolik yuz berdi.");
    return data;
  }

  const STATUS_LABELS = {
    tayyorlanmoqda: "🛠 Tayyorlanmoqda",
    rejalashtirilgan: "🗓 Rejalashtirilgan",
    jonli_davom: "🔴 Jonli davom",
    hisoblanmoqda: "⏳ Hisoblanmoqda",
    yakunlangan: "✅ Yakunlangan",
    arxivda: "📚 Arxivda",
    bekor_qilingan: "🚫 Bekor qilingan",
  };

  async function showTestList() {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const data = await apiGet("/api/admin/tests");
      if (!data.tests.length) {
        render(`<div class="header"><h1>👨‍💼 Testlar</h1></div><div class="empty">Hozircha testlar yo'q.</div>`);
        return;
      }
      const cards = data.tests
        .map(
          (t) => `
            <div class="card" data-id="${t.id}">
              <div class="title">${escapeHtml(t.title)}<span class="badge">${STATUS_LABELS[t.status] || t.status}</span></div>
              <div class="meta">👥 ${t.participants} ta ishtirokchi · ${t.mode === "jonli" ? "🔴 Jonli" : "📚 Arxiv"}</div>
            </div>
          `
        )
        .join("");
      render(`<div class="header"><h1>👨‍💼 Testlar</h1></div>${cards}`);
      document.querySelectorAll(".card").forEach((el) => {
        el.addEventListener("click", () => showTestResults(el.dataset.id));
      });
    } catch (e) {
      showError(e.message);
    }
  }

  async function showTestResults(testId) {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const data = await apiGet(`/api/admin/tests/${testId}`);
      const gradeStats = Object.entries(data.grade_counts)
        .map(([grade, count]) => `<div class="stat"><div class="num">${count}</div><div class="label">${escapeHtml(grade)}</div></div>`)
        .join("");

      const rowsHtml = (results) =>
        results
          .map(
            (r) => `
              <tr>
                <td>${r.rank ?? "-"}</td>
                <td>${escapeHtml(r.full_name)}${r.username ? " (@" + escapeHtml(r.username) + ")" : ""}</td>
                <td>${r.grade || "-"}</td>
                <td>${r.ball_75 ?? "-"}</td>
              </tr>
            `
          )
          .join("");

      render(`
        <button class="back-btn" id="backBtn">⬅️ Testlar ro'yxatiga qaytish</button>
        <div class="header"><h1>${escapeHtml(data.test.title)}</h1></div>
        <div class="stats-row">
          <div class="stat"><div class="num">${data.participants}</div><div class="label">Jami</div></div>
          ${gradeStats}
        </div>
        <button class="export-btn" id="exportBtn">📊 Excel'ni botga yuborish</button>
        <input class="search-input" id="searchInput" placeholder="Ism bo'yicha qidirish..." />
        <table>
          <thead><tr><th>#</th><th>F.I.O</th><th>Daraja</th><th>Ball</th></tr></thead>
          <tbody id="resultsBody">${rowsHtml(data.results)}</tbody>
        </table>
      `);

      document.getElementById("backBtn").addEventListener("click", showTestList);
      document.getElementById("searchInput").addEventListener("input", (e) => {
        const q = e.target.value.trim().toLowerCase();
        const filtered = data.results.filter((r) => r.full_name.toLowerCase().includes(q));
        document.getElementById("resultsBody").innerHTML = rowsHtml(filtered);
      });
      document.getElementById("exportBtn").addEventListener("click", async () => {
        const btn = document.getElementById("exportBtn");
        btn.disabled = true;
        btn.textContent = "⏳ Yuborilmoqda...";
        try {
          await apiPost(`/api/admin/tests/${testId}/export`);
          btn.textContent = "✅ Botga yuborildi";
          if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        } catch (e) {
          btn.textContent = "❌ " + e.message;
          btn.disabled = false;
        }
      });
    } catch (e) {
      showError(e.message);
    }
  }

  showTestList();
})();
