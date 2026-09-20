from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot.config import settings

MINIAPP_BUTTON_TEXT = "🖥 Natijalar (Mini App)"


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="➕ Yangi test"), KeyboardButton(text="📋 Testlar")],
        [KeyboardButton(text="💳 To'lovlar"), KeyboardButton(text="✉️ Apellyatsiyalar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 E'lon yuborish")],
        [KeyboardButton(text="🖼 Marketing rasm")],
    ]
    # Oddiy matnli tugma: reply-klaviatura web_app tugmasi Mini App'ga initData
    # bermaydi (autentifikatsiya ishlamaydi) -- shuning uchun bosilganda
    # inline web_app tugmasi yuboriladi (panel.py).
    if settings.MINIAPP_DOMAIN:
        rows.append([KeyboardButton(text=MINIAPP_BUTTON_TEXT)])
    rows.append([KeyboardButton(text="⬅️ Foydalanuvchi rejimiga qaytish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_miniapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Natijalarni ochish", web_app=WebAppInfo(url=settings.admin_miniapp_url))]
        ]
    )
