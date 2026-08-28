"""🆕 Avtomatik marketing e'lonlari — barcha (yoki tegishli) foydalanuvchilarga
ismi bilan murojaat qilingan, rasm + kuchli matn bilan:

1) Yangi jonli test yaratilganda (announce_new_test)
2) Jonli testga aniq vaqt belgilanganda (announce_schedule)
3) Boshlanishdan 5 daqiqa oldin, hali to'lamaganlarga (announce_urgency)
"""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards.payment import pay_button_keyboard
from db.queries import (
    get_setting,
    list_all_active_users,
    list_users_without_purchase,
    mark_user_blocked,
)

logger = logging.getLogger(__name__)

MARKETING_LOGO_KEY = "marketing_logo_file_id"


def _fmt_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


def _first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name.strip() else "Hurmatli o'quvchi"


async def _broadcast(
    bot: Bot,
    session: AsyncSession,
    users: list,
    caption_fn,
    keyboard: InlineKeyboardMarkup,
) -> tuple[int, int]:
    logo_file_id = await get_setting(session, MARKETING_LOGO_KEY)
    sent, blocked = 0, 0
    for user in users:
        caption = caption_fn(user.full_name)
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


# ---------------- 1) Yangi jonli test yaratildi ----------------


def build_announcement_caption(full_name: str, test, question_count: int) -> str:
    first_name = _first_name(full_name)
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
    users = await list_all_active_users(session)
    keyboard = pay_button_keyboard(test.test_id)
    return await _broadcast(
        bot, session, users,
        lambda full_name: build_announcement_caption(full_name, test, question_count),
        keyboard,
    )


# ---------------- 2) Jonli testga aniq vaqt belgilandi ----------------


def build_schedule_caption(full_name: str, test, question_count: int) -> str:
    first_name = _first_name(full_name)
    local_start = test.start_at.astimezone(settings.tzinfo)
    return (
        f"📅 {first_name}, MUHIM E'LON!\n\n"
        f"🔴 \"{test.title}\" jonli testining VAQTI BELGILANDI:\n"
        f"🗓 {local_start:%d-%m-%Y}, soat {local_start:%H:%M} (Toshkent vaqti)\n\n"
        f"📚 {question_count} ta savol | 💰 Narxi: {_fmt_price(test.price)}\n\n"
        "⏳ Joyingizni band qilish uchun hoziroq to'lov qiling — test "
        "boshlangach chipta sotib olib bo'lmaydi!\n\n"
        "👇 Pastdagi tugma orqali hoziroq qatnashing:"
    )


async def announce_schedule(bot: Bot, session: AsyncSession, test, question_count: int) -> tuple[int, int]:
    users = await list_all_active_users(session)
    keyboard = pay_button_keyboard(test.test_id)
    return await _broadcast(
        bot, session, users,
        lambda full_name: build_schedule_caption(full_name, test, question_count),
        keyboard,
    )


# ---------------- 3) Boshlanishdan 5 daqiqa oldin (shoshiltiruvchi) ----------------


def build_urgency_caption(full_name: str, test) -> str:
    first_name = _first_name(full_name)
    time_text = "tez orada"
    if test.start_at:
        local_start = test.start_at.astimezone(settings.tzinfo)
        time_text = f"soat {local_start:%H:%M} da"
    return (
        f"⏰ {first_name}, SHOSHILING!\n\n"
        f"🔴 \"{test.title}\" atigi 5 DAQIQADAN KEYIN, {time_text} boshlanadi!\n"
        "🚨 Hali to'lov qilmagan bo'lsangiz — ULGURING, vaqt tugab bormoqda!\n\n"
        "👇 Pastdagi tugma orqali hoziroq qatnashing:"
    )


async def announce_urgency(bot: Bot, session: AsyncSession, test) -> tuple[int, int]:
    """Faqat hali chiptasi yo'q foydalanuvchilarga (allaqachon to'laganlarga
    'shoshiling to'lang' deb yuborish noo'rin)."""
    users = await list_users_without_purchase(session, test.test_id)
    keyboard = pay_button_keyboard(test.test_id)
    return await _broadcast(
        bot, session, users,
        lambda full_name: build_urgency_caption(full_name, test),
        keyboard,
    )
