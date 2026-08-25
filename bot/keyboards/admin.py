from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yangi test"), KeyboardButton(text="📋 Testlar")],
            [KeyboardButton(text="💳 To'lovlar"), KeyboardButton(text="✉️ Apellyatsiyalar")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 E'lon yuborish")],
            [KeyboardButton(text="⬅️ Foydalanuvchi rejimiga qaytish")],
        ],
        resize_keyboard=True,
    )
