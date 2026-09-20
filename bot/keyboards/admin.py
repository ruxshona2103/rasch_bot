from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="➕ Yangi test"), KeyboardButton(text="📋 Testlar")],
        [KeyboardButton(text="💳 To'lovlar"), KeyboardButton(text="✉️ Apellyatsiyalar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 E'lon yuborish")],
        [KeyboardButton(text="🖼 Marketing rasm")],
    ]
    rows.append([KeyboardButton(text="⬅️ Foydalanuvchi rejimiga qaytish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

