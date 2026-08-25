"""III.5-bo'lim: Exam Mode (MVP). Savolni ko'rsatish, javob qabul qilish,
Navigator, yakunlash. Taymer statik ko'rsatiladi (real-time soniyama-soniya
yangilanmaydi — Telegram botlarda odatiy amaliyot). Arxiv urinishlar
yakunlanganda darhol MLE/klassik ball ko'rsatadi (core.rasch); jonli
urinishlar admin "Yakunlash" bosgach guruh bo'lib hisoblanadi.
"""

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards.exam import (
    closed_answer_keyboard,
    finish_confirm_keyboard,
    navigator_keyboard,
    open_question_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states.exam import Exam
from core.answer_key import normalize_open_answer
from core.rasch import score_archive_attempt
from db.queries import (
    auto_close_attempt,
    create_attempt,
    finish_attempt,
    get_answers_map,
    get_attempt,
    get_questions_for_test,
    get_test,
    get_user_by_telegram_id,
    has_purchase,
    upsert_answer,
)

router = Router(name="exam")


async def _chat_id(target) -> int:
    return target.chat.id if isinstance(target, Message) else target.message.chat.id


async def _render_question(target, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    test = await get_test(session, data["test_id"])
    chat_id = await _chat_id(target)
    bot = target.bot

    # Har harakatda qayta tekshiruv: admin jonli testni to'xtatgan bo'lsa,
    # foydalanuvchi majburan Exam Mode'dan chiqariladi (javoblari saqlangan holda).
    if test.mode == "jonli" and test.status != "jonli_davom":
        await auto_close_attempt(session, data["attempt_id"])
        await state.clear()
        await bot.send_message(
            chat_id,
            "⏰ Test admin tomonidan yakunlandi. Javoblaringiz saqlandi.",
            reply_markup=main_menu_keyboard(),
        )
        return

    questions = await get_questions_for_test(session, data["test_id"])
    total = len(questions)
    order = data["current_order"]
    question = questions[order - 1]
    answers_map = await get_answers_map(session, data["attempt_id"])
    answered_count = sum(1 for q in questions if q.question_id in answers_map)

    header = f"📝 {order}/{total} | ✅ Belgilangan: {answered_count}"
    body = (question.text or "").strip()
    caption = f"{header}\n\n{body}".strip()

    if question.qtype == "yopiq":
        keyboard = closed_answer_keyboard(order, answers_map.get(question.question_id), total)
    else:
        keyboard = open_question_keyboard(order, total)
        current_val = answers_map.get(question.question_id)
        caption += (
            f"\n\n✍️ Joriy javobingiz: {current_val}"
            if current_val
            else "\n\n✍️ Javobni raqamda yozing (masalan: 12 yoki -3,5)"
        )

    if question.image_file_id:
        await bot.send_photo(chat_id, photo=question.image_file_id, caption=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, caption, reply_markup=keyboard)


@router.callback_query(F.data.startswith("examenter:"))
async def enter_exam(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if test is None or not await has_purchase(session, user.user_pk, test_id):
        await callback.answer("🔒 Bu test uchun kirish huquqi yo'q.", show_alert=True)
        return
    if test.mode == "jonli" and test.status != "jonli_davom":
        await callback.answer("⏳ Test hali boshlanmagan yoki allaqachon yakunlangan.", show_alert=True)
        return

    questions = await get_questions_for_test(session, test_id)
    if not questions:
        await callback.answer("⚠️ Bu testda hali savollar yo'q.", show_alert=True)
        return

    attempt = await get_attempt(session, user.user_pk, test_id)
    if attempt is None:
        deadline_at = datetime.now(settings.tzinfo) + timedelta(minutes=test.duration_min)
        attempt = await create_attempt(session, user.user_pk, test_id, kind=test.mode, deadline_at=deadline_at)
    elif attempt.status != "davom_etmoqda":
        await callback.answer("✅ Siz bu testni allaqachon yakunlagansiz.", show_alert=True)
        return

    answers_map = await get_answers_map(session, attempt.attempt_id)
    start_order = questions[-1].order_num
    for q in questions:
        if q.question_id not in answers_map:
            start_order = q.order_num
            break

    await state.set_state(Exam.taking)
    await state.update_data(attempt_id=attempt.attempt_id, test_id=test_id, current_order=start_order)

    await callback.answer()
    await callback.message.answer("🔴 Exam Mode boshlandi!\n⚠️ Javobingiz har bosishda darhol saqlanadi.")
    await _render_question(callback.message, session, state)


@router.callback_query(Exam.taking, F.data == "examprev")
async def go_prev(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(current_order=data["current_order"] - 1)
    await callback.answer()
    await _render_question(callback.message, session, state)


@router.callback_query(Exam.taking, F.data == "examnext")
async def go_next(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(current_order=data["current_order"] + 1)
    await callback.answer()
    await _render_question(callback.message, session, state)


@router.callback_query(Exam.taking, F.data.startswith("examgoto:"))
async def go_to(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    order = int(callback.data.split(":")[1])
    await state.update_data(current_order=order)
    await callback.answer()
    await _render_question(callback.message, session, state)


@router.callback_query(Exam.taking, F.data == "examnav")
async def open_navigator(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    questions = await get_questions_for_test(session, data["test_id"])
    answers_map = await get_answers_map(session, data["attempt_id"])
    await callback.answer()
    await callback.message.answer("🗺 Navigator:", reply_markup=navigator_keyboard(questions, answers_map))


@router.callback_query(Exam.taking, F.data == "examnavclose")
async def close_navigator(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer()


@router.callback_query(Exam.taking, F.data.startswith("examans:"))
async def select_answer(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    _, order_str, letter = callback.data.split(":")
    data = await state.get_data()
    questions = await get_questions_for_test(session, data["test_id"])
    question = questions[int(order_str) - 1]
    await upsert_answer(session, data["attempt_id"], question.question_id, letter)
    await callback.answer("✅ Saqlandi")
    await _render_question(callback.message, session, state)


@router.message(Exam.taking, F.text)
async def input_open_answer(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    questions = await get_questions_for_test(session, data["test_id"])
    question = questions[data["current_order"] - 1]
    if question.qtype != "ochiq":
        await message.answer("❗️ Bu savol uchun tugmalardan birini tanlang.")
        return
    answer = normalize_open_answer(message.text)
    await upsert_answer(session, data["attempt_id"], question.question_id, answer)
    await _render_question(message, session, state)


@router.message(Exam.taking)
async def input_invalid(message: Message) -> None:
    await message.answer("❗️ Stiker/rasm qabul qilinmaydi. Javobni matn yoki tugma orqali yuboring.")


@router.callback_query(Exam.taking, F.data == "examfinish")
async def ask_finish(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    questions = await get_questions_for_test(session, data["test_id"])
    answers_map = await get_answers_map(session, data["attempt_id"])
    unanswered = sum(1 for q in questions if q.question_id not in answers_map)
    await callback.answer()
    await callback.message.answer(
        f"⚠️ {unanswered} savol belgilanmagan. Rostdanmi yakunlaymiz?",
        reply_markup=finish_confirm_keyboard(),
    )


@router.callback_query(Exam.taking, F.data == "examfinishyes")
async def finish_yes(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    await finish_attempt(session, data["attempt_id"])
    test = await get_test(session, data["test_id"])
    await state.clear()
    await callback.answer()

    if test.mode == "arxiv":
        ball, grade = await score_archive_attempt(session, data["attempt_id"])
        await callback.message.answer(
            "✅ Test yakunlandi!\n"
            f"🏆 Ball: {ball} / 75 | 🎖 Daraja: {grade or 'Baholanmadi'}\n"
            "🏋️ Bu mashq rejimi — ball jonli sinovda kalibrlangan qiyinlik "
            "darajalari asosida taxminiy hisoblanadi, rasmiy natija emas.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            "✅ Test yakunlandi!\n"
            "⏳ Natijalar test admin tomonidan yakunlangach e'lon qilinadi.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(Exam.taking, F.data == "examfinishno")
async def finish_no(callback: CallbackQuery) -> None:
    await callback.answer("Davom etamiz")
