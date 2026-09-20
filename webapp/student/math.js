/* Matn ko'rinishidagi ifodani (1/2, √(2), x^2 ...) chiroyli matematik HTML'ga aylantiradi.
   Yarim yozilgan ifodalar (masalan "1/" yoki "√(") ham xatosiz ishlaydi. */
(function (root) {
  "use strict";

  function esc(c) {
    return String(c).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }

  const ROOTS = [
    ["sqrt", 2], ["cbrt", 3], ["root3", 3], ["root4", 4], ["root5", 5],
    ["√", 2], ["∛", 3], ["∜", 4],
  ];

  function mathToHtml(src) {
    const s = String(src || "").replace(/\s+/g, "");
    let i = 0;

    const frac = (n, d) =>
      `<span class="frac"><span class="num">${n || "&nbsp;"}</span><span class="den">${d || "&nbsp;"}</span></span>`;
    const rad = (idx, inner) =>
      `<span class="rad">${idx !== 2 ? `<sup class="ri">${idx}</sup>` : ""}<span class="rs">√</span><span class="rc">${inner || "&nbsp;"}</span></span>`;
    const unwrap = (part) => (part && part.group !== null ? part.group : part ? part.html : "");

    function parseSum(inParen) {
      let out = "";
      while (i < s.length) {
        const c = s[i];
        if (c === ")") {
          if (inParen) break;
          out += ")"; i++; continue;
        }
        if (c === "+" || c === "-") {
          out += `<span class="op">${c === "-" ? "−" : "+"}</span>`; i++; continue;
        }
        out += parseTerm();
      }
      return out;
    }

    function parseTerm() {
      const parts = [];
      while (i < s.length) {
        const c = s[i];
        if (c === "+" || c === "-" || c === ")") break;
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
      while (s[i] === "^") {
        i++;
        let sign = "";
        if (s[i] === "-") { sign = "−"; i++; }
        const e = parseAtom();
        r = { html: r.html + `<sup>${sign}${unwrap(e)}</sup>`, group: null };
      }
      return r;
    }

    function parseAtom() {
      if (i >= s.length) return { html: "", group: null };
      const rest = s.slice(i);

      const num = rest.match(/^\d+([.,]\d*)?/);
      if (num) { i += num[0].length; return { html: esc(num[0]), group: null }; }

      if (s[i] === "(") {
        i++;
        const inner = parseSum(true);
        if (s[i] === ")") i++;
        return { html: `(${inner})`, group: inner };
      }

      for (const [name, idx] of ROOTS) {
        if (rest.startsWith(name)) {
          i += name.length;
          let inner;
          if (s[i] === "(") {
            i++;
            inner = parseSum(true);
            if (s[i] === ")") i++;
          } else {
            inner = unwrap(parseAtom());
          }
          return { html: rad(idx, inner), group: null };
        }
      }

      if (rest.startsWith("pi")) { i += 2; return { html: "π", group: null }; }
      const ch = s[i++];
      return { html: esc(ch), group: null };
    }

    return parseSum(false);
  }

  root.mathToHtml = mathToHtml;
  if (typeof module !== "undefined" && module.exports) module.exports = { mathToHtml };
})(typeof window !== "undefined" ? window : globalThis);
