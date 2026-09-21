import math
import re

_CLOSED_RE = re.compile(r"^(\d+)-([A-Da-d])$")
_OPEN_RE = re.compile(r"^(\d+):(.+)$")

# 🆕 Ochiq savol javobi endi oddiy son/kasrdan tashqari ildiz (√, sqrt, cbrt,
# root3/4/5), pi/π va +-*/^ amallarini o'z ichiga olgan ifoda ham bo'lishi
# mumkin (masalan "√2", "sqrt(2)", "2*pi", "5^(1/3)"). O'quvchi buni qanday
# formatda yozishidan qat'i nazar (agar matematik jihatdan to'g'ri bo'lsa),
# _eval_expr son qiymatga aylantirib solishtiradi -- bu "universal yechim".


def parse_answer_key(raw_text: str) -> dict[int, str]:
    """Kalit matnini parse qiladi.

    Format: "1-A 2-C ... 35-D 36:12 37:-4.5 38:0.5|1/2 ... 45:7"
    Yopiq savol: "N-X" (X — A/B/C/D)
    Ochiq savol: "N:qiymat" (qiymatda vergul avtomatik nuqtaga aylanadi,
    bir nechta to'g'ri variant "|" bilan ajratiladi)
    """
    result: dict[int, str] = {}
    for token in raw_text.split():
        closed_match = _CLOSED_RE.match(token)
        if closed_match:
            order_num = int(closed_match.group(1))
            result[order_num] = closed_match.group(2).upper()
            continue

        open_match = _OPEN_RE.match(token)
        if open_match:
            order_num = int(open_match.group(1))
            value = "|".join(part.strip().replace(",", ".") for part in open_match.group(2).split("|"))
            result[order_num] = value

    return result


def qtype_for_answer(answer: str) -> str:
    return "yopiq" if re.fullmatch(r"[A-D]", answer) else "ochiq"


def normalize_open_answer(user_answer: str) -> str:
    return user_answer.strip().replace(",", ".")


# ---------------- Matematik ifodani baholash (qo'lda yozilgan xavfsiz parser) ----------------
# Frontend (webapp/student/math.js: evalMath) bilan BIR XIL grammatika:
#   ifoda   := had { (+|-) had }
#   had     := unar { (*|/) unar | oshkormas-ko'paytirish unar }
#   unar    := (+|-) unar | daraja
#   daraja  := postfiks [ ^ unar ]                      (o'ngdan chapga)
#   postfiks:= birlamchi { ! | % | ° }
#   birlamchi := son | konstanta(pi, e) | funksiya(arg;arg) | ( ifoda ) | √operand | ∛operand | ∜operand
# Oshkormas ko'paytirish faqat "son yoki )" dan keyin nom/(/√ kelganda ("2pi", "3√5", "2(3+4)").
# eval()/ast ISHLATILMAYDI -- faqat shu ruxsat etilgan amallar/funksiyalar.

_MAX_EXPR_LEN = 200


def _nth_root(value: float, n: float) -> float:
    if n == 0:
        raise ValueError("0-darajali ildiz")
    if value < 0:
        if float(n).is_integer() and int(n) % 2 != 0:
            return -((-value) ** (1 / n))
        raise ValueError("manfiy sondan juft ildiz olib bo'lmaydi")
    return value ** (1 / n)


def _cot(x: float) -> float:
    return 1 / math.tan(x)


def _deg(fn):
    return lambda x: fn(math.radians(x))


def _arcdeg(fn):
    return lambda x: math.degrees(fn(x))


def _factorial(x: float) -> float:
    if x < 0 or not float(x).is_integer() or x > 170:
        raise ValueError("faktorial faqat 0..170 butun son uchun")
    return float(math.factorial(int(x)))


_CONSTANTS = {"pi": math.pi, "e": math.e}

