from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_NOT_CANCELLABLE = {"bekor_qilingan", "yakunlangan"}


def test_actions_keyboard(test) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if test.mode == "jonli":
        if test.status == "tayyorlanmoqda":
            rows.append(
                [
                    InlineKeyboardButton(text="🕐 Vaqt belgilash", callback_data=f"testschedule:{test.test_id}"),
                    InlineKeyboardButton(text="▶️ Hoziroq boshlash", callback_data=f"teststart:{test.test_id}"),
                ]
            )
        elif test.status == "rejalashtirilgan":
            rows.append(
                [InlineKeyboardButton(text="▶️ Hoziroq boshlash", callback_data=f"teststart:{test.test_id}")]
            )
        elif test.status == "jonli_davom":
            rows.append(
                [InlineKeyboardButton(text="🏁 Yakunlash", callback_data=f"testfinish:{test.test_id}")]
            )

    rows.append(
        [InlineKeyboardButton(text="🎥 Video qo'shish", callback_data=f"testvideo:{test.test_id}")]
    )
    if test.status not in _NOT_CANCELLABLE:
        rows.append(
            [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data=f"testcancel:{test.test_id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm_keyboard(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, bekor qilish", callback_data=f"testcancelyes:{test_id}"),
                InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"testcancelno:{test_id}"),
            ]
        ]
    )
