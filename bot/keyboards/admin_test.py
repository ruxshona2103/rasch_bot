from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.common import with_cancel_row


def price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Tekin (bepul)", callback_data="tcprice:free")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="tcback:duration")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="flow:cancel")],
        ]
    )


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


OPTION_COUNTS = (4, 5, 6)


def manual_closed_answer_keyboard(option_count: int = 4) -> InlineKeyboardMarkup:
    """To'g'ri javob tugmalari (A..) + variantlar sonini tanlash qatori."""
    letters = [chr(ord("A") + i) for i in range(option_count)]
    counts = [
        InlineKeyboardButton(
            text=f"{'✅ ' if n == option_count else ''}{n} variant", callback_data=f"optcnt:{n}"
        )
        for n in OPTION_COUNTS
    ]
    return with_cancel_row(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=l, callback_data=f"answer:{l}") for l in letters],
                counts,
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
