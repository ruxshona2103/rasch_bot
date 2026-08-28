"""🆕 Testga savol qo'shish / mavjud savolni o'zgartirish / o'chirish.

Har qanday test uchun ishlaydi (jonli_davom/hisoblanmoqda'dan tashqari) —
jumladan ARXIVDAGI testlar uchun ham (faqat yangi/tayyor testlar emas).
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.admin_test import manual_closed_answer_keyboard, manual_qtype_keyboard
from bot.keyboards.common import cancel_inline_keyboard
from bot.keyboards.question_edit import edit_menu_keyboard
from bot.keyboards.test_manage import test_actions_keyboard
from bot.states.question_edit import QuestionEdit
from core.answer_key import normalize_open_answer
from core.telegram_media import document_to_photo_file_id, is_image_document
from db.queries import (
    add_question,
    count_questions,
    delete_question_and_renumber,
    get_questions_for_test,
    get_test,
    update_question,
)

router = Router(name="admin_question_edit")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data.startswith("testedit:"))
async def open_edit_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[1])
    total = await count_questions(session, test_id)
    await callback.message.answer(
        f"✏️ Savollarni tahrirlash — jami {total} ta savol.",
        reply_markup=edit_menu_keyboard(test_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qedit:back:"))
async def back_to_test(callback: CallbackQuery, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[2])
    test = await get_test(session, test_id)
    await callback.message.answer("👨‍💼 Testlar boshqaruviga qaytdingiz.", reply_markup=test_actions_keyboard(test))
    await callback.answer()


# ================= Savol qo'shish =================


@router.callback_query(F.data.startswith("qedit:add:"))
async def start_add_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[2])
    total = await count_questions(session, test_id)
    await state.update_data(edit_test_id=test_id, edit_order=total + 1)
    await callback.message.answer(f"{total + 1}-savol turi:", reply_markup=manual_qtype_keyboard())
    await state.set_state(QuestionEdit.waiting_add_qtype)
    await callback.answer()


@router.callback_query(QuestionEdit.waiting_add_qtype, F.data.startswith("qtype:"))
async def add_process_qtype(callback: CallbackQuery, state: FSMContext) -> None:
    qtype = callback.data.split(":", 1)[1]
    await state.update_data(edit_qtype=qtype)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Savol matnini yoki rasmini yuboring (photo yoki file):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(QuestionEdit.waiting_add_content)
    await callback.answer()


@router.message(QuestionEdit.waiting_add_content, F.photo)
async def add_content_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(edit_text=None, edit_image_file_id=message.photo[-1].file_id)
    await _after_add_content(message, state)


@router.message(QuestionEdit.waiting_add_content, F.document)
async def add_content_document(message: Message, state: FSMContext) -> None:
    document = message.document
    if not await is_image_document(document):
        await message.answer(
            "❗️ Faqat rasm formatidagi fayl qabul qilinadi. Qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return
    file_id = await document_to_photo_file_id(message, document)
    await state.update_data(edit_text=None, edit_image_file_id=file_id)
    await _after_add_content(message, state)


@router.message(QuestionEdit.waiting_add_content, F.text)
async def add_content_text(message: Message, state: FSMContext) -> None:
    await state.update_data(edit_text=message.text.strip(), edit_image_file_id=None)
    await _after_add_content(message, state)


@router.message(QuestionEdit.waiting_add_content)
async def add_content_invalid(message: Message) -> None:
    await message.answer("❗️ Matn yoki rasm yuboring:", reply_markup=cancel_inline_keyboard())


async def _after_add_content(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["edit_qtype"] == "yopiq":
        await message.answer(
            "Javob variantlarini kiriting, masalan:\nA) 24\nB) 36\nC) 12\nD) 8",
            reply_markup=cancel_inline_keyboard(),
        )
        await state.set_state(QuestionEdit.waiting_add_options)
    else:
        await _ask_add_answer(message, state)


@router.message(QuestionEdit.waiting_add_options, F.text)
async def add_process_options(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    combined = _combine_text(data.get("edit_text"), message.text.strip())
    await state.update_data(edit_text=combined)
    await _ask_add_answer(message, state)


@router.message(QuestionEdit.waiting_add_options)
async def add_options_invalid(message: Message) -> None:
    await message.answer("❗️ Variantlarni matn ko'rinishida kiriting:", reply_markup=cancel_inline_keyboard())


async def _ask_add_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["edit_qtype"] == "yopiq":
        await message.answer("To'g'ri javobni tanlang:", reply_markup=manual_closed_answer_keyboard())
    else:
        await message.answer(
            "To'g'ri javobni raqamda yozing (masalan: 12 yoki 0.5|1/2):",
            reply_markup=cancel_inline_keyboard(),
        )
    await state.set_state(QuestionEdit.waiting_add_answer)


@router.callback_query(QuestionEdit.waiting_add_answer, F.data.startswith("answer:"))
async def add_answer_closed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    answer = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_added_question(callback.message, state, session, answer)
    await callback.answer()


@router.message(QuestionEdit.waiting_add_answer, F.text)
async def add_answer_open(message: Message, state: FSMContext, session: AsyncSession) -> None:
    answer = "|".join(normalize_open_answer(part) for part in message.text.split("|"))
    await _save_added_question(message, state, session, answer)


async def _save_added_question(message: Message, state: FSMContext, session: AsyncSession, answer: str) -> None:
    data = await state.get_data()
    await add_question(
        session,
        test_id=data["edit_test_id"],
        order_num=data["edit_order"],
        qtype=data["edit_qtype"],
        correct_answer=answer,
        text=data.get("edit_text"),
        image_file_id=data.get("edit_image_file_id"),
    )
    test_id = data["edit_test_id"]
    order = data["edit_order"]
    await state.clear()
    await message.answer(f"✅ {order}-savol qo'shildi.", reply_markup=edit_menu_keyboard(test_id))


# ================= Savolni o'chirish =================


@router.callback_query(F.data.startswith("qedit:delete:"))
async def start_delete_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[2])
    total = await count_questions(session, test_id)
    if total == 0:
        await callback.answer("Bu testda savol yo'q.", show_alert=True)
        return
    await state.update_data(edit_test_id=test_id)
    await callback.message.answer(
        f"Nechinchi savolni o'chiramiz? (1-{total}):", reply_markup=cancel_inline_keyboard()
    )
    await state.set_state(QuestionEdit.waiting_delete_number)
    await callback.answer()


@router.message(QuestionEdit.waiting_delete_number, F.text.regexp(r"^\d+$"))
async def process_delete_number(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["edit_test_id"]
    order_num = int(message.text)
    total = await count_questions(session, test_id)
    if not (1 <= order_num <= total):
        await message.answer(f"❗️ 1 dan {total} gacha raqam kiriting:", reply_markup=cancel_inline_keyboard())
        return

    deleted = await delete_question_and_renumber(session, test_id, order_num)
    await state.clear()
    if deleted:
        new_total = await count_questions(session, test_id)
        await message.answer(
            f"🗑 {order_num}-savol o'chirildi. Endi jami {new_total} ta savol.",
            reply_markup=edit_menu_keyboard(test_id),
        )
    else:
        await message.answer("⚠️ Savol topilmadi.", reply_markup=edit_menu_keyboard(test_id))


@router.message(QuestionEdit.waiting_delete_number)
async def process_delete_number_invalid(message: Message) -> None:
    await message.answer("❗️ Faqat raqam kiriting:", reply_markup=cancel_inline_keyboard())


# ================= Savolni o'zgartirish =================


@router.callback_query(F.data.startswith("qedit:edit:"))
async def start_edit_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[2])
    total = await count_questions(session, test_id)
    if total == 0:
        await callback.answer("Bu testda savol yo'q.", show_alert=True)
        return
    await state.update_data(edit_test_id=test_id)
    await callback.message.answer(
        f"Nechinchi savolni o'zgartiramiz? (1-{total}):", reply_markup=cancel_inline_keyboard()
    )
    await state.set_state(QuestionEdit.waiting_edit_number)
    await callback.answer()


@router.message(QuestionEdit.waiting_edit_number, F.text.regexp(r"^\d+$"))
async def process_edit_number(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["edit_test_id"]
    order_num = int(message.text)
    total = await count_questions(session, test_id)
    if not (1 <= order_num <= total):
        await message.answer(f"❗️ 1 dan {total} gacha raqam kiriting:", reply_markup=cancel_inline_keyboard())
        return

    questions = await get_questions_for_test(session, test_id)
    question = questions[order_num - 1]
    await state.update_data(edit_question_id=question.question_id, edit_order=order_num)
    await message.answer(f"{order_num}-savol turi:", reply_markup=manual_qtype_keyboard())
    await state.set_state(QuestionEdit.waiting_edit_qtype)


@router.message(QuestionEdit.waiting_edit_number)
async def process_edit_number_invalid(message: Message) -> None:
    await message.answer("❗️ Faqat raqam kiriting:", reply_markup=cancel_inline_keyboard())


@router.callback_query(QuestionEdit.waiting_edit_qtype, F.data.startswith("qtype:"))
async def edit_process_qtype(callback: CallbackQuery, state: FSMContext) -> None:
    qtype = callback.data.split(":", 1)[1]
    await state.update_data(edit_qtype=qtype)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Yangi savol matnini yoki rasmini yuboring (photo yoki file):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(QuestionEdit.waiting_edit_content)
    await callback.answer()


@router.message(QuestionEdit.waiting_edit_content, F.photo)
async def edit_content_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(edit_text=None, edit_image_file_id=message.photo[-1].file_id)
    await _after_edit_content(message, state)


@router.message(QuestionEdit.waiting_edit_content, F.document)
async def edit_content_document(message: Message, state: FSMContext) -> None:
    document = message.document
    if not await is_image_document(document):
        await message.answer(
            "❗️ Faqat rasm formatidagi fayl qabul qilinadi. Qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return
    file_id = await document_to_photo_file_id(message, document)
    await state.update_data(edit_text=None, edit_image_file_id=file_id)
    await _after_edit_content(message, state)


@router.message(QuestionEdit.waiting_edit_content, F.text)
async def edit_content_text(message: Message, state: FSMContext) -> None:
    await state.update_data(edit_text=message.text.strip(), edit_image_file_id=None)
    await _after_edit_content(message, state)


@router.message(QuestionEdit.waiting_edit_content)
async def edit_content_invalid(message: Message) -> None:
    await message.answer("❗️ Matn yoki rasm yuboring:", reply_markup=cancel_inline_keyboard())


async def _after_edit_content(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["edit_qtype"] == "yopiq":
        await message.answer(
            "Javob variantlarini kiriting, masalan:\nA) 24\nB) 36\nC) 12\nD) 8",
            reply_markup=cancel_inline_keyboard(),
        )
        await state.set_state(QuestionEdit.waiting_edit_options)
    else:
        await _ask_edit_answer(message, state)


@router.message(QuestionEdit.waiting_edit_options, F.text)
async def edit_process_options(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    combined = _combine_text(data.get("edit_text"), message.text.strip())
    await state.update_data(edit_text=combined)
    await _ask_edit_answer(message, state)


@router.message(QuestionEdit.waiting_edit_options)
async def edit_options_invalid(message: Message) -> None:
    await message.answer("❗️ Variantlarni matn ko'rinishida kiriting:", reply_markup=cancel_inline_keyboard())


async def _ask_edit_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["edit_qtype"] == "yopiq":
        await message.answer("To'g'ri javobni tanlang:", reply_markup=manual_closed_answer_keyboard())
    else:
        await message.answer(
            "To'g'ri javobni raqamda yozing (masalan: 12 yoki 0.5|1/2):",
            reply_markup=cancel_inline_keyboard(),
        )
    await state.set_state(QuestionEdit.waiting_edit_answer)


@router.callback_query(QuestionEdit.waiting_edit_answer, F.data.startswith("answer:"))
async def edit_answer_closed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    answer = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_edited_question(callback.message, state, session, answer)
    await callback.answer()


@router.message(QuestionEdit.waiting_edit_answer, F.text)
async def edit_answer_open(message: Message, state: FSMContext, session: AsyncSession) -> None:
    answer = "|".join(normalize_open_answer(part) for part in message.text.split("|"))
    await _save_edited_question(message, state, session, answer)


async def _save_edited_question(message: Message, state: FSMContext, session: AsyncSession, answer: str) -> None:
    data = await state.get_data()
    await update_question(
        session,
        question_id=data["edit_question_id"],
        qtype=data["edit_qtype"],
        correct_answer=answer,
        text=data.get("edit_text"),
        image_file_id=data.get("edit_image_file_id"),
    )
    test_id = data["edit_test_id"]
    order = data["edit_order"]
    await state.clear()
    await message.answer(f"✅ {order}-savol yangilandi.", reply_markup=edit_menu_keyboard(test_id))


def _combine_text(existing: str | None, addition: str) -> str:
    return f"{existing}\n\n{addition}" if existing else addition
