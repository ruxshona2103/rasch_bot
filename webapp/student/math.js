/* Matematik ifodalar uchun ikkita vosita (server core/answer_key.py bilan BIR XIL grammatika):
   1) evalMath(str)   -> son yoki null (klaviaturadagi "=" va xotira tugmalari uchun)
   2) mathToHtml(str) -> chiroyli ko'rinish (kasr, ildiz, daraja...). Yarim yozilgan ifoda ham xatosiz. */
(function (root) {
  "use strict";

  /* ------------------------------ umumiy jadvallar ------------------------------ */
  const nthRoot = (v, n) => {
    if (n === 0) throw new Error("root0");
    if (v < 0) {
      if (Number.isInteger(n) && Math.abs(n) % 2 === 1) return -Math.pow(-v, 1 / n);
      throw new Error("even root of negative");
    }
    return Math.pow(v, 1 / n);
  };
  const rad = (x) => (x * Math.PI) / 180;
  const deg = (x) => (x * 180) / Math.PI;
  const cot = (x) => 1 / Math.tan(x);
  const dom = (fn, ok) => (x) => { if (!ok(x)) throw new Error("domain"); return fn(x); };
  const fact = (x) => {
    if (x < 0 || !Number.isInteger(x) || x > 170) throw new Error("factorial");
    let r = 1; for (let i = 2; i <= x; i++) r *= i; return r;
  };
  const asin = dom(Math.asin, (x) => x >= -1 && x <= 1);
  const acos = dom(Math.acos, (x) => x >= -1 && x <= 1);
  const acosh = dom(Math.acosh, (x) => x >= 1);
  const atanh = dom(Math.atanh, (x) => x > -1 && x < 1);
  const lnf = dom(Math.log, (x) => x > 0);
  const lg = dom(Math.log10, (x) => x > 0);
  const lg2 = dom(Math.log2, (x) => x > 0);
  const sqrtf = dom(Math.sqrt, (x) => x >= 0);

  const FUNCS = {
    sqrt: [sqrtf, 1], cbrt: [(x) => nthRoot(x, 3), 1], root3: [(x) => nthRoot(x, 3), 1],
    root4: [(x) => nthRoot(x, 4), 1], root5: [(x) => nthRoot(x, 5), 1], root: [nthRoot, 2],
    sin: [Math.sin, 1], cos: [Math.cos, 1], tan: [Math.tan, 1], tg: [Math.tan, 1], cot: [cot, 1], ctg: [cot, 1],
    sind: [(x) => Math.sin(rad(x)), 1], cosd: [(x) => Math.cos(rad(x)), 1], tand: [(x) => Math.tan(rad(x)), 1],
    tgd: [(x) => Math.tan(rad(x)), 1], cotd: [(x) => cot(rad(x)), 1], ctgd: [(x) => cot(rad(x)), 1],
    asin: [asin, 1], acos: [acos, 1], atan: [Math.atan, 1], arcsin: [asin, 1], arccos: [acos, 1],
    arctan: [Math.atan, 1], arctg: [Math.atan, 1],
    asind: [(x) => deg(asin(x)), 1], acosd: [(x) => deg(acos(x)), 1], atand: [(x) => deg(Math.atan(x)), 1],
    sinh: [Math.sinh, 1], cosh: [Math.cosh, 1], tanh: [Math.tanh, 1], sh: [Math.sinh, 1], ch: [Math.cosh, 1], th: [Math.tanh, 1],
    asinh: [Math.asinh, 1], acosh: [acosh, 1], atanh: [atanh, 1],
    ln: [lnf, 1], lg: [lg, 1], log10: [lg, 1], log2: [lg2, 1], exp: [Math.exp, 1], abs: [Math.abs, 1],
  };
  const CONSTS = { pi: Math.PI, e: Math.E };
  const PREFIX_ROOTS = { "√": "sqrt", "∛": "cbrt", "∜": "root4" };

  /* ------------------------------ 1) hisoblagich ------------------------------ */
  function tokenize(text) {
    let s = String(text)
      .replace(/×/g, "*").replace(/÷/g, "/").replace(/[−–—]/g, "-")
      .replace(/π/g, "pi").replace(/²/g, "^2").replace(/³/g, "^3")
      .replace(/(\d),(?=\d)/g, "$1.");
    const toks = [];
    let i = 0;
    while (i < s.length) {
      const c = s[i];
      if (/\s/.test(c)) { i++; continue; }
      let m = /^(\d+(?:\.\d+)?(?:E[+-]?\d+)?|\.\d+)/.exec(s.slice(i));
      if (m) { toks.push(["num", parseFloat(m[1])]); i += m[1].length; continue; }
      if (PREFIX_ROOTS[c]) { toks.push(["root", PREFIX_ROOTS[c]]); i++; continue; }
      m = /^[A-Za-z_][A-Za-z_0-9]*/.exec(s.slice(i));
      if (m) { toks.push(["name", m[0].toLowerCase()]); i += m[0].length; continue; }
      if ("+-*/^!%°();,".includes(c)) { toks.push(["op", c === "," ? ";" : c]); i++; continue; }
      throw new Error("bad char");
    }
    return toks;
  }

  function evalMath(text) {
    if (!text || String(text).length > 200) return null;
    try {
      const t = tokenize(text);
      let i = 0;
      const peek = () => (i < t.length ? t[i] : ["end", null]);
      const take = () => t[i++] || ["end", null];
      const isOp = (ch) => { const p = peek(); return p[0] === "op" && p[1] === ch; };
      const close = () => { const p = take(); if (!(p[0] === "op" && p[1] === ")")) throw new Error("close"); };
      const startsAtom = (p) => p[0] === "name" || p[0] === "root" || (p[0] === "op" && p[1] === "(");

      function expr() {
        let v = term();
        while (isOp("+") || isOp("-")) { const op = take()[1]; const r = term(); v = op === "+" ? v + r : v - r; }
        return v;
      }
      function term() {
        let v = unary();
        for (;;) {
          const prev = i > 0 ? t[i - 1] : ["end", null];
          if (isOp("*")) { take(); v = v * unary(); }
          else if (isOp("/")) { take(); const d = unary(); if (d === 0) throw new Error("div0"); v = v / d; }
          else if ((prev[0] === "num" || (prev[0] === "op" && prev[1] === ")")) && startsAtom(peek())) { v = v * unary(); }
          else return v;
        }
      }
      function unary() {
        if (isOp("-")) { take(); return -unary(); }
        if (isOp("+")) { take(); return unary(); }
        return power();
      }
      function power() {
        const b = postfix();
        if (isOp("^")) { take(); return Math.pow(b, unary()); }
        return b;
      }
      function postfix() {
        let v = primary();
        for (;;) {
          if (isOp("!")) { take(); v = fact(v); }
          else if (isOp("%")) { take(); v = v / 100; }
          else if (isOp("°")) { take(); v = (v * Math.PI) / 180; }
          else return v;
        }
      }
      function operand() {
        const p = peek();
        if (p[0] === "num") { take(); return p[1]; }
        if (p[0] === "name" && CONSTS[p[1]] !== undefined) { take(); return CONSTS[p[1]]; }
        if (p[0] === "op" && p[1] === "(") { take(); const v = expr(); close(); return v; }
        if (p[0] === "root") { take(); return FUNCS[p[1]][0](operand()); }
        throw new Error("operand");
      }
      function primary() {
        const tok = take();
        const [kind, val] = tok;
        if (kind === "num") return val;
        if (kind === "root") {
          if (isOp("(")) { take(); const v = expr(); close(); return FUNCS[val][0](v); }
          return FUNCS[val][0](operand());
        }
        if (kind === "name") {
          if (CONSTS[val] !== undefined && !isOp("(")) return CONSTS[val];
          if (FUNCS[val] && isOp("(")) {
            take();
            const args = [expr()];
            while (isOp(";")) { take(); args.push(expr()); }
            close();
            if (args.length !== FUNCS[val][1]) throw new Error("arity");
            return FUNCS[val][0](...args);
          }
          throw new Error("name");
        }
        if (kind === "op" && val === "(") { const v = expr(); close(); return v; }
        throw new Error("unexpected");
      }

      const v = expr();
      if (peek()[0] !== "end") return null;
      return Number.isFinite(v) ? v : null;
    } catch (e) {
      return null;
    }
  }

  /* ------------------------------ 2) chiroyli ko'rinish ------------------------------ */
  function esc(c) {
    return String(c).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }

  const FN_LABEL = {
    tg: "tg", tan: "tan", ctg: "ctg", cot: "cot", sind: "sin°", cosd: "cos°", tand: "tg°", tgd: "tg°", cotd: "ctg°", ctgd: "ctg°",
    asin: "sin⁻¹", acos: "cos⁻¹", atan: "tg⁻¹", arcsin: "sin⁻¹", arccos: "cos⁻¹", arctan: "tg⁻¹", arctg: "tg⁻¹",
    asind: "sin⁻¹°", acosd: "cos⁻¹°", atand: "tg⁻¹°", asinh: "sh⁻¹", acosh: "ch⁻¹", atanh: "th⁻¹",
    log10: "log₁₀", log2: "log₂",
  };
  const ROOT_SYMBOLS = [["∛", 3], ["∜", 4], ["√", 2]];
  const ROOT_NAMES = { sqrt: 2, cbrt: 3, root3: 3, root4: 4, root5: 5 };

  function mathToHtml(src) {
    const s = String(src || "")
      .replace(/\s+/g, "").replace(/²/g, "^2").replace(/³/g, "^3");
    let i = 0;

    const frac = (n, d) => `<span class="frac"><span class="num">${n || "&nbsp;"}</span><span class="den">${d || "&nbsp;"}</span></span>`;
    const radical = (idx, inner) =>
      `<span class="rad">${idx !== 2 ? `<sup class="ri">${idx}</sup>` : ""}<span class="rs">√</span><span class="rc">${inner || "&nbsp;"}</span></span>`;
    const unwrap = (part) => (part && part.group !== null ? part.group : part ? part.html : "");

    function parseSum(inParen) {
      let out = "";
      while (i < s.length) {
        const c = s[i];
        if (c === ")") { if (inParen) break; out += ")"; i++; continue; }
        if (c === ";" && inParen) break;
        if (c === "+" || c === "-") { out += `<span class="op">${c === "-" ? "−" : "+"}</span>`; i++; continue; }
        out += parseTerm();
      }
      return out;
    }

    function parseTerm() {
      const parts = [];
      while (i < s.length) {
        const c = s[i];
        if (c === "+" || c === "-" || c === ")" || c === ";") break;
        if (c === "*") { parts.push({ html: '<span class="op">·</span>', group: null }); i++; continue; }
        if (c === "/") {
          i++;
          const den = parseFactor();
          const numHtml = parts.length === 1 ? unwrap(parts[0]) : parts.map((p) => p.html).join("");
          parts.length = 0;
          parts.push({ html: frac(numHtml, unwrap(den)), group: null });
          continue;
        }
        parts.push(parseFactor());
      }
      return parts.map((p) => p.html).join("");
    }

    function parseFactor() {
      let r = parseAtom();
      for (;;) {
        if (s[i] === "!" || s[i] === "%" || s[i] === "°") { r = { html: r.html + esc(s[i]), group: null }; i++; continue; }
        break;
      }
      while (s[i] === "^") {
        i++;
        let sign = "";
        if (s[i] === "-") { sign = "−"; i++; }
        const e = parseAtom();
        r = { html: r.html + `<sup>${sign}${unwrap(e)}</sup>`, group: null };
      }
      return r;
    }

    function parseArgs() {
      const args = [parseSum(true)];
      while (s[i] === ";") { i++; args.push(parseSum(true)); }
      if (s[i] === ")") i++;
      return args;
    }

    function parseAtom() {
      if (i >= s.length) return { html: "", group: null };
      const rest = s.slice(i);

      const num = rest.match(/^\d+([.,]\d*)?(E[+-]?\d+)?/);
      if (num) {
        i += num[0].length;
        const [mant, ex] = num[0].split("E");
        return { html: esc(mant) + (ex ? `<span class="op">×</span>10<sup>${esc(ex)}</sup>` : ""), group: null };
      }

      if (s[i] === "(") {
        i++;
        const inner = parseSum(true);
        if (s[i] === ")") i++;
        return { html: `(${inner})`, group: inner };
      }

      for (const [sym, idx] of ROOT_SYMBOLS) {
        if (s.startsWith(sym, i)) {
          i += sym.length;
          let inner;
          if (s[i] === "(") { i++; inner = parseSum(true); if (s[i] === ")") i++; }
          else inner = unwrap(parseAtom());
          return { html: radical(idx, inner), group: null };
        }
      }

      const id = rest.match(/^[A-Za-z]+\d*/);
      if (id) {
        const name = id[0].toLowerCase();
        const next = s[i + id[0].length];
        if (name in ROOT_NAMES && next === "(") {
          i += id[0].length + 1;
          const a = parseArgs();
          return { html: radical(ROOT_NAMES[name], a[0]), group: null };
        }
        if (name === "root" && next === "(") {
          i += id[0].length + 1;
          const a = parseArgs();
          return { html: radical(a[1] !== undefined ? a[1] : 2, a[0]), group: null };
        }
        if (name === "abs" && next === "(") {
          i += id[0].length + 1;
          const a = parseArgs();
          return { html: `|${a[0]}|`, group: null };
        }
        if (FUNCS[name] && next === "(") {
          i += id[0].length + 1;
          const a = parseArgs();
          return { html: `<span class="fn">${esc(FN_LABEL[name] || name)}</span>(${a.join("; ")})`, group: null };
        }
        if (name.startsWith("pi")) { i += 2; return { html: "π", group: null }; }
        if (name === "e" || name.startsWith("e")) { i += 1; return { html: "<i>e</i>", group: null }; }
      }

      const ch = s[i++];
      return { html: esc(ch), group: null };
    }

    return parseSum(false);
  }

  root.mathToHtml = mathToHtml;
  root.evalMath = evalMath;
  if (typeof module !== "undefined" && module.exports) module.exports = { mathToHtml, evalMath };
})(typeof window !== "undefined" ? window : globalThis);
