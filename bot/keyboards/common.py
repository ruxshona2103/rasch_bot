from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def cancel_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="flow:cancel")]]
    )


def with_cancel_row(keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Mavjud inline klaviaturaga pastdan '❌ Bekor qilish' qatorini qo'shadi."""
    rows = list(keyboard.inline_keyboard) + [
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="flow:cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_cancel_keyboard(back_data: str) -> InlineKeyboardMarkup:
    """Ko'p qadamli jarayonlarda '⬅️ Orqaga' (faqat shu qadamni bekor qilib,
    oldingi qadamga qaytaradi — kiritilgan ma'lumotlar yo'qolmaydi) va
    '❌ Bekor qilish' (butun jarayonni to'liq tugatadi) tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_data)],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="flow:cancel")],
        ]
    )
