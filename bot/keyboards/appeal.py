from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def appeal_button_keyboard(attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✉️ Apellyatsiya", callback_data=f"appeal:start:{attempt_id}")]]
    )


def appeal_review_keyboard(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔧 Kalitni tuzatish", callback_data=f"appeal:fixkey:{appeal_id}")],
            [InlineKeyboardButton(text="🗑 Savolni chiqarish", callback_data=f"appeal:exclude:{appeal_id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"appeal:reject:{appeal_id}")],
        ]
    )
