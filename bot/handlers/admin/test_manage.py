"""IV.3-bo'lim: testlar ro'yxati, vaqt belgilash/qo'lda boshlash/yakunlash, video qo'shish, bekor qilish."""

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.filters.admin import IsAdmin
from bot.keyboards.common import cancel_inline_keyboard
from bot.keyboards.test_manage import cancel_confirm_keyboard, delete_confirm_keyboard, test_actions_keyboard
from bot.states.payment import TestManage
from core.marketing import announce_schedule
from core.rasch import finalize_jonli_test, format_breakdown
from core.scheduler import schedule_test
from db.queries import (
    archive_finished_test,
    cancel_test,
    count_questions,
    delete_test_completely,
    finish_test_manually,
    get_test,
    list_all_tests,
    list_purchasers,
    set_test_schedule,
    set_test_video_url,
    start_test_manually,
)

router = Router(name="admin_test_manage")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

_STATUS_LABELS = {
    "tayyorlanmoqda": "🛠 Tayyorlanmoqda (vaqt belgilanmagan)",
    "rejalashtirilgan": "🗓 Rejalashtirilgan",
    "jonli_davom": "🔴 Jonli davom etmoqda",
    "hisoblanmoqda": "⏳ Hisoblanmoqda",
    "yakunlangan": "✅ Yakunlangan",
    "arxivda": "📚 Arxivda",
    "bekor_qilingan": "🚫 Bekor qilingan",
}


def _fmt_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


def _test_text(test) -> str:
    lines = [
        test.title,
        f"Holat: {_STATUS_LABELS.get(test.status, test.status)} | 💰 {_fmt_price(test.price)}",
    ]
    if test.mode == "jonli" and test.status == "rejalashtirilgan" and test.start_at:
        local_start = test.start_at.astimezone(settings.tzinfo)
        lines.append(f"📅 Boshlanishi: {local_start:%d-%m %H:%M} (Toshkent vaqti)")
    return "\n".join(lines)


@router.message(F.text == "📋 Testlar")
async def list_tests(message: Message, session: AsyncSession) -> None:
    tests = await list_all_tests(session)
    if not tests:
        await message.answer("Hozircha testlar yo'q.")
        return

    for test in tests:
        await message.answer(_test_text(test), reply_markup=test_actions_keyboard(test))


@router.callback_query(F.data.startswith("testschedule:"))
async def ask_schedule_time(callback: CallbackQuery, state: FSMContext) -> None:
    test_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_test_id=test_id)
    await state.set_state(TestManage.waiting_schedule_time)
    await callback.message.answer(
        f"📅 Boshlanish sanasi va vaqtini kiriting ({settings.TIMEZONE} — Toshkent vaqti bilan), "
        "masalan: 12.02 20:00",
        reply_markup=cancel_inline_keyboard(),
    )
    await callback.answer()


@router.message(TestManage.waiting_schedule_time, F.text)
async def process_schedule_time(
    message: Message, state: FSMContext, session: AsyncSession, scheduler: AsyncIOScheduler
) -> None:
    data = await state.get_data()
    test_id = data["schedule_test_id"]
    test = await get_test(session, test_id)

    try:
        day_month, time_part = message.text.strip().split()
        day, month = (int(x) for x in day_month.split("."))
        hour, minute = (int(x) for x in time_part.split(":"))
        year = datetime.now(settings.tzinfo).year
        start_at = datetime(year, month, day, hour, minute, tzinfo=settings.tzinfo)
    except (ValueError, TypeError):
        await message.answer(
            "❗️ Format noto'g'ri. Masalan: 12.02 20:00 (Toshkent vaqti) — qayta kiriting:",
            reply_markup=cancel_inline_keyboard(),
        )
        return

    deadline_at = start_at + timedelta(minutes=test.duration_min)

    changed = await set_test_schedule(session, test_id, start_at, deadline_at)
    await state.clear()
    if not changed:
        await message.answer("⚠️ Bu testga endi vaqt belgilab bo'lmaydi.")
        return

    test = await get_test(session, test_id)
    schedule_test(scheduler, message.bot, test)

    await message.answer(
        f"✅ Vaqt belgilandi: {start_at:%d-%m %H:%M} (Toshkent vaqti). "
        "Test shu vaqtda avtomatik boshlanadi.\n📢 Barcha foydalanuvchilarga e'lon yuborilmoqda...",
        reply_markup=test_actions_keyboard(test),
    )

    question_count = await count_questions(session, test_id)
    sent, blocked = await announce_schedule(message.bot, session, test, question_count)
    await message.answer(
        f"✅ Vaqt e'loni {sent} kishiga yetdi, 🚫 {blocked} bloklagan.",
    )


