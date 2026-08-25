from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def pay_button_keyboard(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish", callback_data=f"pay:start:{test_id}")]
        ]
    )


def enter_test_keyboard(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="▶️ Kirish", callback_data=f"examenter:{test_id}")]]
    )


def approve_reject_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay:approve:{payment_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay:reject:{payment_id}"),
            ]
        ]
    )


def reject_reason_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Summa kam", callback_data=f"payreason:{payment_id}:summa_kam")],
            [InlineKeyboardButton(text="Chek soxta", callback_data=f"payreason:{payment_id}:soxta")],
            [InlineKeyboardButton(text="Boshqa (yozaman)", callback_data=f"payreason:{payment_id}:boshqa")],
        ]
    )
