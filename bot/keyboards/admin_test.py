from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import with_cancel_row


def mode_keyboard() -> InlineKeyboardMarkup:
    return with_cancel_row(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔴 Jonli", callback_data="mode:jonli"),
                    InlineKeyboardButton(text="📚 Arxiv", callback_data="mode:arxiv"),
                ]
            ]
        )
    )


def method_keyboard() -> InlineKeyboardMarkup:
    return with_cancel_row(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 PDF orqali", callback_data="method:pdf")],
                [InlineKeyboardButton(text="✍️ Qo'lda kiritish", callback_data="method:manual")],
            ]
        )
    )


def yes_no_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=yes_data),
                InlineKeyboardButton(text="❌ Yo'q", callback_data=no_data),
            ]
        ]
    )


def manual_qtype_keyboard() -> InlineKeyboardMarkup:
    return with_cancel_row(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Yopiq (A/B/C/D)", callback_data="qtype:yopiq"),
                    InlineKeyboardButton(text="✍️ Ochiq (raqamli)", callback_data="qtype:ochiq"),
                ]
            ]
        )
    )


def manual_closed_answer_keyboard() -> InlineKeyboardMarkup:
    return with_cancel_row(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="A", callback_data="answer:A"),
                    InlineKeyboardButton(text="B", callback_data="answer:B"),
                    InlineKeyboardButton(text="C", callback_data="answer:C"),
                    InlineKeyboardButton(text="D", callback_data="answer:D"),
                ]
            ]
        )
    )


def manual_next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Yana savol", callback_data="manual:more"),
                InlineKeyboardButton(text="🏁 Tugatish", callback_data="manual:finish"),
            ]
        ]
    )
