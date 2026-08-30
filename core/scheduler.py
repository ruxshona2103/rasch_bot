"""IV.3-bo'lim: avtopilot. Jonli test uchun 4 vazifa:
eslatma (-30 daq) -> ochish (start_at) -> yopish (deadline_at) -> Rasch (+5 daq).

🆕 Restart himoyasi: joblar xotirada saqlanadi (MemoryJobStore), lekin bot
qayta ishga tushganda `recover_all_jobs()` orqali bazadagi `tests.status`dan
kelib chiqib qayta tiklanadi — allaqachon o'tgan bosqichlar qayta bajarilmaydi.
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings
from db.engine import async_session
from db.queries import get_test, list_purchasers, list_tests_by_mode, mark_test_status

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("rejalashtirilgan", "jonli_davom", "hisoblanmoqda")


def create_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(
        timezone=settings.tzinfo,
        job_defaults={"misfire_grace_time": None, "coalesce": True},
    )


async def _notify(bot: Bot, telegram_id: int, text: str) -> None:
    try:
        await bot.send_message(telegram_id, text)
    except Exception:
        logger.warning("Xabar yuborilmadi: telegram_id=%s", telegram_id, exc_info=True)


async def send_reminder(bot: Bot, test_id: int) -> None:
    async with async_session() as session:
        test = await get_test(session, test_id)
        if test is None or test.status != "rejalashtirilgan":
            return
        for user in await list_purchasers(session, test_id):
            await _notify(bot, user.telegram_id, f"🔔 ID: {user.public_id} — 30 daqiqa qoldi! \"{test.title}\"")


async def send_urgency_reminder(bot: Bot, test_id: int) -> None:
    """🆕 Boshlanishdan 5 daqiqa oldin — hali chiptasi yo'q foydalanuvchilarga
    marketing rasmi bilan shoshiltiruvchi eslatma (III.4/V-bo'lim marketing)."""
    from core.marketing import announce_urgency

    async with async_session() as session:
        test = await get_test(session, test_id)
        if test is None or test.status != "rejalashtirilgan":
            return
        sent, blocked = await announce_urgency(bot, session, test)
    logger.info("Shoshiltiruvchi eslatma: test_id=%s, sent=%s, blocked=%s", test_id, sent, blocked)


async def open_test(bot: Bot, test_id: int) -> None:
    async with async_session() as session:
        test = await get_test(session, test_id)
        if test is None:
            return
        changed = await mark_test_status(session, test_id, ("rejalashtirilgan",), "jonli_davom")
        if not changed:
            return
        for user in await list_purchasers(session, test_id):
            await _notify(
                bot,
                user.telegram_id,
                f"▶️ \"{test.title}\" boshlandi!\n"
                "⚠️ Exam Mode hali ishlab chiqilmoqda — testni topshirish tez orada qo'shiladi.",
            )
    logger.info("Test ochildi: test_id=%s", test_id)


async def close_test(bot: Bot, test_id: int) -> None:
    async with async_session() as session:
        changed = await mark_test_status(
            session, test_id, ("rejalashtirilgan", "jonli_davom"), "hisoblanmoqda"
        )
        if not changed:
            return
        # "davom_etmoqda" urinishlar bu yerda emas, balki
        # core.rasch.finalize_jonli_test boshida avtomatik yakunlanadi
        # (Rasch hisoblashdan to'g'ridan-to'g'ri oldin, run_rasch chaqirilganda).
    logger.info("Test yopildi (to'lov/kirish to'xtatildi): test_id=%s", test_id)


async def run_rasch(bot: Bot, test_id: int) -> None:
    from core.rasch import finalize_jonli_test, format_breakdown

    async with async_session() as session:
        test = await get_test(session, test_id)
        if test is None:
            return

        results = await finalize_jonli_test(session, test_id)
        test = await get_test(session, test_id)
        total = len(results)
        lookup = {r.user_pk: r for r in results}

        for user in await list_purchasers(session, test_id):
            result = lookup.get(user.user_pk)
            if result is None:
                continue
            await _notify(
                bot,
                user.telegram_id,
                f"🏆 \"{test.title}\" NATIJANGIZ\n"
                f"📊 Ball: {result.ball_75} / 75 | 🎖 Daraja: {result.grade or 'Baholanmadi'}\n"
                f"🥇 Reyting: {total} tadan {result.rank_position}-o'rin\n\n"
                f"{format_breakdown(result.correct_orders, result.wrong_orders)}",
            )
    logger.info("Rasch bosqichi yakunlandi: test_id=%s, %d natija", test_id, total)


def _job_id(kind: str, test_id: int) -> str:
    return f"{kind}:{test_id}"


def schedule_test(scheduler: AsyncIOScheduler, bot: Bot, test) -> None:
    """Test yaratilganda YOKI bot qayta ishga tushganda chaqiriladi.
    test.status'ga qarab, allaqachon o'tgan bosqichlarni qayta rejalashtirmaydi.

    🆕 Yangi testlar endi vaqtsiz ('tayyorlanmoqda', start_at/deadline_at=None)
    yaratiladi va admin "▶️ Boshlash"/"🏁 Yakunlash" tugmalari orqali qo'lda
    boshqaradi — bunday testlar uchun bu funksiya HECH NARSA qilmaydi (pastdagi
    None tekshiruvlar orqali). Faqat eski, sana bilan rejalashtirilgan testlar
    uchun ishlaydi (orqaga moslik)."""
    if test.mode != "jonli" or test.status not in _ACTIVE_STATUSES:
        return

    now = datetime.now(settings.tzinfo)

    if test.status == "rejalashtirilgan" and test.start_at is not None:
        reminder_time = test.start_at - timedelta(minutes=30)
        if reminder_time > now:
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=reminder_time,
                args=[bot, test.test_id],
                id=_job_id("reminder", test.test_id),
                replace_existing=True,
            )
        urgency_time = test.start_at - timedelta(minutes=5)
        if urgency_time > now:
            scheduler.add_job(
                send_urgency_reminder,
                "date",
                run_date=urgency_time,
                args=[bot, test.test_id],
                id=_job_id("urgency", test.test_id),
                replace_existing=True,
            )
        scheduler.add_job(
            open_test,
            "date",
            run_date=test.start_at,
            args=[bot, test.test_id],
            id=_job_id("open", test.test_id),
            replace_existing=True,
        )

    if test.status in ("rejalashtirilgan", "jonli_davom") and test.deadline_at is not None:
        scheduler.add_job(
            close_test,
            "date",
            run_date=test.deadline_at,
            args=[bot, test.test_id],
            id=_job_id("close", test.test_id),
            replace_existing=True,
        )

    if test.deadline_at is not None:
        scheduler.add_job(
            run_rasch,
            "date",
            run_date=test.deadline_at + timedelta(minutes=5),
            args=[bot, test.test_id],
            id=_job_id("rasch", test.test_id),
            replace_existing=True,
        )


async def recover_all_jobs(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """Bot ishga tushganda chaqiriladi — bazadan faol jonli testlarni o'qib,
    ularning avtopilot vazifalarini qayta tiklaydi (VI-qism, restart himoyasi)."""
    async with async_session() as session:
        tests = [t for t in await list_tests_by_mode(session, "jonli") if t.status in _ACTIVE_STATUSES]

    for test in tests:
        schedule_test(scheduler, bot, test)

    logger.info("Scheduler: %d ta faol jonli test uchun vazifalar tiklandi", len(tests))