# nom -> (funksiya, argumentlar soni)
_FUNCTIONS: dict[str, tuple] = {
    "sqrt": (math.sqrt, 1), "cbrt": (lambda x: _nth_root(x, 3), 1),
    "root3": (lambda x: _nth_root(x, 3), 1), "root4": (lambda x: _nth_root(x, 4), 1),
    "root5": (lambda x: _nth_root(x, 5), 1), "root": (_nth_root, 2),
    "sin": (math.sin, 1), "cos": (math.cos, 1), "tan": (math.tan, 1), "tg": (math.tan, 1),
    "cot": (_cot, 1), "ctg": (_cot, 1),
    "sind": (_deg(math.sin), 1), "cosd": (_deg(math.cos), 1), "tand": (_deg(math.tan), 1),
    "tgd": (_deg(math.tan), 1), "cotd": (_deg(_cot), 1), "ctgd": (_deg(_cot), 1),
    "asin": (math.asin, 1), "acos": (math.acos, 1), "atan": (math.atan, 1),
    "arcsin": (math.asin, 1), "arccos": (math.acos, 1), "arctan": (math.atan, 1), "arctg": (math.atan, 1),
    "asind": (_arcdeg(math.asin), 1), "acosd": (_arcdeg(math.acos), 1), "atand": (_arcdeg(math.atan), 1),
    "sinh": (math.sinh, 1), "cosh": (math.cosh, 1), "tanh": (math.tanh, 1),
    "sh": (math.sinh, 1), "ch": (math.cosh, 1), "th": (math.tanh, 1),
    "asinh": (math.asinh, 1), "acosh": (math.acosh, 1), "atanh": (math.atanh, 1),
    "ln": (math.log, 1), "lg": (math.log10, 1), "log10": (math.log10, 1), "log2": (math.log2, 1),
    "exp": (math.exp, 1), "abs": (abs, 1),
}
_PREFIX_ROOTS = {"√": "sqrt", "∛": "cbrt", "∜": "root4"}


class _ParseError(Exception):
    pass