@router.callback_query(F.data.startswith("teststart:"))
async def start_test_now(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    changed = await start_test_manually(session, test_id)
    if not changed:
        await callback.answer("⚠️ Bu testni hozir boshlab bo'lmaydi.", show_alert=True)
        return

    test = await get_test(session, test_id)
    for user in await list_purchasers(session, test_id):
        try:
            await callback.bot.send_message(
                user.telegram_id,
                f"▶️ \"{test.title}\" boshlandi!\n"
                "⚠️ Exam Mode hali ishlab chiqilmoqda — testni topshirish tez orada qo'shiladi.",
            )
        except Exception:
            continue

    await callback.message.edit_text(_test_text(test), reply_markup=test_actions_keyboard(test))
    await callback.answer("✅ Test boshlandi")


@router.callback_query(F.data.startswith("testfinish:"))
async def finish_test_now(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    changed = await finish_test_manually(session, test_id)
    if not changed:
        await callback.answer("⚠️ Bu testni hozir yakunlab bo'lmaydi.", show_alert=True)
        return

    await callback.answer("⏳ Natijalar hisoblanmoqda...")

    results = await finalize_jonli_test(session, test_id)
    test = await get_test(session, test_id)
    total = len(results)
    lookup = {r.user_pk: r for r in results}

    for user in await list_purchasers(session, test_id):
        result = lookup.get(user.user_pk)
        if result is None:
            continue
        try:
            await callback.bot.send_message(
                user.telegram_id,
                f"🏆 \"{test.title}\" NATIJANGIZ\n"
                f"📊 Ball: {result.ball_75} / 75 | 🎖 Daraja: {result.grade or 'Baholanmadi'}\n"
                f"🥇 Reyting: {total} tadan {result.rank_position}-o'rin\n\n"
                f"{format_breakdown(result.correct_orders, result.wrong_orders)}",
            )
        except Exception:
            continue

    method = "Rasch (JMLE)" if test.calibrated else "klassik %"
    await callback.message.edit_text(
        f"{_test_text(test)}\n\n✅ {total} ta natija hisoblandi ({method}).",
        reply_markup=test_actions_keyboard(test),
    )


@router.callback_query(F.data.startswith("testvideo:"))
async def ask_video_url(callback: CallbackQuery, state: FSMContext) -> None:
    test_id = int(callback.data.split(":")[1])
    await state.update_data(video_test_id=test_id)
    await state.set_state(TestManage.waiting_video_url)
    await callback.message.answer("🎥 Video havolasini yuboring (YouTube/kanal post):")
    await callback.answer()


@router.message(TestManage.waiting_video_url, F.text)
async def save_video_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await set_test_video_url(session, data["video_test_id"], message.text.strip())
    await state.clear()
    await message.answer("✅ Video havolasi saqlandi.")


@router.callback_query(F.data.startswith("testcancel:"))
async def confirm_cancel(callback: CallbackQuery) -> None:
    test_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=cancel_confirm_keyboard(test_id))
    await callback.answer()


@router.callback_query(F.data.startswith("testcancelno:"))
async def cancel_no(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    await callback.message.edit_reply_markup(reply_markup=test_actions_keyboard(test))
    await callback.answer()


@router.callback_query(F.data.startswith("testcancelyes:"))
async def cancel_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    purchasers = await list_purchasers(session, test_id)

    await cancel_test(session, test_id, callback.from_user.id)

    for user in purchasers:
        try:
            await callback.bot.send_message(
                user.telegram_id,
                f"🚫 \"{test.title}\" testi bekor qilindi. Admin bilan bog'laning.",
            )
        except Exception:
            continue

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Test bekor qilindi, xabar yuborildi.")
    await callback.answer()


# ---------------- 🆕 Arxivga ko'chirish ----------------


@router.callback_query(F.data.startswith("testarchive:"))
async def ask_archive_price(callback: CallbackQuery, state: FSMContext) -> None:
    test_id = int(callback.data.split(":")[1])
    await state.update_data(archive_test_id=test_id)
    await state.set_state(TestManage.waiting_archive_price)
    await callback.message.answer(
        "📥 Arxivga ko'chirilgach qanday narxda sotilsin? (so'mda, faqat raqam):",
        reply_markup=cancel_inline_keyboard(),
    )
    await callback.answer()


@router.message(TestManage.waiting_archive_price, F.text.regexp(r"^\d+$"))
async def process_archive_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["archive_test_id"]
    await state.clear()

    changed = await archive_finished_test(session, test_id, int(message.text), message.from_user.id)
    if not changed:
        await message.answer("⚠️ Bu testni arxivga ko'chirib bo'lmaydi (faqat yakunlangan jonli testlar uchun).")
        return

    test = await get_test(session, test_id)
    await message.answer(
        f"✅ \"{test.title}\" arxivga ko'chirildi. Endi 📚 Arxiv testlar bo'limida {_fmt_price(test.price)}ga sotiladi.",
        reply_markup=test_actions_keyboard(test),
    )


@router.message(TestManage.waiting_archive_price)
async def process_archive_price_invalid(message: Message) -> None:
    await message.answer("❗️ Iltimos, faqat raqam kiriting (narx, so'm):", reply_markup=cancel_inline_keyboard())


# ---------------- 🆕 Butunlay o'chirish ----------------


@router.callback_query(F.data.startswith("testdelete:"))
async def confirm_delete(callback: CallbackQuery) -> None:
    test_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(
        reply_markup=delete_confirm_keyboard(test_id)
    )
    await callback.answer(
        "⚠️ Diqqat: bu amal testni, savollarni, to'lovlarni va urinishlarni "
        "BUTUNLAY o'chiradi, qaytarib bo'lmaydi!",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("testdeleteno:"))
async def delete_no(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    await callback.message.edit_reply_markup(reply_markup=test_actions_keyboard(test))
    await callback.answer()


@router.callback_query(F.data.startswith("testdeleteyes:"))
async def delete_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    title = test.title if test else f"test_id={test_id}"

    await delete_test_completely(session, test_id, callback.from_user.id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"🗑 \"{title}\" butunlay o'chirildi.")
    await callback.answer()
