from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import settings


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🔴 Jonli testlar"), KeyboardButton(text="📚 Arxiv testlar")],
        [KeyboardButton(text="👤 Kabinetim"), KeyboardButton(text="📊 Natijalarim")],
        [KeyboardButton(text="🎥 Video yechimlar"), KeyboardButton(text="ℹ️ Yordam / Aloqa")],
    ]
    # 🆕 Mini App tayyor bo'lgandagina tugma ko'rsatiladi (domen sozlanmagan
    # bo'lsa Telegram bo'sh/noto'g'ri URL bilan xatoga chiqadi).
    if settings.MINIAPP_DOMAIN:
        rows.append([KeyboardButton(text="🖥 Mini App", web_app=WebAppInfo(url=settings.miniapp_url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
