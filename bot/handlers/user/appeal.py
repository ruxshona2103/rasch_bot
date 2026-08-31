"""III.6-bo'lim: o'quvchi natija ekranida "✉️ Apellyatsiya" tugmasi orqali
savol raqami + izoh yuboradi. Admin tomoni IV.5-bo'limda (appeals.py)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards.common import cancel_inline_keyboard
from bot.states.appeal import AppealFlow
from db.queries import (
    count_questions,
    create_appeal,
    get_attempt_by_id,
    get_test,
    get_user_by_telegram_id,
)

router = Router(name="appeal")


@router.callback_query(F.data.startswith("appeal:start:"))
async def start_appeal(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    attempt_id = int(callback.data.split(":")[2])
    attempt = await get_attempt_by_id(session, attempt_id)
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if attempt is None or user is None or attempt.user_pk != user.user_pk:
        await callback.answer("🔒 Bu urinish sizga tegishli emas.", show_alert=True)
        return

    total = await count_questions(session, attempt.test_id)
    if total == 0:
        await callback.answer("Bu testda savollar topilmadi.", show_alert=True)
        return

    await state.update_data(appeal_attempt_id=attempt_id, appeal_test_id=attempt.test_id, appeal_total=total)
    await callback.message.answer(
        f"✉️ Qaysi savol raqami bo'yicha apellyatsiya berasiz? (1-{total}):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(AppealFlow.waiting_question_number)
    await callback.answer()


@router.message(AppealFlow.waiting_question_number, F.text.regexp(r"^\d+$"))
async def process_question_number(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    num = int(message.text)
    if not (1 <= num <= data["appeal_total"]):
        await message.answer(
            f"❗️ 1 dan {data['appeal_total']} gacha raqam kiriting:", reply_markup=cancel_inline_keyboard()
        )
        return
    await state.update_data(appeal_question_num=num)
    await message.answer(
        "✍️ Izohingizni yozing (nima uchun bu javob noto'g'ri deb hisoblaysiz):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(AppealFlow.waiting_comment)


@router.message(AppealFlow.waiting_question_number)
async def process_question_number_invalid(message: Message) -> None:
    await message.answer("❗️ Faqat raqam kiriting:", reply_markup=cancel_inline_keyboard())


@router.message(AppealFlow.waiting_comment, F.text)
async def process_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    test = await get_test(session, data["appeal_test_id"])
    comment = message.text.strip()

    appeal = await create_appeal(
        session,
        user_pk=user.user_pk,
        attempt_id=data["appeal_attempt_id"],
        test_id=data["appeal_test_id"],
        question_order_num=data["appeal_question_num"],
        comment=comment,
    )
    await state.clear()
    await message.answer("✅ Apellyatsiyangiz qabul qilindi. Admin ko'rib chiqadi.")

    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(
                admin_id,
                f"✉️ APELLYATSIYA #{appeal.appeal_id}\n"
                f"🎫 ID: {user.public_id} | {user.full_name}\n"
                f"🧪 {test.title}, {data['appeal_question_num']}-savol\n"
                f"\"{comment}\"",
            )
        except Exception:
            continue


@router.message(AppealFlow.waiting_comment)
async def process_comment_invalid(message: Message) -> None:
    await message.answer("❗️ Izohni matn ko'rinishida yozing:", reply_markup=cancel_inline_keyboard())
