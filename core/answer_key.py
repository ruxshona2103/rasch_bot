import re

_CLOSED_RE = re.compile(r"^(\d+)-([A-Da-d])$")
_OPEN_RE = re.compile(r"^(\d+):(.+)$")
# Ochiq savol javobi: butun/kasr son (vergul yoki nuqta bilan) yoki oddiy kasr (1/2).
# So'z bilan yozilgan javoblarni ("o'n ikki") rad etish uchun ishlatiladi.
_NUMERIC_ANSWER_RE = re.compile(r"^-?\d+([.,]\d+|/\d+)?$")


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


def is_valid_numeric_answer(user_answer: str) -> bool:
    """🆕 O'quvchi javobi raqam formatida ekanini tekshiradi (12, -3,5, 1/2 va h.k.).
    "o'n ikki" kabi so'z bilan yozilgan javoblar bu yerda False qaytaradi —
    ular hech qachon to'g'ri javob bilan mos kelmaydi, shuning uchun umuman
    qabul qilinmasdan, o'quvchiga darhol qayta yozish so'raladi."""
    return bool(_NUMERIC_ANSWER_RE.match(user_answer.strip()))


def is_open_answer_correct(user_answer: str, correct_answer: str) -> bool:
    normalized = normalize_open_answer(user_answer)
    accepted_variants = correct_answer.split("|")
    return normalized in accepted_variants
