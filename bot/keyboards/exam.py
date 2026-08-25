from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _nav_row(order_num: int, total: int) -> list[InlineKeyboardButton]:
    row = []
    if order_num > 1:
        row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data="examprev"))
    if order_num < total:
        row.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data="examnext"))
    return row


def closed_answer_keyboard(order_num: int, selected: str | None, total: int) -> InlineKeyboardMarkup:
    def label(letter: str) -> str:
        return f"✅{letter}" if selected == letter else letter

    rows = [
        [
            InlineKeyboardButton(text=label("A"), callback_data=f"examans:{order_num}:A"),
            InlineKeyboardButton(text=label("B"), callback_data=f"examans:{order_num}:B"),
            InlineKeyboardButton(text=label("C"), callback_data=f"examans:{order_num}:C"),
            InlineKeyboardButton(text=label("D"), callback_data=f"examans:{order_num}:D"),
        ]
    ]
    nav = _nav_row(order_num, total)
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text="🗺 Navigator", callback_data="examnav"),
            InlineKeyboardButton(text="🏁 Yakunlash", callback_data="examfinish"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def open_question_keyboard(order_num: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    nav = _nav_row(order_num, total)
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text="🗺 Navigator", callback_data="examnav"),
            InlineKeyboardButton(text="🏁 Yakunlash", callback_data="examfinish"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def navigator_keyboard(questions, answers_map: dict[int, str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for question in questions:
        answered = bool(answers_map.get(question.question_id))
        mark = "✅" if answered else "⬜"
        row.append(
            InlineKeyboardButton(text=f"{mark}{question.order_num}", callback_data=f"examgoto:{question.order_num}")
        )
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Yopish", callback_data="examnavclose")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def finish_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, yakunlash", callback_data="examfinishyes"),
                InlineKeyboardButton(text="➡️ Davom etish", callback_data="examfinishno"),
            ]
        ]
    )
