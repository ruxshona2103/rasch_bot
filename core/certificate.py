"""🆕 Natija sertifikati (PDF): ball, daraja, o'rin, bo'limlar bo'yicha ball,
matematikaga oid iqtibos va shior. PyMuPDF (fitz) bilan chiziladi -- yangi
bog'liqlik yo'q; shriftlar assets/fonts'da (kirill va lotin ismlar uchun)."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import fitz

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_REG = FONT_DIR / "DejaVuSans.ttf"
_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
_OBL = FONT_DIR / "LiberationSans-Italic.ttf"

NAVY = (0.043, 0.165, 0.314)
GOLD = (0.83, 0.65, 0.16)
GOLD_DARK = (0.62, 0.45, 0.06)
CREAM = (1.0, 0.992, 0.965)
GRAY = (0.32, 0.36, 0.43)
WHITE = (1, 1, 1)
GRADE_COLORS = {
    "A+": (0.07, 0.5, 0.23), "A": (0.07, 0.5, 0.23),
    "B+": (0.11, 0.31, 0.85), "B": (0.11, 0.31, 0.85),
    "C+": (0.71, 0.33, 0.04), "C": (0.71, 0.33, 0.04),
    "NC": (0.85, 0.14, 0.11),
}

# (iqtibos, muallif) -- manbalar bo'yicha tasdiqlangan mashhur iqtiboslar
QUOTES = [
    ("Sof matematika o'ziga xos tarzda mantiqiy g'oyalarning she'riyatidir.", "Albert Eynshteyn"),
    ("Matematikani o'rganishning yagona yo'li — matematika bilan shug'ullanishdir.", "Pol Halmosh"),
    ("Matematika — aql musiqasidir.", "Jeyms Silvestr"),
    ("Matematikaning mohiyati uning erkinligidadir.", "Georg Kantor"),
    ("Matematika — fanlar malikasi.", "Karl Fridrix Gauss"),
    ("Biz bilishimiz kerak — biz bilib olamiz.", "Devid Hilbert"),
    ("Matematika raqamlar, tenglamalar yoki algoritmlar haqida emas: u tushunish haqida.", "Uilyam Terston"),
]

LEVEL_MESSAGES = {
    "top": "Ajoyib natija! Siz yuqori cho'qqiga juda yaqinsiz.",
    "good": "Yaxshi natija! Yana bir qadam — va eng yuqori daraja.",
    "mid": "Yaxshi boshlanish! Muntazam mashq natijani oshiradi.",
    "low": "Xatolar — o'sish zinapoyasi. Keyingi mockda o'sasiz!",
}


@dataclass
class CertificateData:
    full_name: str
    username: str | None
    test_title: str
    ball: float
    grade: str | None
    date: datetime
    seed: int = 0
    rank: int | None = None
    participants: int | None = None
    sections: list[tuple[str, float]] = field(default_factory=list)


def level_key(grade: str | None) -> str:
    if grade in ("A+", "A"):
        return "top"
    if grade in ("B+", "B"):
        return "good"
    if grade in ("C+", "C"):
        return "mid"
    return "low"


def split_section_scores(ball: float, correct_by_topic: dict[str, int]) -> list[tuple[str, float]]:
    """Umumiy ballni bo'limlarga to'g'ri javoblar ulushiga qarab bo'ladi
    (yig'indi aynan umumiy ballga teng bo'ladi)."""
    if not correct_by_topic:
        return []
    total = sum(correct_by_topic.values())
    if total == 0:
        return [(name, 0.0) for name in correct_by_topic]
    parts = {name: round(ball * n / total, 2) for name, n in correct_by_topic.items()}
    diff = round(ball - sum(parts.values()), 2)
    if diff:
        biggest = max(parts, key=parts.get)
        parts[biggest] = round(parts[biggest] + diff, 2)
    return list(parts.items())


def render_certificate(data: CertificateData) -> bytes:
    f_reg = fitz.Font(fontfile=str(_REG))
    f_bold = fitz.Font(fontfile=str(_BOLD))
    f_obl = fitz.Font(fontfile=str(_OBL))
    fonts = {"dj": f_reg, "djb": f_bold, "dji": f_obl}

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="dj", fontfile=str(_REG))
    page.insert_font(fontname="djb", fontfile=str(_BOLD))
    page.insert_font(fontname="dji", fontfile=str(_OBL))
    W, H = page.rect.width, page.rect.height

    def text(x, y, s, size, font="dj", color=NAVY):
        page.insert_text((x, y), s, fontname=font, fontsize=size, color=color)

    def tlen(s, size, font="dj"):
        return fonts[font].text_length(s, fontsize=size)

    def ctext(cx, y, s, size, font="dj", color=NAVY):
        text(cx - tlen(s, size, font) / 2, y, s, size, font, color)

    def wrap(s, size, font, max_w):
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}".strip()
            if tlen(trial, size, font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def rect(r, fill=None, color=None, width=1.0, radius=None):
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(*r), radius=radius)
        sh.finish(fill=fill, color=color, width=width)
        sh.commit()

    def line(p1, p2, color=GOLD, width=1.0):
        sh = page.new_shape()
        sh.draw_line(p1, p2)
        sh.finish(color=color, width=width)
        sh.commit()

    def diamond(cx, cy, r, color=GOLD):
        sh = page.new_shape()
        sh.draw_polyline([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)])
        sh.finish(fill=color, color=color, width=0.5)
        sh.commit()

    def divider(y, half=170):
        line((W / 2 - half, y), (W / 2 - 8, y))
        line((W / 2 + 8, y), (W / 2 + half, y))
        diamond(W / 2, y, 4)

    # ---------------- fon va ramkalar ----------------
    rect((0, 0, W, H), fill=CREAM)
    rect((12, 12, W - 12, H - 12), color=GOLD, width=2.4)
    rect((22, 22, W - 22, H - 22), color=NAVY, width=2.2)
    rect((28, 28, W - 28, H - 28), color=GOLD, width=0.8)
    for sx, sy in ((28, 28), (W - 28, 28), (28, H - 28), (W - 28, H - 28)):
        dx = 1 if sx < W / 2 else -1
        dy = 1 if sy < H / 2 else -1
        for k in range(1, 7):
            d = k * 16
            line((sx + dx * d, sy), (sx, sy + dy * d), GOLD, 0.7)

    cx = W / 2

    # ---------------- sarlavha ----------------
    ctext(cx, 112, "O'tkazilgan online mock testimizda", 12.5, "dj", NAVY)
    ctext(cx, 132, "ONLINE Mock test natijasiga asoslanib", 12.5, "djb", NAVY)
    divider(152, 118)
    ctext(cx, 196, "MOCK NATIJASIGA KO'RA", 25, "djb", NAVY)
    ctext(cx, 226, "SIZNING BILIM DARAJANGIZ", 25, "djb", NAVY)
    divider(252, 90)

    # ---------------- test nomi banneri ----------------
    rect((75, 274, 520, 314), fill=NAVY, color=GOLD, width=1.4, radius=0.18)
    text(92, 299, "SERTIFIKAT MOCK TESTI:", 10.5, "djb", GOLD)
    title = data.test_title
    size = 11.5
    while tlen(title, size, "djb") > 215 and size > 7:
        size -= 0.5
    text(520 - 14 - tlen(title, size, "djb"), 299, title, size, "djb", WHITE)

    # ---------------- shaxs ma'lumotlari ----------------
    rows = [("F.I.Sh.", data.full_name), ("Nick name", f"@{data.username}" if data.username else "-")]
    if data.rank and data.participants:
        rows.append(("O'rin", f"{data.rank} / {data.participants}"))
    y = 350
    for label, value in rows:
        text(105, y, label, 12, "dj", NAVY)
        text(232, y, ":", 12, "djb", NAVY)
        vsize = 13
        while tlen(value, vsize, "djb") > 240 and vsize > 8:
            vsize -= 0.5
        text(250, y, value, vsize, "djb", NAVY)
        y += 27

    # ---------------- ball va daraja ----------------
    grade = data.grade or "NC"
    gcolor = GRADE_COLORS.get(grade, GRADE_COLORS["NC"])
    top = 430
    for x0, title_txt, big, bigcolor in ((84, "UMUMIY BALL", f"{data.ball:.2f}", NAVY), (350, "DARAJA", grade, gcolor)):
        rect((x0, top, x0 + 161, top + 124), color=GOLD, width=1.2, radius=0.06)
        ctext(x0 + 80.5, top + 30, title_txt, 12.5, "djb", NAVY)
        line((x0 + 32, top + 39), (x0 + 129, top + 39), GOLD, 0.7)
        ctext(x0 + 80.5, top + 92, big, 44 if len(big) <= 5 else 34, "djb", bigcolor)

    # medal
    mx, my = cx, top + 56
    page.draw_circle((mx, my), 27, color=GOLD, fill=None, width=6)
    page.draw_circle((mx, my), 19, color=GOLD_DARK, fill=None, width=1)
    for sign in (-1, 1):
        sh = page.new_shape()
        sh.draw_polyline([(mx + sign * 6, my + 27), (mx + sign * 24, my + 62), (mx + sign * 12, my + 55), (mx + sign * 2, my + 64), (mx + sign * 2, my + 29)])
        sh.finish(fill=GOLD, color=GOLD, width=0.6)
        sh.commit()

    # bo'limlar bo'yicha ball
    y = 584
    if data.sections:
        names = [name for name, _ in data.sections]
        vals = [f"{val:.2f}" for _, val in data.sections]
        widths = [tlen(n, 11, "djb") + 8 + tlen(v, 11, "dj") for n, v in zip(names, vals)]
        total_w = sum(widths) + 40 * (len(widths) - 1)
        x = cx - total_w / 2
        for n, v, w in zip(names, vals, widths):
            text(x, y, n, 11, "djb", NAVY)
            text(x + tlen(n, 11, "djb") + 8, y, v, 11, "dj", NAVY)
            x += w + 40
        y += 22
    else:
        y += 4

    # ---------------- motivatsiya va iqtibos ----------------
    divider(y + 6, 150)
    yy = y + 30
    for ln in wrap(LEVEL_MESSAGES[level_key(data.grade)], 11.5, "djb", 440):
        ctext(cx, yy, ln, 11.5, "djb", GOLD_DARK)
        yy += 16
    quote, author = QUOTES[data.seed % len(QUOTES)]
    yy += 4
    for ln in wrap(f"«{quote}»", 10.5, "dji", 400):
        ctext(cx, yy, ln, 10.5, "dji", NAVY)
        yy += 15
    ctext(cx, yy + 2, f"— {author}", 9.5, "dj", GRAY)
    divider(yy + 20, 150)

    # ---------------- sana va imzo ----------------
    text(105, 724, "Berilgan sanasi:", 10, "dj", NAVY)
    text(105, 741, data.date.strftime("%d.%m.%Y"), 12.5, "djb", NAVY)
    line((360, 739), (500, 739), GOLD, 1)
    ctext(430, 751, "Abdurashid Yusufov", 9.5, "djb", NAVY)
    ctext(430, 761, "o'qituvchi", 7.5, "dj", GRAY)

    # ---------------- pastki shior ----------------
    rect((75, 768, 520, 806), fill=NAVY, radius=0.2)
    ctext(cx, 785, "Abdurashid Yusufov bilan hammasi oson!", 12, "djb", GOLD)
    ctext(cx, 799, "Mazkur sertifikat Rasch baholash modeliga asosida avtomatik yaratilgan.", 6.8, "dj", WHITE)

    buf = io.BytesIO()
    try:
        doc.subset_fonts()  # shriftni faqat ishlatilgan belgilarga qisqartiradi (~1 MB -> ~50 KB)
    except Exception:
        pass
    doc.save(buf, garbage=3, deflate=True)
    doc.close()
    return buf.getvalue()


async def render_certificate_async(data: CertificateData) -> bytes:
    return await asyncio.get_running_loop().run_in_executor(None, render_certificate, data)
