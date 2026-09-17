import ast
import math
import operator
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


# ---------------- Matematik ifodani (ildiz, pi va h.k.) baholash ----------------

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def _nth_root(value: float, n: float) -> float:
    if value < 0:
        if n % 2 == 0:
            raise ValueError("manfiy sondan juft ildiz olib bo'lmaydi")
        return -((-value) ** (1 / n))
    return value ** (1 / n)


_FUNCTIONS = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: _nth_root(x, 3),
    "root3": lambda x: _nth_root(x, 3),
    "root4": lambda x: _nth_root(x, 4),
    "root5": lambda x: _nth_root(x, 5),
}


def _preprocess_math(text: str) -> str:
    s = text.strip()
    s = s.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("^", "**")
    s = s.replace("π", "pi")
    # o'nlik vergul -> nuqta (raqamlar orasida bo'lsagina)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    # √(...)/√raqam -> sqrt(...); ∛, ∜ xuddi shunday cbrt/root4'ga
    s = re.sub(r"√\(([^)]*)\)", r"sqrt(\1)", s)
    s = re.sub(r"√(-?\d+(?:\.\d+)?)", r"sqrt(\1)", s)
    s = re.sub(r"∛\(([^)]*)\)", r"cbrt(\1)", s)
    s = re.sub(r"∛(-?\d+(?:\.\d+)?)", r"cbrt(\1)", s)
    s = re.sub(r"∜\(([^)]*)\)", r"root4(\1)", s)
    s = re.sub(r"∜(-?\d+(?:\.\d+)?)", r"root4(\1)", s)
    # oshkormas ko'paytirish: "3sqrt(5)" -> "3*sqrt(5)", "2pi" -> "2*pi", "2(3+4)" -> "2*(3+4)"
    # (root3(/root4(/root5( funksiya nomlarining o'zidagi raqam bundan mustasno)
    s = re.sub(r"(?<!root3)(?<!root4)(?<!root5)(?<=[\d)])(?=[a-zA-Zπ(])", "*", s)
    return s


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise ValueError("nomos konstanta")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords:
            raise ValueError("nomos argument")
        args = [_eval_node(a) for a in node.args]
        return float(_FUNCTIONS[node.func.id](*args))
    raise ValueError("ruxsat etilmagan ifoda")


def _eval_expr(text: str) -> float | None:
    try:
        processed = _preprocess_math(text)
        if not processed:
            return None
        tree = ast.parse(processed, mode="eval")
        value = _eval_node(tree)
    except (ValueError, TypeError, ZeroDivisionError, SyntaxError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    return value


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
