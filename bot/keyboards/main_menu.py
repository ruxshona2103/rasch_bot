from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Jonli testlar"), KeyboardButton(text="📚 Arxiv testlar")],
            [KeyboardButton(text="👤 Kabinetim"), KeyboardButton(text="📊 Natijalarim")],
            [KeyboardButton(text="🎥 Video yechimlar"), KeyboardButton(text="ℹ️ Yordam / Aloqa")],
        ],
        resize_keyboard=True,
    )
