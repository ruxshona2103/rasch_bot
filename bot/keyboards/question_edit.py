from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def edit_menu_keyboard(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Savol qo'shish", callback_data=f"qedit:add:{test_id}")],
            [InlineKeyboardButton(text="✏️ Savolni o'zgartirish", callback_data=f"qedit:edit:{test_id}")],
            [InlineKeyboardButton(text="🗑 Savolni o'chirish", callback_data=f"qedit:delete:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"qedit:back:{test_id}")],
        ]
    )
