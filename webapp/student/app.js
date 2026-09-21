(function () {
  "use strict";

  const app = document.getElementById("app");
  const keypad = document.getElementById("keypad");
  const toastEl = document.getElementById("toast");
  const tabbar = document.getElementById("tabbar");
  const tg = window.Telegram && window.Telegram.WebApp;

  const BRAND = `<div class="brand">🎓 Abdurashid Teacher bilan hammasi oson<small>Milliy sertifikat mock testlari</small></div>`;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  function render(html) { app.innerHTML = html; window.scrollTo(0, 0); }
  function showError(m) { render(`<div class="error">⚠️ ${esc(m)}</div>`); }
  let toastTimer = null;
  function toastOk(m) { toast(m, true); }
  function toast(m, ok) {
    toastEl.textContent = m; toastEl.hidden = false;
    toastEl.style.background = ok ? "var(--ok)" : "";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3000);
  }

  if (!tg) { showError("Bu sahifa Telegram ichidan ochilishi kerak."); tabbar.hidden = true; return; }
  tg.ready(); tg.expand();
  const applyTheme = () => { if (tg.colorScheme) document.documentElement.dataset.theme = tg.colorScheme; };
  applyTheme();
  if (tg.onEvent) tg.onEvent("themeChanged", applyTheme);

  const initData = tg.initData || "";
  if (!initData) { showError("Sessiya aniqlanmadi. Botni qayta oching."); tabbar.hidden = true; return; }

  const H = (extra) => Object.assign({ Authorization: "tma " + initData }, extra || {});
  async function apiGet(url) {
    const r = await fetch(url, { headers: H() });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || "Xatolik yuz berdi.");
    return d;
  }
  async function apiPost(url, body) {
    const r = await fetch(url, { method: "POST", headers: H({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || "Xatolik yuz berdi.");
    return d;
  }
  const buzz = (t) => { if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred(t); };

  /* ------------------------------ ilmiy klaviatura (kalkulyator) ------------------------------ */
  const SCI = [
    ["(", ")", "mc", "m+", "m-", "mr"],
    ["2nd", "x²", "x³", "xʸ", "eˣ", "10ˣ"],
    ["1/x", "²√x", "³√x", "ʸ√x", "ln", "log₁₀"],
    ["x!", "sin", "cos", "tg", "e", "EE"],
    ["Rand", "sh", "ch", "th", "π", "Rad"],
    ["°", ";", "ctg", "|x|", "^", "x⁻¹"],
  ];
  const MAIN = [
    ["⌫", "AC", "%", "÷"],
    ["7", "8", "9", "×"],
    ["4", "5", "6", "−"],
    ["1", "2", "3", "+"],
    ["±", "0", ",", "="],
  ];
  const kp = { second: false, deg: false, mem: null, sci: window.innerHeight >= 780 };
  let kpTarget = null;
  let kpOpen = false;

  const FN_KEYS = { sin: "sin", cos: "cos", tg: "tg", sh: "sh", ch: "ch", th: "th" };
  const INV = { sin: "asin", cos: "acos", tg: "atan", sh: "asinh", ch: "acosh", th: "atanh" };
  const INV_LABEL = { sin: "sin⁻¹", cos: "cos⁻¹", tg: "tg⁻¹", sh: "sh⁻¹", ch: "ch⁻¹", th: "th⁻¹" };
  const TRIG = ["sin", "cos", "tg"];

  function keyLabel(k) {
    if (kp.second && INV_LABEL[k]) return INV_LABEL[k];
    if (kp.second && k === "eˣ") return "2ˣ";
    if (kp.second && k === "ln") return "log₂";
    if (k === "Rad") return kp.deg ? "Deg" : "Rad";
    return k;
  }
  // Tugma bosilganda kiritiladigan matn (null -- maxsus amal)
  function keyInsert(k) {
    const map = {
      "÷": "/", "×": "*", "−": "-", "x²": "^2", "x³": "^3", "xʸ": "^(", "10ˣ": "10^(", "1/x": "1/(",
      "²√x": "√(", "³√x": "∛(", "ʸ√x": "root(", "log₁₀": "log10(", "x!": "!", "EE": "E", "|x|": "abs(", "x⁻¹": "^(-1)",
    };
    if (k === "eˣ") return kp.second ? "2^(" : "e^(";
    if (k === "ln") return kp.second ? "log2(" : "ln(";
    if (k === "ctg") return kp.deg ? "ctgd(" : "ctg(";
    if (FN_KEYS[k]) {
      const base = kp.second ? INV[k] : k;
      const withDeg = kp.deg && (TRIG.includes(k)) ? base + "d" : base;
      return withDeg + "(";
    }
    if (k === "Rand") return String(Math.round(Math.random() * 10000) / 10000);
    if (map[k]) return map[k];
    if (["2nd", "Rad", "AC", "⌫", "±", "=", "mc", "m+", "m-", "mr"].includes(k)) return null;
    return k;
  }

  function buildKeypad() {
    const grid = (rows, cols, cls) => `<div class="grid ${cls}" style="grid-template-columns:repeat(${cols},1fr)">${rows.flat().map((k) => {
      let c = "";
      if (k === "=" || k === "÷" || k === "×" || k === "−" || k === "+") c = "op";
      else if (["⌫", "AC", "%", "±"].includes(k)) c = "gray";
      else if (/^[0-9,]$/.test(k)) c = "digit";
      else c = "fn";
      if (k === "2nd" && kp.second) c += " active";
      if (k === "mr" && kp.mem !== null) c += " active";
      if (k === "Rad" && kp.deg) c += " active";
      return `<button type="button" class="${c}" data-k="${esc(k)}">${esc(keyLabel(k))}</button>`;
    }).join("")}</div>`;
    keypad.innerHTML = `
      <div class="kp-head">
        <button type="button" class="kp-fx" data-k="__sci">${kp.sci ? "🔬 Ilmiy: yoqilgan" : "🔬 Ilmiy tugmalar"}</button>
        <span class="kp-mode">${kp.deg ? "Deg (gradus)" : "Rad (radian)"}${kp.mem !== null ? " · M" : ""}</span>
        <button type="button" class="kp-close" data-k="__close">✕ Yopish</button>
      </div>
      <div class="kp-scroll">${kp.sci ? grid(SCI, 6, "sci") : ""}${grid(MAIN, 4, "main")}</div>`;
    keypad.querySelectorAll("button").forEach((b) => {
      b.addEventListener("pointerdown", (e) => e.preventDefault());
      b.addEventListener("click", () => pressKey(b.dataset.k));
    });
    if (kpOpen) document.body.style.paddingBottom = keypad.offsetHeight + 24 + "px";
  }
  function setNativeKb(on) {
    document.querySelectorAll(".open-input").forEach((i) => i.setAttribute("inputmode", on ? "text" : "none"));
  }
  function openKeypad(input) {
    kpTarget = input; kpOpen = true;
    keypad.hidden = false; setNativeKb(false);
    input.focus();
    document.body.style.paddingBottom = keypad.offsetHeight + 24 + "px";
    input.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  function closeKeypad() {
    kpOpen = false; keypad.hidden = true; setNativeKb(true);
    document.body.style.paddingBottom = "";
  }
  function fmtNum(v) { return String(Number(v.toPrecision(12))); }
  function rowOf(el) { const r = el.closest(".qrow"); return r ? Number(r.dataset.order) : null; }

  function insertText(el, text) {
    const s = el.selectionStart == null ? el.value.length : el.selectionStart;
    const e = el.selectionEnd == null ? el.value.length : el.selectionEnd;
    el.value = el.value.slice(0, s) + text + el.value.slice(e);
    el.setSelectionRange(s + text.length, s + text.length);
    el.dispatchEvent(new Event("input"));
  }

  function pressKey(k) {
    if (k === "__close") { closeKeypad(); if (kpTarget) kpTarget.blur(); return; }
    if (k === "__sci") { kp.sci = !kp.sci; buildKeypad(); return; }
    if (k === "2nd") { kp.second = !kp.second; buildKeypad(); return; }
    if (k === "Rad") { kp.deg = !kp.deg; buildKeypad(); return; }
    if (!kpTarget) return;
    const el = kpTarget;
    const order = rowOf(el);

    if (k === "AC") { el.value = ""; el.dispatchEvent(new Event("input")); return; }
    if (k === "⌫") {
      const s = el.selectionStart == null ? el.value.length : el.selectionStart;
      const e = el.selectionEnd == null ? el.value.length : el.selectionEnd;
      if (s !== e) el.value = el.value.slice(0, s) + el.value.slice(e);
      else if (s > 0) { el.value = el.value.slice(0, s - 1) + el.value.slice(s); el.setSelectionRange(s - 1, s - 1); }
      el.dispatchEvent(new Event("input"));
      return;
    }
    if (k === "±") {
      el.value = el.value.startsWith("-") ? el.value.slice(1) : "-" + el.value;
      el.dispatchEvent(new Event("input"));
      return;
    }
    if (k === "=" || k === "m+" || k === "m-") {
      const v = window.evalMath(el.value);
      if (v === null) { if (!setHint(order, "❌ Ifoda hisoblanmadi", "err")) toast("Ifoda hisoblanmadi"); return; }
      if (k === "=") { setHint(order, "= " + fmtNum(v), "calc"); return; }
      kp.mem = (kp.mem || 0) + (k === "m+" ? v : -v);
      setHint(order, "M = " + fmtNum(kp.mem), "calc");
      buildKeypad();
      return;
    }
    if (k === "mc") { kp.mem = null; setHint(order, "Xotira tozalandi", "calc"); buildKeypad(); return; }
    if (k === "mr") {
      if (kp.mem === null) { toast("Xotira bo'sh"); return; }
      insertText(el, kp.mem < 0 ? `(${fmtNum(kp.mem)})` : fmtNum(kp.mem));
      return;
    }
    const text = keyInsert(k);
    if (text !== null) insertText(el, text);
  }
  buildKeypad();

  /* ------------------------------ tab navigatsiya ------------------------------ */
  let currentTab = "home";
  function setTab(tab) {
    currentTab = tab;
    closeKeypad();
    tabbar.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    if (tab === "home") showHome();
    else if (tab === "results") showResultsList();
    else showProfile();
  }
  tabbar.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));

  /* ------------------------------ bosh sahifa ------------------------------ */
  async function showHome() {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const d = await apiGet("/api/my-tests");
      if (!d.tests.length) {
        render(`<div class="hero"><h1>👋 Xush kelibsiz!</h1><div class="who">Hozircha sizda faol testlar yo'q. Botdagi "Jonli/Arxiv testlar" bo'limidan test tanlang.</div></div>${BRAND}`);
        return;
      }
      const cards = d.tests.map((t) => {
        let action = "";
        if (t.can_enter) action = `<button class="btn" data-enter="${t.id}">▶️ Testni boshlash</button>`;
        else if (t.finished) action = `<div class="meta" style="margin-top:8px">✅ Topshirilgan${t.ball_75 != null ? ` · <b>${t.ball_75}</b> ball ${t.grade ? "· " + esc(t.grade) : ""}` : " · natija kutilmoqda"}</div>`;
        else action = `<div class="meta" style="margin-top:8px">⏳ Hali boshlanmagan</div>`;
        return `<div class="card"><div class="title">${esc(t.title)}</div>
          <div class="meta"><span class="pill">${t.mode === "jonli" ? "🔴 Jonli" : "📚 Arxiv"}</span></div>${action}</div>`;
      }).join("");
      render(`<div class="hero"><div class="who">Mening testlarim</div><h1>📝 Testlar</h1></div>${cards}${BRAND}`);
      app.querySelectorAll("[data-enter]").forEach((b) => b.addEventListener("click", () => startExam(b.dataset.enter)));
    } catch (e) { showError(e.message); }
  }

  /* ------------------------------ imtihon ------------------------------ */
  let exam = null;

  async function startExam(testId) {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    currentTab = "home";
    tabbar.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === "home"));
    try {
      const d = await apiGet(`/api/tests/${encodeURIComponent(testId)}`);
      if (d.finished) {
        render(`<div class="hero"><div class="who">${esc(d.user.full_name)}</div><h1>✅ Siz bu testni yakunlagansiz</h1></div>
          <div class="card">Natijangizni "Natijalar" yoki "Profil" bo'limidan ko'rishingiz mumkin.</div>${BRAND}`);
        return;
      }
      exam = { test: d.test, user: d.user, questions: d.questions, answers: d.answers || {}, attemptId: null };
      if (d.attempt) exam.attemptId = d.attempt.attempt_id;
      else exam.attemptId = (await apiPost("/api/attempt/start", { test_id: Number(testId) })).attempt_id;
      renderExam();
      startHeartbeat();
    } catch (e) { showError(e.message); }
  }

  const answered = () => Object.keys(exam.answers).length;

  // Ilova ochiq ekanini serverga bildirib turamiz; 5 daqiqa signal bo'lmasa server
  // qoralama javoblarni o'chiradi (yopib ketilgan/aloqa uzilgan holat).
  let hbTimer = null;
  function stopHeartbeat() { clearInterval(hbTimer); hbTimer = null; }
  async function beat() {
    if (!exam || !exam.attemptId) return;
    try {
      const r = await apiPost("/api/heartbeat", { attempt_id: exam.attemptId });
      if (r.finished) { stopHeartbeat(); return; }
      if (r.cleared) {
        exam.answers = {};
        if (currentTab === "home" && document.querySelector(".finish-btn")) renderExam();
        toast("Uzoq vaqt aloqa bo'lmadi: javoblar tozalandi, qaytadan kiriting.");
      }
    } catch (e) { /* aloqa yo'q -- keyingi urinishda */ }
  }
  function startHeartbeat() {
    stopHeartbeat();
    hbTimer = setInterval(beat, 20000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) beat(); });
  }

  function renderExam() {
    const total = exam.questions.length;
    const groups = [];
    exam.questions.forEach((q) => {
      const last = groups[groups.length - 1];
      const key = q.qtype === "yopiq" ? "c" + q.option_count : "o";
      if (last && last.key === key) last.items.push(q); else groups.push({ key, items: [q] });
    });
    const sheets = groups.map((g) => {
      const title = g.key === "o" ? "Ochiq savollar — javobni yozing" : `Yopiq savollar (A–${String.fromCharCode(64 + Number(g.key.slice(1)))})`;
      return `<div class="section-title">${title}</div><div class="sheet">${g.items.map(rowHtml).join("")}</div>`;
    }).join("");

    render(`
      <div class="hero">
        <div class="who">👤 ${esc(exam.user.full_name)}</div>
        <h1>${esc(exam.test.title)}</h1>
        <div class="progress-bar"><div id="pbar" style="width:0%"></div></div>
        <div class="progress-text" id="ptext"></div>
      </div>
      ${sheets}
      ${BRAND}
      <div class="footer"><div class="in"><button class="finish-btn" id="finishBtn">🏁 Testni yakunlash</button></div></div>
    `);
    updateProgress(total);
    document.getElementById("finishBtn").addEventListener("click", onFinish);
    exam.questions.forEach(wireRow);
  }

  function rowHtml(q) {
    const cur = exam.answers[q.order_num];
    const saved = cur ? " saved" : "";
    if (q.qtype === "yopiq") {
      const letters = Array.from({ length: q.option_count }, (_, i) => String.fromCharCode(65 + i));
      return `<div class="qrow" data-order="${q.order_num}"><div class="qn${saved}" id="qn-${q.order_num}">${q.order_num}.</div>
        <div class="opts">${letters.map((l) => `<button type="button" class="opt-btn${cur === l ? " selected" : ""}" data-l="${l}">${l}</button>`).join("")}</div></div>`;
    }
    return `<div class="qrow open" data-order="${q.order_num}"><div class="qn${saved}" id="qn-${q.order_num}">${q.order_num}.</div>
      <div class="open-col"><div class="open-wrap"><input class="open-input" type="text" autocomplete="off" autocapitalize="off" placeholder="Javob..." value="${esc(cur || "")}" />
      <button type="button" class="kb-btn" title="Matematik klaviatura">⌨️</button></div>
      <div class="preview" id="pv-${q.order_num}">${cur && window.mathToHtml ? window.mathToHtml(cur) : ""}</div>
      <div class="hint" id="hint-${q.order_num}"></div></div></div>`;
  }

  function updateProgress(total) {
    const n = answered();
    total = total || exam.questions.length;
    document.getElementById("pbar").style.width = (total ? Math.round((n / total) * 100) : 0) + "%";
    document.getElementById("ptext").textContent = `✅ Belgilangan: ${n} / ${total}`;
  }

  function mark(order, cls) {
    const el = document.getElementById("qn-" + order);
    if (!el) return;
    el.className = "qn" + (cls ? " " + cls : "");
  }

  function setHint(order, text, cls) {
    const el = document.getElementById("hint-" + order);
    if (!el) return false;
    el.textContent = text;
    el.className = "hint" + (cls ? " " + cls : "");
    return true;
  }

  // silent=true: yozib turilganda (yarim ifoda bo'lishi mumkin) xato ko'rsatilmaydi
  async function save(order, answer, silent) {
    try {
      await apiPost("/api/answer", { attempt_id: exam.attemptId, order_num: order, answer });
      exam.answers[order] = answer;
      mark(order, "saved");
      setHint(order, "");
      updateProgress();
    } catch (e) {
      if (silent) { mark(order, "pend"); return; }
      mark(order, "err");
      buzz("error");
      if (!setHint(order, "❌ " + e.message, "err")) toast(`${order}-savol: ${e.message}`);
    }
  }

  function wireRow(q) {
    const row = document.querySelector(`.qrow[data-order="${q.order_num}"]`);
    if (!row) return;
    if (q.qtype === "yopiq") {
      row.querySelectorAll(".opt-btn").forEach((b) => b.addEventListener("click", () => {
        row.querySelectorAll(".opt-btn").forEach((x) => x.classList.remove("selected"));
        b.classList.add("selected");
        if (tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
        save(q.order_num, b.dataset.l);
      }));
      return;
    }
    const input = row.querySelector(".open-input");
    const preview = document.getElementById("pv-" + q.order_num);
    let t = null;
    const fix = () => {
      // Kompyuter tilida "/" o'rniga chiqadigan belgilarni to'g'rilaymiz
      const v = input.value;
      const nv = v.replace(/[?÷:]/g, "/").replace(/×/g, "*").replace(/[−–—]/g, "-");
      if (nv !== v) {
        const pos = input.selectionStart;
        input.value = nv;
        input.setSelectionRange(pos, pos);
      }
    };
    input.addEventListener("focus", () => { kpTarget = input; if (kpOpen) setNativeKb(false); });
    input.addEventListener("keydown", (e) => {
      if (e.ctrlKey && (e.key === "/" || e.code === "Slash")) {
        e.preventDefault();
        const p = input.selectionStart;
        input.value = input.value.slice(0, p) + "/" + input.value.slice(input.selectionEnd);
        input.setSelectionRange(p + 1, p + 1);
        input.dispatchEvent(new Event("input"));
      }
    });
    input.addEventListener("input", () => {
      fix();
      if (preview) preview.innerHTML = window.mathToHtml ? window.mathToHtml(input.value) : "";
      clearTimeout(t); mark(q.order_num, ""); setHint(q.order_num, "");
      t = setTimeout(() => { const v = input.value.trim(); if (v) save(q.order_num, v, true); }, 700);
    });
    input.addEventListener("blur", () => {
      clearTimeout(t);
      const v = input.value.trim();
      if (v && v !== exam.answers[q.order_num]) save(q.order_num, v, false);
    });
    row.querySelector(".kb-btn").addEventListener("click", () => (kpOpen && kpTarget === input ? closeKeypad() : openKeypad(input)));
  }

  function onFinish() {
    const left = exam.questions.length - answered();
    const bad = document.querySelectorAll(".qn.err, .qn.pend").length;
    let msg = left > 0 ? `⚠️ ${left} savol belgilanmagan. Rostdan yakunlaymizmi?` : "Testni yakunlaysizmi?";
    if (bad > 0) msg = `⚠️ ${bad} ta javob noto'g'ri yozilgani uchun saqlanmagan. ` + msg;
    const go = async () => {
      try {
        const r = await apiPost("/api/finish", { attempt_id: exam.attemptId });
        closeKeypad(); stopHeartbeat(); buzz("success");
        if (r.mode === "arxiv") {
          render(`<div class="hero"><div class="who">👤 ${esc(exam.user.full_name)}</div><h1>✅ Test yakunlandi!</h1></div>
            <div class="stats"><div class="stat"><div class="num">${r.ball_75}</div><div class="label">Ball / 75</div></div>
            <div class="stat"><div class="num">${esc(r.grade || "—")}</div><div class="label">Daraja</div></div>
            <div class="stat"><div class="num">🏆</div><div class="label">Natija</div></div></div>
            <div class="card"><pre style="white-space:pre-wrap;font-family:inherit;margin:0">${esc(r.breakdown)}</pre></div>
            <button class="btn" id="certBtn">📄 Sertifikatni (PDF) botga yuborish</button>${BRAND}`);
          document.getElementById("certBtn").addEventListener("click", (e) => sendCertificate(r.attempt_id, e.target));
        } else {
          render(`<div class="hero"><div class="who">👤 ${esc(exam.user.full_name)}</div><h1>✅ Test yakunlandi!</h1></div>
            <div class="card">⏳ Natijalar test admin tomonidan yakunlangach e'lon qilinadi. Botga umumiy natija xabari keladi.</div>${BRAND}`);
        }
      } catch (e) { toast(e.message); }
    };
    if (tg.showConfirm) tg.showConfirm(msg, (ok) => { if (ok) go(); });
    else if (window.confirm(msg)) go();
  }

  /* ------------------------------ natijalar ------------------------------ */
  async function showResultsList() {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const d = await apiGet("/api/results");
      if (!d.tests.length) { render(`<div class="hero"><h1>📊 Natijalar</h1></div><div class="empty">Hozircha e'lon qilingan natijalar yo'q.</div>${BRAND}`); return; }
      const cards = d.tests.map((t) => `
        <div class="card click" data-id="${t.id}"><div class="title">${esc(t.title)}</div>
          <div class="meta"><span>👥 ${t.participants} kishi</span><span class="pill">${t.mode === "jonli" ? "🔴 Jonli" : "📚 Arxiv"}</span></div>
          <button class="btn ghost">Natijalarni ko'rish →</button></div>`).join("");
      render(`<div class="hero"><div class="who">Test natijalari</div><h1>📊 Natijalar</h1></div>${cards}${BRAND}`);
      app.querySelectorAll(".card.click").forEach((c) => c.addEventListener("click", () => showResultDetail(c.dataset.id)));
    } catch (e) { showError(e.message); }
  }

  async function showResultDetail(id) {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const d = await apiGet(`/api/results/${id}`);
      const medal = (r) => (r === 1 ? "🥇" : r === 2 ? "🥈" : r === 3 ? "🥉" : r ?? "-");
      const rows = (list) => list.map((r) => `<div class="lb-row${r.is_me ? " me" : ""}"><div class="lb-rank">${medal(r.rank)}</div>
        <div class="lb-name">${esc(r.full_name)}${r.is_me ? " (siz)" : ""}</div><div class="lb-grade">${esc(r.grade || "—")}</div><div class="lb-ball">${r.ball_75 ?? "-"}</div></div>`).join("");
      const grades = Object.entries(d.grade_counts).map(([g, c]) => `<div class="stat"><div class="num">${c}</div><div class="label">${esc(g)}</div></div>`).join("");
      render(`<button class="back-btn" id="bk">⬅️ Orqaga</button>
        <div class="hero"><div class="who">Test natijalari</div><h1>${esc(d.test.title)}</h1><div class="progress-text">👥 Ishtirokchilar: ${d.participants}</div></div>
        <div class="section-title">Daraja bo'yicha</div><div class="stats">${grades}</div>
        <input class="search-input" id="q" placeholder="🔍 Ism bo'yicha qidirish" />
        <div class="sheet" id="lb">${rows(d.results)}</div>${BRAND}`);
      document.getElementById("bk").addEventListener("click", showResultsList);
      document.getElementById("q").addEventListener("input", (e) => {
        const q = e.target.value.trim().toLowerCase();
        document.getElementById("lb").innerHTML = rows(d.results.filter((r) => r.full_name.toLowerCase().includes(q)));
      });
    } catch (e) { showError(e.message); }
  }

  /* ------------------------------ profil ------------------------------ */
  async function showProfile() {
    render(`<div class="loading">Yuklanmoqda...</div>`);
    try {
      const d = await apiGet("/api/me");
      const best = d.results.reduce((m, r) => Math.max(m, r.ball_75 || 0), 0);
      const list = d.results.map((r) => `<div class="lb-row"><div class="lb-rank">${r.rank ?? "-"}</div>
        <div class="lb-name">${esc(r.title)}<div class="meta">${esc(r.date)}</div></div><div class="lb-grade">${esc(r.grade || "—")}</div><div class="lb-ball">${r.ball_75}</div>
        <button class="cert-btn" data-cert="${r.attempt_id}" title="Sertifikat (PDF)">📄</button></div>`).join("");
      const last = d.results.slice(-8);
      const bars = last.length ? `<div class="section-title">O'sish dinamikasi</div><div class="card"><div class="bars">${last.map((r) =>
        `<div class="bar" style="height:${Math.max(4, Math.round((r.ball_75 / 75) * 100))}%"><span>${r.ball_75}</span></div>`).join("")}</div></div>` : "";
      render(`<div class="hero"><div class="prof-head"><div class="avatar">${esc((d.user.full_name || "?").charAt(0).toUpperCase())}</div>
        <div><h1>${esc(d.user.full_name)}</h1><div class="sub">${d.user.username ? "@" + esc(d.user.username) : ""}${d.user.public_id ? " · 🎫 ID " + d.user.public_id : ""}</div></div></div></div>
        <div class="stats"><div class="stat"><div class="num">${d.results.length}</div><div class="label">Testlar</div></div>
        <div class="stat"><div class="num">${best || "-"}</div><div class="label">Eng yaxshi ball</div></div>
        <div class="stat"><div class="num">${d.results.length ? (d.results.reduce((s, r) => s + r.ball_75, 0) / d.results.length).toFixed(1) : "-"}</div><div class="label">O'rtacha</div></div></div>
        ${bars}
        <div class="section-title">Mening natijalarim (📄 — sertifikat PDF)</div>
        <div class="sheet">${list || `<div class="empty">Hali natijalar yo'q.</div>`}</div>${BRAND}`);
      app.querySelectorAll("[data-cert]").forEach((b) => b.addEventListener("click", () => sendCertificate(b.dataset.cert, b)));
    } catch (e) { showError(e.message); }
  }

  async function sendCertificate(attemptId, btn) {
    if (btn) btn.disabled = true;
    try {
      await apiPost("/api/certificate", { attempt_id: Number(attemptId) });
      buzz("success");
      toastOk("📄 Sertifikat botga yuborildi");
    } catch (e) { toast(e.message); }
    finally { if (btn) setTimeout(() => { btn.disabled = false; }, 15000); }
  }

  /* ------------------------------ boshlash ------------------------------ */
  const testId = new URLSearchParams(window.location.search).get("test_id");
  if (testId) startExam(testId); else setTab("home");
})();
