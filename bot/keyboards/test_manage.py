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

    # 🆕 Savol qo'shish/o'zgartirish/o'chirish — jonli_davom/hisoblanmoqda'dan
    # tashqari har doim (arxivdagi testlar uchun ham) ochiq
    if test.status not in ("jonli_davom", "hisoblanmoqda"):
        rows.append(
            [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"testedit:{test.test_id}")]
        )

    # 🆕 Yakunlangan jonli test: arxivga ko'chirish yoki butunlay o'chirish
    if test.mode == "jonli" and test.status == "yakunlangan":
        rows.append(
            [InlineKeyboardButton(text="📥 Arxivga ko'chirish", callback_data=f"testarchive:{test.test_id}")]
        )

    if test.status not in _NOT_CANCELLABLE:
        rows.append(
            [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data=f"testcancel:{test.test_id}")]
        )

    if test.status in ("yakunlangan", "bekor_qilingan", "arxivda"):
        rows.append(
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"testdelete:{test.test_id}")]
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


def delete_confirm_keyboard(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Ha, BUTUNLAY o'chirish", callback_data=f"testdeleteyes:{test_id}"),
                InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"testdeleteno:{test_id}"),
            ]
        ]
    )
