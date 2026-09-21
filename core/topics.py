"""🆕 Savol bo'limlari (algebra/geometriya) -- sertifikatdagi bo'limlar bo'yicha ball uchun."""

import re

ALGEBRA = "algebra"
GEOMETRY = "geometriya"
TOPIC_LABELS = {ALGEBRA: "Algebra", GEOMETRY: "Geometriya"}
TOPIC_ORDER = (ALGEBRA, GEOMETRY)


def parse_order_ranges(text: str, max_n: int) -> set[int] | None:
    """"25-30, 33-35 41" -> {25..30, 33..35, 41}. Noto'g'ri format yoki
    1..max_n dan tashqari raqam bo'lsa None."""
    tokens = [t for t in re.split(r"[,;\s]+", text.strip()) if t]
    if not tokens:
        return None
    result: set[int] = set()
    for token in tokens:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", token)
        if not m:
            return None
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if a < 1 or b < a or b > max_n:
            return None
        result.update(range(a, b + 1))
    return result
