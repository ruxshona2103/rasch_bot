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
  if (tg.colorScheme) {
    document.documentElement.dataset.theme = tg.colorScheme;
  }
  if (tg.onEvent) {
    tg.onEvent("themeChanged", () => {
      document.documentElement.dataset.theme = tg.colorScheme;
    });
  }

  const initData = tg.initData || "";
  const params = new URLSearchParams(window.location.search);
  const testId = params.get("test_id");

  if (!initData) {
    showError("Sessiya aniqlanmadi. Botni qayta oching.");
    return;
  }
  if (!testId) {
    showError("Test tanlanmagan. Botdagi test ro'yxatidan \"Kirish\" tugmasini bosing.");
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

  async function apiPost(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Xatolik yuz berdi.");
    return data;
  }

  let state = { test: null, questions: [], attemptId: null, answers: {} };

  async function boot() {
    const data = await apiGet(`/api/tests/${encodeURIComponent(testId)}`);
    if (data.finished) {
      render(`<div class="error">✅ Siz bu testni allaqachon yakunlagansiz. Natijangizni botda "📊 Natijalarim" bo'limidan ko'ring.</div>`);
      return;
    }
    state.test = data.test;
    state.questions = data.questions;
    state.answers = data.answers || {};

    if (data.attempt) {
      state.attemptId = data.attempt.attempt_id;
    } else {
      const started = await apiPost("/api/attempt/start", { test_id: Number(testId) });
      state.attemptId = started.attempt_id;
    }

    renderExam();
  }

  function answeredCount() {
    return Object.keys(state.answers).length;
  }

  function renderExam() {
    const total = state.questions.length;
    const answered = answeredCount();
    const pct = total ? Math.round((answered / total) * 100) : 0;

    const questionsHtml = state.questions
      .map((q) => renderQuestion(q))
      .join("");

    render(`
      <div class="header">
        <h1>📝 ${escapeHtml(state.test.title)}</h1>
        <div class="progress-bar"><div style="width:${pct}%"></div></div>
        <div class="progress-text" id="progressText">✅ Belgilangan: ${answered} / ${total}</div>
      </div>
      <div id="questions">${questionsHtml}</div>
      <div class="footer">
        <button class="finish-btn" id="finishBtn">🏁 Yakunlash</button>
      </div>
    `);

    document.getElementById("finishBtn").addEventListener("click", onFinish);
    state.questions.forEach((q) => wireQuestion(q));
  }

  function renderQuestion(q) {
    const current = state.answers[q.order_num];
    if (q.qtype === "yopiq") {
      const letters = Array.from({ length: q.option_count }, (_, i) => String.fromCharCode(65 + i));
      const gridClass = q.option_count > 4 ? "options opt6" : "options";
      const buttons = letters
        .map(
          (l) =>
            `<button type="button" class="opt-btn${current === l ? " selected" : ""}" data-order="${q.order_num}" data-letter="${l}">${l}</button>`
        )
        .join("");
      return `
        <div class="question" data-order="${q.order_num}">
          <div class="qnum">${q.order_num}-savol</div>
          <div class="${gridClass}">${buttons}</div>
          <div class="save-hint" id="hint-${q.order_num}"></div>
        </div>
      `;
    }
    return `
      <div class="question" data-order="${q.order_num}">
        <div class="qnum">${q.order_num}-savol (ochiq)</div>
        <input
          class="open-input"
          type="text"
          inputmode="text"
          placeholder="Masalan: 12, 1/2, √2, 2*pi"
          value="${current ? escapeHtml(current) : ""}"
          data-order="${q.order_num}"
        />
        <div class="save-hint" id="hint-${q.order_num}"></div>
      </div>
    `;
  }

  function setHint(orderNum, text, cls) {
    const el = document.getElementById(`hint-${orderNum}`);
    if (!el) return;
    el.textContent = text;
    el.className = "save-hint" + (cls ? " " + cls : "");
  }

  function updateProgress() {
    const total = state.questions.length;
    const answered = answeredCount();
    const pct = total ? Math.round((answered / total) * 100) : 0;
    const bar = document.querySelector(".progress-bar > div");
    if (bar) bar.style.width = pct + "%";
    const text = document.getElementById("progressText");
    if (text) text.textContent = `✅ Belgilangan: ${answered} / ${total}`;
  }

  async function submitAnswer(orderNum, answer) {
    setHint(orderNum, "saqlanmoqda...");
    try {
      await apiPost("/api/answer", { attempt_id: state.attemptId, order_num: orderNum, answer });
      state.answers[orderNum] = answer;
      setHint(orderNum, "✅ saqlandi", "ok");
      updateProgress();
    } catch (e) {
      setHint(orderNum, "❌ " + e.message, "err");
    }
  }

  function wireQuestion(q) {
    const card = document.querySelector(`.question[data-order="${q.order_num}"]`);
    if (!card) return;

    if (q.qtype === "yopiq") {
      card.querySelectorAll(".opt-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          card.querySelectorAll(".opt-btn").forEach((b) => b.classList.remove("selected"));
          btn.classList.add("selected");
          submitAnswer(q.order_num, btn.dataset.letter);
        });
      });
    } else {
      const input = card.querySelector(".open-input");
      let timer = null;
      input.addEventListener("input", () => {
        clearTimeout(timer);
        setHint(q.order_num, "");
        timer = setTimeout(() => {
          const val = input.value.trim();
          if (val) submitAnswer(q.order_num, val);
        }, 700);
      });
      input.addEventListener("blur", () => {
        clearTimeout(timer);
        const val = input.value.trim();
        if (val) submitAnswer(q.order_num, val);
      });
    }
  }

  async function onFinish() {
    const total = state.questions.length;
    const unanswered = total - answeredCount();
    const ok = window.confirm(
      unanswered > 0
        ? `⚠️ ${unanswered} savol belgilanmagan. Rostdanmi yakunlaymiz?`
        : "Testni yakunlaysizmi?"
    );
    if (!ok) return;

    try {
      const result = await apiPost("/api/finish", { attempt_id: state.attemptId });
      if (result.mode === "arxiv") {
        render(`
          <div class="header"><h1>✅ Test yakunlandi!</h1></div>
          <div class="question">
            <div class="qnum">🏆 Ball: ${result.ball_75} / 75</div>
            <div class="qnum">🎖 Daraja: ${result.grade || "chegaradan past"}</div>
            <pre style="white-space:pre-wrap;font-family:inherit;">${escapeHtml(result.breakdown)}</pre>
          </div>
        `);
      } else {
        render(`
          <div class="header"><h1>✅ Test yakunlandi!</h1></div>
          <div class="question">⏳ Natijalar test admin tomonidan yakunlangach e'lon qilinadi.</div>
        `);
      }
      if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (e) {
      showError(e.message);
    }
  }

  boot().catch((e) => showError(e.message));
})();
