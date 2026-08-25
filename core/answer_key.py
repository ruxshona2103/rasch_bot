import re

_CLOSED_RE = re.compile(r"^(\d+)-([A-Da-d])$")
_OPEN_RE = re.compile(r"^(\d+):(.+)$")


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


def is_open_answer_correct(user_answer: str, correct_answer: str) -> bool:
    normalized = normalize_open_answer(user_answer)
    accepted_variants = correct_answer.split("|")
    return normalized in accepted_variants
