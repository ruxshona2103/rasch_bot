from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import settings


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="➕ Yangi test"), KeyboardButton(text="📋 Testlar")],
        [KeyboardButton(text="💳 To'lovlar"), KeyboardButton(text="✉️ Apellyatsiyalar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 E'lon yuborish")],
        [KeyboardButton(text="🖼 Marketing rasm")],
    ]
    if settings.MINIAPP_DOMAIN:
        rows.append(
            [KeyboardButton(text="🖥 Natijalar (Mini App)", web_app=WebAppInfo(url=settings.admin_miniapp_url))]
        )
    rows.append([KeyboardButton(text="⬅️ Foydalanuvchi rejimiga qaytish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
