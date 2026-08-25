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