_NUM_RE = re.compile(r"\d+(?:\.\d+)?(?:E[+-]?\d+)?|\.\d+")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _tokenize(text: str) -> list[tuple[str, object]]:
    s = text.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("π", "pi").replace("²", "^2").replace("³", "^3")
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)  # o'nlik vergul
    tokens: list[tuple[str, object]] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        m = _NUM_RE.match(s, i)
        if m:
            tokens.append(("num", float(m.group(0))))
            i = m.end()
            continue
        if c in _PREFIX_ROOTS:
            tokens.append(("root", _PREFIX_ROOTS[c]))
            i += 1
            continue
        m = _NAME_RE.match(s, i)
        if m:
            tokens.append(("name", m.group(0).lower()))
            i = m.end()
            continue
        if c in "+-*/^!%°();,":
            tokens.append(("op", ";" if c == "," else c))
            i += 1
            continue
        raise _ParseError(f"noma'lum belgi: {c}")
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("end", None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def is_op(self, ch):
        return self.peek() == ("op", ch)

    def parse(self) -> float:
        v = self.expr()
        if self.peek()[0] != "end":
            raise _ParseError("ortiqcha belgilar")
        return v

    def expr(self) -> float:
        v = self.term()
        while self.is_op("+") or self.is_op("-"):
            op = self.take()[1]
            r = self.term()
            v = v + r if op == "+" else v - r
        return v

    def _starts_atom(self, tok) -> bool:
        return tok[0] in ("name", "root") or tok == ("op", "(")

    def term(self) -> float:
        v = self.unary()
        while True:
            prev = self.t[self.i - 1] if self.i > 0 else ("end", None)
            if self.is_op("*"):
                self.take()
                v = v * self.unary()
            elif self.is_op("/"):
                self.take()
                d = self.unary()
                if d == 0:
                    raise ZeroDivisionError
                v = v / d
            elif (prev[0] == "num" or prev == ("op", ")")) and self._starts_atom(self.peek()):
                v = v * self.unary()
            else:
                return v

    def unary(self) -> float:
        if self.is_op("-"):
            self.take()
            return -self.unary()
        if self.is_op("+"):
            self.take()
            return self.unary()
        return self.power()

    def power(self) -> float:
        base = self.postfix()
        if self.is_op("^"):
            self.take()
            return base ** self.unary()
        return base

    def postfix(self) -> float:
        v = self.primary()
        while True:
            if self.is_op("!"):
                self.take(); v = _factorial(v)
            elif self.is_op("%"):
                self.take(); v = v / 100
            elif self.is_op("°"):
                self.take(); v = v * math.pi / 180
            else:
                return v

    def operand(self) -> float:
        """√ / ∛ / ∜ dan keyingi bevosita operand: son, konstanta, (ifoda) yoki ichma-ich ildiz belgisi."""
        tok = self.peek()
        if tok[0] == "num":
            self.take(); return tok[1]
        if tok[0] == "name" and tok[1] in _CONSTANTS:
            self.take(); return _CONSTANTS[tok[1]]
        if tok == ("op", "("):
            self.take(); v = self.expr(); self._close(); return v
        if tok[0] == "root":
            self.take(); return _FUNCTIONS[tok[1]][0](self.operand())
        raise _ParseError("ildiz operandi yo'q")

    def _close(self):
        if self.take() != ("op", ")"):
            raise _ParseError("qavs yopilmagan")

    def primary(self) -> float:
        tok = self.take()
        kind, val = tok
        if kind == "num":
            return val
        if kind == "root":
            if self.is_op("("):
                self.take(); v = self.expr(); self._close()
                return _FUNCTIONS[val][0](v)
            return _FUNCTIONS[val][0](self.operand())
        if kind == "name":
            if val in _CONSTANTS and not self.is_op("("):
                return _CONSTANTS[val]
            if val in _FUNCTIONS and self.is_op("("):
                fn, arity = _FUNCTIONS[val]
                self.take()
                args = [self.expr()]
                while self.is_op(";"):
                    self.take(); args.append(self.expr())
                self._close()
                if len(args) != arity:
                    raise _ParseError("argumentlar soni noto'g'ri")
                return fn(*args)
            raise _ParseError(f"noma'lum nom: {val}")
        if tok == ("op", "("):
            v = self.expr(); self._close(); return v
        raise _ParseError("kutilmagan belgi")


def _eval_expr(text: str) -> float | None:
    if not text or len(text) > _MAX_EXPR_LEN:
        return None
    try:
        value = _Parser(_tokenize(text)).parse()
    except (_ParseError, ValueError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
        return None
    if not isinstance(value, float) and not isinstance(value, int):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def is_valid_numeric_answer(user_answer: str) -> bool:
    """O'quvchi javobi matematik ifoda sifatida hisoblanadigan formatda
    ekanini tekshiradi: oddiy son (12, -3,5, 1/2) yoki ildiz/pi ifodasi
    (√2, sqrt(2), 2*pi, 5^(1/3) va h.k.). Bir nechta variant "|" bilan
    ajratilgan bo'lsa (admin kalit kiritganda), har biri tekshiriladi.
    So'z bilan yozilgan javoblar ("o'n ikki") har doim False qaytaradi."""
    parts = user_answer.strip().split("|")
    if not parts or any(not p.strip() for p in parts):
        return False
    return all(_eval_expr(p) is not None for p in parts)


def _values_match(a: float, b: float) -> bool:
    return round(a, 4) == round(b, 4)


def is_open_answer_correct(user_answer: str, correct_answer: str) -> bool:
    normalized = normalize_open_answer(user_answer)
    accepted_variants = correct_answer.split("|")

    # Avval aniq (matn) moslikni tekshiramiz -- eng ishonchli va tez yo'l,
    # mavjud (oddiy sonli) ma'lumotlar bilan ham to'liq mos.
    if normalized in accepted_variants:
        return True

    # Ildiz/pi kabi turlicha yozilishi mumkin bo'lgan ifodalar uchun --
    # ikkala tomonni ham son qiymatga aylantirib solishtiramiz.
    user_value = _eval_expr(normalized)
    if user_value is None:
        return False

    for variant in accepted_variants:
        variant_value = _eval_expr(variant)
        if variant_value is not None and _values_match(user_value, variant_value):
            return True
    return False
