"""🆕 Yangi jonli test yaratilganda barcha foydalanuvchilarga avtomatik,
ismi bilan murojaat qilingan marketing e'loni yuboriladi (rasm + kuchli matn).
"""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.payment import pay_button_keyboard
from db.queries import get_setting, list_all_active_users, mark_user_blocked

logger = logging.getLogger(__name__)

MARKETING_LOGO_KEY = "marketing_logo_file_id"


def _fmt_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


def build_announcement_caption(full_name: str, test, question_count: int) -> str:
    first_name = full_name.strip().split()[0] if full_name.strip() else "Hurmatli o'quvchi"
    return (
        f"🔥 {first_name}, DIQQAT — YANGI JONLI MOCK-TEST OCHILDI!\n\n"
        f"🏆 {test.title}\n"
        f"📚 {question_count} ta savol — haqiqiy Milliy sertifikat imtihoni formatida\n"
        f"⏱ Davomiyligi: {test.duration_min} daqiqa\n"
        f"💰 Narxi: {_fmt_price(test.price)}\n\n"
        "⚡️ Nega aynan hozir qatnashishingiz kerak:\n"
        "✅ Rasch modeli asosida — xalqaro aniqlikdagi baholash\n"
        "✅ O'z darajangizni (A+/A/B+/B/C+/C) aniq bilib olasiz\n"
        "✅ Boshqa o'quvchilar orasida umumiy reytingda o'rningizni ko'rasiz\n"
        "✅ Haqiqiy imtihon kuni uchun eng yaqin tayyorgarlik\n\n"
        "⏳ Joylar CHEKLANGAN — hoziroq to'lovni amalga oshiring, imtihon kuni "
        "afsuslanib qolmang!\n\n"
        "👇 Pastdagi tugma orqali hoziroq qatnashing:"
    )


async def announce_new_test(bot: Bot, session: AsyncSession, test, question_count: int) -> tuple[int, int]:
    """Barcha bloklanmagan foydalanuvchilarga yuboradi. Qaytaradi: (yetdi, bloklagan)."""
    logo_file_id = await get_setting(session, MARKETING_LOGO_KEY)
    users = await list_all_active_users(session)
    keyboard = pay_button_keyboard(test.test_id)

    sent, blocked = 0, 0
    for user in users:
        caption = build_announcement_caption(user.full_name, test, question_count)
        try:
            if logo_file_id:
                await bot.send_photo(user.telegram_id, photo=logo_file_id, caption=caption, reply_markup=keyboard)
            else:
                await bot.send_message(user.telegram_id, caption, reply_markup=keyboard)
            sent += 1
        except TelegramForbiddenError:
            await mark_user_blocked(session, user.user_pk)
            blocked += 1
        except Exception:
            logger.warning("Marketing xabari yuborilmadi: user_pk=%s", user.user_pk, exc_info=True)
        await asyncio.sleep(0.04)  # ~25 msg/s, Telegram limitiga mos

    return sent, blocked
