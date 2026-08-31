"""Test yaratish — IV.2-bo'lim: PDF usuli (asosiy) va qo'lda kiritish (zaxira).

PDF usuli: admin PDF yuboradi (1 sahifa = 1 savol) -> PyMuPDF PNG'ga aylantiradi
-> kalit matnini parse qiladi -> har savol DB'ga yoziladi.

Qo'lda kiritish: har savol birma-bir so'raladi (turi -> kontent -> to'g'ri javob).
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.admin import admin_panel_keyboard
from bot.keyboards.common import back_cancel_keyboard, cancel_inline_keyboard
from bot.keyboards.admin_test import (
    manual_closed_answer_keyboard,
    manual_next_keyboard,
    manual_qtype_keyboard,
    method_keyboard,
    mode_keyboard,
    price_keyboard,
    yes_no_keyboard,
)
from bot.keyboards.test_manage import test_actions_keyboard
from bot.states.admin_test import TestCreate
from core.answer_key import parse_answer_key, qtype_for_answer
from core.marketing import announce_new_test
from core.pdf_parser import pdf_to_png_pages
from core.telegram_media import document_to_photo_file_id, is_image_document
from core.storage import save_question_png, test_media_dir
from db.models import Question, Test
from db.queries import add_question, count_questions, create_test, get_test

router = Router(name="admin_test_create")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ---------- 1) Nomi -> 2) Savollar soni -> 3) Davomiylik -> 4) Narx ----------

@router.message(F.text == "➕ Yangi test")
async def start_test_creation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "1️⃣ Test nomini kiriting (masalan: Mock #5 — Matematika):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(TestCreate.waiting_title)


@router.message(TestCreate.waiting_title, F.text)
async def process_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await message.answer(
        "2️⃣ Yopiq savollar soni (A/B/C/D), masalan: 35",
        reply_markup=back_cancel_keyboard("tcback:title"),
    )
    await state.set_state(TestCreate.waiting_closed_count)


@router.message(TestCreate.waiting_closed_count, F.text.regexp(r"^\d+$"))
async def process_closed_count(message: Message, state: FSMContext) -> None:
    await state.update_data(closed_count=int(message.text))
    await message.answer(
        "Ochiq savollar soni (raqamli javob), masalan: 10",
        reply_markup=back_cancel_keyboard("tcback:closed_count"),
    )
    await state.set_state(TestCreate.waiting_open_count)


@router.message(TestCreate.waiting_closed_count)
async def process_closed_count_invalid(message: Message) -> None:
    await message.answer(
        "Iltimos, faqat raqam kiriting:", reply_markup=back_cancel_keyboard("tcback:title")
    )


@router.message(TestCreate.waiting_open_count, F.text.regexp(r"^\d+$"))
async def process_open_count(message: Message, state: FSMContext) -> None:
    await state.update_data(open_count=int(message.text))
    await message.answer(
        "3️⃣ Test davomiyligi (daqiqada), masalan: 120",
        reply_markup=back_cancel_keyboard("tcback:open_count"),
    )
    await state.set_state(TestCreate.waiting_duration)


@router.message(TestCreate.waiting_open_count)
async def process_open_count_invalid(message: Message) -> None:
    await message.answer(
        "Iltimos, faqat raqam kiriting:", reply_markup=back_cancel_keyboard("tcback:closed_count")
    )


@router.message(TestCreate.waiting_duration, F.text.regexp(r"^\d+$"))
async def process_duration(message: Message, state: FSMContext) -> None:
    await state.update_data(duration_min=int(message.text))
    await message.answer("4️⃣ 💰 Narxni kiriting (so'mda), masalan: 15000", reply_markup=price_keyboard())
    await state.set_state(TestCreate.waiting_price)


@router.message(TestCreate.waiting_duration)
async def process_duration_invalid(message: Message) -> None:
    await message.answer(
        "Iltimos, faqat raqam kiriting (daqiqa):",
        reply_markup=back_cancel_keyboard("tcback:open_count"),
    )


@router.message(TestCreate.waiting_price, F.text.regexp(r"^\d+$"))
async def process_price(message: Message, state: FSMContext) -> None:
    await state.update_data(price=int(message.text))
    await message.answer("5️⃣ Rejimni tanlang:", reply_markup=mode_keyboard())
    await state.set_state(TestCreate.waiting_mode)


@router.message(TestCreate.waiting_price)
async def process_price_invalid(message: Message) -> None:
    await message.answer("Iltimos, faqat raqam kiriting (narx, so'm):", reply_markup=price_keyboard())


@router.callback_query(TestCreate.waiting_price, F.data == "tcprice:free")
async def process_price_free(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(price=0)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🆓 Test BEPUL qilib belgilandi.\n5️⃣ Rejimni tanlang:", reply_markup=mode_keyboard())
    await state.set_state(TestCreate.waiting_mode)
    await callback.answer()


# ---------- ⬅️ Orqaga (faqat shu qadamni bekor qilib, oldingi so'rovga qaytaradi) ----------

@router.callback_query(F.data == "tcback:title")
async def back_to_title(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "1️⃣ Test nomini kiriting (masalan: Mock #5 — Matematika):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(TestCreate.waiting_title)
    await callback.answer()


@router.callback_query(F.data == "tcback:closed_count")
async def back_to_closed_count(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "2️⃣ Yopiq savollar soni (A/B/C/D), masalan: 35",
        reply_markup=back_cancel_keyboard("tcback:title"),
    )
    await state.set_state(TestCreate.waiting_closed_count)
    await callback.answer()


@router.callback_query(F.data == "tcback:open_count")
async def back_to_open_count(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Ochiq savollar soni (raqamli javob), masalan: 10",
        reply_markup=back_cancel_keyboard("tcback:closed_count"),
    )
    await state.set_state(TestCreate.waiting_open_count)
    await callback.answer()


@router.callback_query(F.data == "tcback:duration")
async def back_to_duration(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "3️⃣ Test davomiyligi (daqiqada), masalan: 120",
        reply_markup=back_cancel_keyboard("tcback:open_count"),
    )
    await state.set_state(TestCreate.waiting_duration)
    await callback.answer()


# ---------- 5) Rejim ----------
# 🆕 Jonli test uchun vaqt endi test yaratishda SO'RALMAYDI — admin
# "📋 Testlar" ro'yxatidan "▶️ Boshlash" / "🏁 Yakunlash" tugmalari orqali
# testni xohlagan payt qo'lda boshlaydi va yakunlaydi (test_manage.py).

@router.callback_query(TestCreate.waiting_mode, F.data.startswith("mode:"))
async def process_mode(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    mode = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    if mode == "jonli":
        test = await create_test(
            session,
            title=data["title"],
            price=data["price"],
            duration_min=data["duration_min"],
            mode="jonli",
            start_at=None,
            deadline_at=None,
            status="tayyorlanmoqda",
        )
    else:
        test = await create_test(
            session,
            title=data["title"],
            price=data["price"],
            duration_min=data["duration_min"],
            mode="arxiv",
            start_at=None,
            deadline_at=None,
            status="arxivda",
        )

    await state.update_data(test_id=test.test_id, mode=mode)
    await callback.message.answer("6️⃣ Savollarni qanday kiritamiz?", reply_markup=method_keyboard())
    await state.set_state(TestCreate.waiting_method)
    await callback.answer()


# ---------- 6) Usul tanlash ----------

@router.callback_query(TestCreate.waiting_method, F.data.startswith("method:"))
async def process_method(callback: CallbackQuery, state: FSMContext) -> None:
    method = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)

    if method == "pdf":
        await callback.message.answer(
            "📄 PDF yuboring.\n⚠️ QOIDA: 1 savol = 1 sahifa!",
            reply_markup=cancel_inline_keyboard(),
        )
        await state.set_state(TestCreate.waiting_pdf)
    else:
        await state.update_data(manual_order=1)
        await callback.message.answer(
            "1-savol turi:", reply_markup=manual_qtype_keyboard()
        )
        await state.set_state(TestCreate.waiting_manual_qtype)

    await callback.answer()


# ================= PDF USULI =================

@router.message(TestCreate.waiting_pdf, F.document)
async def process_pdf(message: Message, state: FSMContext) -> None:
    document = message.document
    if not (document.file_name or "").lower().endswith(".pdf"):
        await message.answer("❗️ Faqat PDF fayl qabul qilinadi. Qayta yuboring:")
        return

    file_bytes_io = await message.bot.download(document)
    pdf_bytes = file_bytes_io.read()

    try:
        pages = pdf_to_png_pages(pdf_bytes)
    except Exception:
        await message.answer("❗️ PDF o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin, qayta yuboring:")
        return

    data = await state.get_data()
    test_id = data["test_id"]
    expected = data["closed_count"] + data["open_count"]

    for order_num, png_bytes in enumerate(pages, start=1):
        save_question_png(test_id, order_num, png_bytes)

    await state.update_data(pdf_page_count=len(pages))

    warn = ""
    if len(pages) != expected:
        warn = (
            f"\n⚠️ Kutilgan savollar soni {expected} edi, lekin PDF'da {len(pages)} "
            f"sahifa topildi. Baribir shu son bilan davom etamizmi?"
        )

    await message.answer(
        f"✅ {len(pages)} sahifa topildi.{warn}\n{len(pages)} savol sifatida saqlaymi?",
        reply_markup=yes_no_keyboard("pdfconfirm:yes", "pdfconfirm:no"),
    )
    await state.set_state(TestCreate.waiting_pdf_confirm)


@router.message(TestCreate.waiting_pdf)
async def process_pdf_invalid(message: Message) -> None:
    await message.answer(
        "❗️ Iltimos, PDF faylni hujjat (document) sifatida yuboring:",
        reply_markup=cancel_inline_keyboard(),
    )


@router.callback_query(TestCreate.waiting_pdf_confirm, F.data == "pdfconfirm:no")
async def pdf_confirm_no(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("📄 Yangi PDF yuboring:")
    await state.set_state(TestCreate.waiting_pdf)
    await callback.answer()


@router.callback_query(TestCreate.waiting_pdf_confirm, F.data == "pdfconfirm:yes")
async def pdf_confirm_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🔑 Endi kalitni yuboring.\n"
        "Format: 1-A 2-C 3-B ... 35-D 36:12 37:-4.5 38:0.5|1/2 ... 45:7",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(TestCreate.waiting_key)
    await callback.answer()


@router.message(TestCreate.waiting_key, F.text)
async def process_key(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["test_id"]
    page_count = data["pdf_page_count"]

    key_map = parse_answer_key(message.text)
    missing = [n for n in range(1, page_count + 1) if n not in key_map]
    if missing:
        await message.answer(
            f"❗️ Quyidagi savollar uchun kalit topilmadi: {', '.join(map(str, missing))}\n"
            "Kalitni to'liq qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return

    directory = test_media_dir(test_id)
    for order_num in range(1, page_count + 1):
        answer = key_map[order_num]
        png_path = directory / f"{order_num}.png"
        photo_msg = await message.answer_photo(
            photo=BufferedInputFile(png_path.read_bytes(), filename=f"{order_num}.png"),
            caption=f"{order_num}/{page_count}",
        )
        file_id = photo_msg.photo[-1].file_id
        await add_question(
            session,
            test_id=test_id,
            order_num=order_num,
            qtype=qtype_for_answer(answer),
            correct_answer=answer,
            image_file_id=file_id,
        )

    await message.answer(
        f"✅ {page_count}/{page_count} javob topildi va saqlandi.",
        reply_markup=yes_no_keyboard("finalconfirm:yes", "finalconfirm:no"),
    )
    await state.set_state(TestCreate.waiting_final_confirm)


# ================= QO'LDA KIRITISH USULI =================

@router.callback_query(TestCreate.waiting_manual_qtype, F.data.startswith("qtype:"))
async def manual_process_qtype(callback: CallbackQuery, state: FSMContext) -> None:
    qtype = callback.data.split(":", 1)[1]
    await state.update_data(current_qtype=qtype)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Savol matnini yoki rasmini yuboring (rasmni ham 📷 photo, ham 📎 file "
        "sifatida — istalgan formatda: PNG, JPG va h.k. — yuborishingiz mumkin):",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(TestCreate.waiting_manual_content)
    await callback.answer()


@router.message(TestCreate.waiting_manual_content, F.photo)
async def manual_process_content_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(current_text=None, current_image_file_id=message.photo[-1].file_id)
    await _after_content(message, state)


@router.message(TestCreate.waiting_manual_content, F.document)
async def manual_process_content_document(message: Message, state: FSMContext) -> None:
    document = message.document
    if not await is_image_document(document):
        await message.answer(
            "❗️ Faqat rasm formatidagi fayl qabul qilinadi (PNG, JPG va h.k.). Qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return

    file_id = await document_to_photo_file_id(message, document)
    await state.update_data(current_text=None, current_image_file_id=file_id)
    await _after_content(message, state)


@router.message(TestCreate.waiting_manual_content, F.text)
async def manual_process_content_text(message: Message, state: FSMContext) -> None:
    await state.update_data(current_text=message.text.strip(), current_image_file_id=None)
    await _after_content(message, state)


@router.message(TestCreate.waiting_manual_content)
async def manual_process_content_invalid(message: Message) -> None:
    await message.answer(
        "❗️ Matn yoki rasm (photo yoki file) yuboring:", reply_markup=cancel_inline_keyboard()
    )


async def _after_content(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["current_qtype"] == "yopiq":
        await message.answer(
            "Endi javob variantlarini kiriting, masalan:\nA) 24\nB) 36\nC) 12\nD) 8",
            reply_markup=cancel_inline_keyboard(),
        )
        await state.set_state(TestCreate.waiting_manual_options)
    else:
        await _ask_manual_answer(message, state)


@router.message(TestCreate.waiting_manual_options, F.text)
async def manual_process_options(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    options_text = message.text.strip()
    existing_text = data.get("current_text")
    combined_text = f"{existing_text}\n\n{options_text}" if existing_text else options_text
    await state.update_data(current_text=combined_text)
    await _ask_manual_answer(message, state)


@router.message(TestCreate.waiting_manual_options)
async def manual_process_options_invalid(message: Message) -> None:
    await message.answer(
        "❗️ Variantlarni matn ko'rinishida kiriting (masalan: A) 24  B) 36  C) 12  D) 8):",
        reply_markup=cancel_inline_keyboard(),
    )


async def _ask_manual_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data["current_qtype"] == "yopiq":
        await message.answer("To'g'ri javobni tanlang:", reply_markup=manual_closed_answer_keyboard())
    else:
        await message.answer(
            "To'g'ri javobni raqamda yozing (masalan: 12 yoki 0.5|1/2):",
            reply_markup=cancel_inline_keyboard(),
        )
    await state.set_state(TestCreate.waiting_manual_answer)


@router.callback_query(TestCreate.waiting_manual_answer, F.data.startswith("answer:"))
async def manual_process_answer_closed(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    answer = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_manual_question(callback.message, state, session, answer)
    await callback.answer()


@router.message(TestCreate.waiting_manual_answer, F.text)
async def manual_process_answer_open(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    from core.answer_key import normalize_open_answer

    answer = "|".join(normalize_open_answer(part) for part in message.text.split("|"))
    await _save_manual_question(message, state, session, answer)


async def _save_manual_question(
    message: Message, state: FSMContext, session: AsyncSession, answer: str
) -> None:
    data = await state.get_data()
    order_num = data["manual_order"]
    await add_question(
        session,
        test_id=data["test_id"],
        order_num=order_num,
        qtype=data["current_qtype"],
        correct_answer=answer,
        text=data.get("current_text"),
        image_file_id=data.get("current_image_file_id"),
    )
    await state.update_data(manual_order=order_num + 1)
    await message.answer(
        f"✅ {order_num}-savol saqlandi.", reply_markup=manual_next_keyboard()
    )
    await state.set_state(TestCreate.waiting_manual_next)


@router.callback_query(TestCreate.waiting_manual_next, F.data == "manual:more")
async def manual_add_more(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"{data['manual_order']}-savol turi:", reply_markup=manual_qtype_keyboard()
    )
    await state.set_state(TestCreate.waiting_manual_qtype)
    await callback.answer()


@router.callback_query(TestCreate.waiting_manual_next, F.data == "manual:finish")
async def manual_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    total = await count_questions(session, data["test_id"])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Jami {total} savol saqlandi.",
        reply_markup=yes_no_keyboard("finalconfirm:yes", "finalconfirm:no"),
    )
    await state.set_state(TestCreate.waiting_final_confirm)
    await callback.answer()


# ================= YAKUNIY TASDIQLASH =================

@router.callback_query(TestCreate.waiting_final_confirm, F.data == "finalconfirm:yes")
async def final_confirm_yes(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"🎉 Test tayyor! (test_id={data['test_id']})")

    if data.get("mode") == "jonli":
        test = await get_test(session, data["test_id"])
        await callback.message.answer(
            "Testni qachon boshlaymiz?", reply_markup=test_actions_keyboard(test)
        )

        question_count = await count_questions(session, data["test_id"])
        await callback.message.answer("📢 Barcha foydalanuvchilarga e'lon yuborilmoqda...")
        sent, blocked = await announce_new_test(callback.bot, session, test, question_count)
        await callback.message.answer(f"✅ E'lon {sent} kishiga yetdi, 🚫 {blocked} bloklagan.")

    await callback.message.answer("👨‍💼 Admin panel:", reply_markup=admin_panel_keyboard())
    await state.clear()
    await callback.answer()


@router.callback_query(TestCreate.waiting_final_confirm, F.data == "finalconfirm:no")
async def final_confirm_no(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["test_id"]
    await session.execute(delete(Question).where(Question.test_id == test_id))
    await session.execute(delete(Test).where(Test.test_id == test_id))
    await session.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "❌ Test bekor qilindi va o'chirildi.", reply_markup=admin_panel_keyboard()
    )
    await state.clear()
    await callback.answer()
