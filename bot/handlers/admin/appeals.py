"""IV.5-bo'lim: apellyatsiyalarni ko'rish, kalitni tuzatish, savolni chiqarish,
rad etish. Kalit tuzatilsa yoki savol chiqarilsa — shu testning barcha
jonli VA arxiv urinishlari avtomatik qayta hisoblanadi (core.rasch.rescore_test)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.appeal import appeal_review_keyboard
from bot.keyboards.common import cancel_inline_keyboard
from bot.states.appeal import AppealReview
from core.answer_key import normalize_open_answer
from core.rasch import format_breakdown, rescore_test
from db.queries import (
    exclude_question,
    get_appeal,
    get_question_by_order,
    get_test,
    get_user_by_pk,
    list_pending_appeals,
    resolve_appeal,
    set_question_correct_answer,
)

router = Router(name="admin_appeals")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "✉️ Apellyatsiyalar")
async def list_appeals(message: Message, session: AsyncSession) -> None:
    appeals = await list_pending_appeals(session)
    if not appeals:
        await message.answer("Hozircha yangi apellyatsiyalar yo'q.")
        return

    for appeal in appeals:
        user = await get_user_by_pk(session, appeal.user_pk)
        test = await get_test(session, appeal.test_id)
        await message.answer(
            f"✉️ APELLYATSIYA #{appeal.appeal_id} | 🎫 ID: {user.public_id}\n"
            f"🧪 {test.title}, {appeal.question_order_num}-savol\n"
            f"\"{appeal.comment}\"",
            reply_markup=appeal_review_keyboard(appeal.appeal_id),
        )


async def _notify_rescored(bot, session: AsyncSession, test, jonli_results, arxiv_results, reason: str) -> None:
    for result in jonli_results:
        user = await get_user_by_pk(session, result.user_pk)
        try:
            await bot.send_message(
                user.telegram_id,
                f"⚠️ \"{test.title}\" testida {reason}.\n"
                f"Yangi ballingiz: {result.ball_75} / 75 | 🎖 {result.grade or 'Baholanmadi'}\n\n"
                f"{format_breakdown(result.correct_orders, result.wrong_orders)}",
            )
        except Exception:
            continue

    for user_pk, ball, grade in arxiv_results:
        user = await get_user_by_pk(session, user_pk)
        try:
            await bot.send_message(
                user.telegram_id,
                f"⚠️ \"{test.title}\" (arxiv) testida {reason}.\n"
                f"Yangi ballingiz: {ball} / 75 | 🎖 {grade or 'Baholanmadi'}",
            )
        except Exception:
            continue


# ---------------- 🔧 Kalitni tuzatish ----------------


@router.callback_query(F.data.startswith("appeal:fixkey:"))
async def ask_new_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    appeal_id = int(callback.data.split(":")[2])
    appeal = await get_appeal(session, appeal_id)
    if appeal is None or appeal.status != "kutilmoqda":
        await callback.answer("⚠️ Bu apellyatsiya allaqachon hal qilingan.", show_alert=True)
        return

    await state.update_data(review_appeal_id=appeal_id)
    await callback.message.answer(
        f"🔧 {appeal.question_order_num}-savol uchun YANGI to'g'ri javobni kiriting\n"
        "(yopiq savol uchun A/B/C/D, ochiq savol uchun raqam — bir nechta variant "
        "bo'lsa | bilan, masalan 0.5|1/2):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(AppealReview.waiting_new_answer)
    await callback.answer()


@router.message(AppealReview.waiting_new_answer, F.text)
async def process_new_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    appeal_id = data["review_appeal_id"]
    appeal = await get_appeal(session, appeal_id)
    if appeal is None or appeal.status != "kutilmoqda":
        await state.clear()
        await message.answer("⚠️ Bu apellyatsiya allaqachon hal qilingan.")
        return

    question = await get_question_by_order(session, appeal.test_id, appeal.question_order_num)
    if question is None:
        await state.clear()
        await message.answer("⚠️ Savol topilmadi.")
        return

    raw = message.text.strip()
    if question.qtype == "yopiq":
        new_answer = raw.upper()
        if new_answer not in ("A", "B", "C", "D"):
            await message.answer("❗️ Faqat A, B, C yoki D kiriting:", reply_markup=cancel_inline_keyboard())
            return
    else:
        new_answer = "|".join(normalize_open_answer(part) for part in raw.split("|"))

    await set_question_correct_answer(session, question.question_id, new_answer)
    resolved = await resolve_appeal(session, appeal_id, message.from_user.id, "kalit_tuzatildi")
    await state.clear()
    if resolved is None:
        await message.answer("⚠️ Bu apellyatsiya shu orada boshqa admin tomonidan hal qilingan.")
        return

    await message.answer(
        f"✅ Kalit tuzatildi ({appeal.question_order_num}-savol → {new_answer}). "
        "Natijalar qayta hisoblanmoqda..."
    )

    jonli_results, arxiv_results = await rescore_test(session, appeal.test_id)
    test = await get_test(session, appeal.test_id)
    await _notify_rescored(
        message.bot, session, test, jonli_results, arxiv_results,
        f"{appeal.question_order_num}-savol kaliti tuzatildi",
    )
    await message.answer(
        f"✅ Qayta hisoblash yakunlandi: {len(jonli_results)} jonli + {len(arxiv_results)} arxiv natija yangilandi."
    )


@router.message(AppealReview.waiting_new_answer)
async def process_new_answer_invalid(message: Message) -> None:
    await message.answer("❗️ Javobni matn ko'rinishida kiriting:", reply_markup=cancel_inline_keyboard())


# ---------------- 🗑 Savolni chiqarish ----------------


@router.callback_query(F.data.startswith("appeal:exclude:"))
async def exclude_question_appeal(callback: CallbackQuery, session: AsyncSession) -> None:
    appeal_id = int(callback.data.split(":")[2])
    appeal = await get_appeal(session, appeal_id)
    if appeal is None or appeal.status != "kutilmoqda":
        await callback.answer("⚠️ Bu apellyatsiya allaqachon hal qilingan.", show_alert=True)
        return

    question = await get_question_by_order(session, appeal.test_id, appeal.question_order_num)
    if question is None:
        await callback.answer("⚠️ Savol topilmadi.", show_alert=True)
        return

    await exclude_question(session, question.question_id)
    resolved = await resolve_appeal(session, appeal_id, callback.from_user.id, "savol_chiqarildi")
    await callback.message.edit_reply_markup(reply_markup=None)
    if resolved is None:
        await callback.answer("⚠️ Bu apellyatsiya shu orada hal qilingan.", show_alert=True)
        return

    await callback.message.answer(
        f"🗑 {appeal.question_order_num}-savol kalibrlashdan chiqarildi. Natijalar qayta hisoblanmoqda..."
    )
    await callback.answer()

    jonli_results, arxiv_results = await rescore_test(session, appeal.test_id)
    test = await get_test(session, appeal.test_id)
    await _notify_rescored(
        callback.bot, session, test, jonli_results, arxiv_results,
        f"{appeal.question_order_num}-savol chiqarib tashlandi",
    )
    await callback.message.answer(
        f"✅ Qayta hisoblash yakunlandi: {len(jonli_results)} jonli + {len(arxiv_results)} arxiv natija yangilandi."
    )


# ---------------- ❌ Rad etish ----------------


@router.callback_query(F.data.startswith("appeal:reject:"))
async def reject_appeal(callback: CallbackQuery, session: AsyncSession) -> None:
    appeal_id = int(callback.data.split(":")[2])
    appeal = await resolve_appeal(session, appeal_id, callback.from_user.id, "rad_etildi")
    if appeal is None:
        await callback.answer("⚠️ Bu apellyatsiya allaqachon hal qilingan.", show_alert=True)
        return

    user = await get_user_by_pk(session, appeal.user_pk)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"❌ Apellyatsiya #{appeal_id} rad etildi.")
    try:
        await callback.bot.send_message(
            user.telegram_id,
            f"❌ Apellyatsiyangiz ({appeal.question_order_num}-savol) ko'rib chiqildi va rad etildi.",
        )
    except Exception:
        pass
    await callback.answer("Rad etildi")
