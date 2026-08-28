"""IV.7-bo'lim: E'lon yuborish (broadcast).

outbox jadvali va APScheduler orqali navbatga qo'yish keyingi bosqichda
qo'shiladi; hozircha to'g'ridan-to'g'ri, lekin Telegram limitiga mos sekinlik
bilan (~25 msg/s) yuboriladi.
"""

import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.admin_test import yes_no_keyboard
from bot.keyboards.common import cancel_inline_keyboard
from bot.states.broadcast import Broadcast, MarketingLogo
from core.marketing import MARKETING_LOGO_KEY
from core.telegram_media import document_to_photo_file_id, is_image_document
from db.queries import list_all_user_telegram_ids, mark_user_blocked, set_setting

router = Router(name="admin_broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📢 E'lon yuborish")
async def start_broadcast(message: Message, state: FSMContext) -> None:
    await message.answer(
        "📢 Yuboriladigan matn yoki rasmni yuboring:", reply_markup=cancel_inline_keyboard()
    )
    await state.set_state(Broadcast.waiting_content)


@router.message(Broadcast.waiting_content, F.photo)
async def process_photo_content(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id, text=message.caption or "")
    await _show_preview(message, state)


@router.message(Broadcast.waiting_content, F.document)
async def process_document_content(message: Message, state: FSMContext) -> None:
    document = message.document
    if not await is_image_document(document):
        await message.answer(
            "❗️ Faqat rasm formatidagi fayl qabul qilinadi (PNG, JPG va h.k.). Qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return
    file_id = await document_to_photo_file_id(message, document)
    await state.update_data(photo_file_id=file_id, text=message.caption or "")
    await _show_preview(message, state)


@router.message(Broadcast.waiting_content, F.text)
async def process_text_content(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None, text=message.text)
    await _show_preview(message, state)


@router.message(Broadcast.waiting_content)
async def process_content_invalid(message: Message) -> None:
    await message.answer("❗️ Matn yoki rasm yuboring:", reply_markup=cancel_inline_keyboard())


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer("👁 Preview:")
    if data.get("photo_file_id"):
        await message.answer_photo(photo=data["photo_file_id"], caption=data.get("text") or None)
    else:
        await message.answer(data["text"])

    await message.answer(
        "Barcha foydalanuvchilarga yuborilsinmi?",
        reply_markup=yes_no_keyboard("broadcast:send", "broadcast:cancel"),
    )
    await state.set_state(Broadcast.waiting_confirm)


@router.callback_query(Broadcast.waiting_confirm, F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(Broadcast.waiting_confirm, F.data == "broadcast:send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("📤 Yuborilmoqda...")

    recipients = await list_all_user_telegram_ids(session)
    sent, blocked = 0, 0

    for user_pk, telegram_id in recipients:
        try:
            if data.get("photo_file_id"):
                await callback.bot.send_photo(
                    telegram_id, photo=data["photo_file_id"], caption=data.get("text") or None
                )
            else:
                await callback.bot.send_message(telegram_id, data["text"])
            sent += 1
        except TelegramForbiddenError:
            await mark_user_blocked(session, user_pk)
            blocked += 1
        except Exception:
            continue
        await asyncio.sleep(0.04)  # ~25 msg/s, Telegram limitiga mos

    await callback.message.answer(f"✅ {sent} yetdi, 🚫 {blocked} bloklagan")
    await callback.answer()


# ---------------- 🆕 Marketing rasm (yangi jonli test e'lonlari uchun) ----------------


@router.message(F.text == "🖼 Marketing rasm")
async def ask_marketing_logo(message: Message, state: FSMContext) -> None:
    await message.answer(
        "🖼 Yangi jonli test e'lonlarida ishlatiladigan rasmni (logotip) yuboring.\n"
        "Bu rasm har safar yangi jonli test yaratilganda barcha foydalanuvchilarga "
        "avtomatik ketadigan e'lon xabariga qo'yiladi.",
        reply_markup=cancel_inline_keyboard(),
    )
    await state.set_state(MarketingLogo.waiting_photo)


@router.message(MarketingLogo.waiting_photo, F.photo)
async def save_marketing_logo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    file_id = message.photo[-1].file_id
    await set_setting(session, MARKETING_LOGO_KEY, file_id)
    await state.clear()
    await message.answer("✅ Marketing rasmi saqlandi. Endi yangi jonli testlar shu rasm bilan e'lon qilinadi.")


@router.message(MarketingLogo.waiting_photo, F.document)
async def save_marketing_logo_document(message: Message, state: FSMContext, session: AsyncSession) -> None:
    document = message.document
    if not await is_image_document(document):
        await message.answer(
            "❗️ Faqat rasm formatidagi fayl qabul qilinadi (PNG, JPG va h.k.). Qayta yuboring:",
            reply_markup=cancel_inline_keyboard(),
        )
        return
    file_id = await document_to_photo_file_id(message, document)
    await set_setting(session, MARKETING_LOGO_KEY, file_id)
    await state.clear()
    await message.answer("✅ Marketing rasmi saqlandi. Endi yangi jonli testlar shu rasm bilan e'lon qilinadi.")


@router.message(MarketingLogo.waiting_photo)
async def save_marketing_logo_invalid(message: Message) -> None:
    await message.answer("❗️ Iltimos, rasm yuboring:", reply_markup=cancel_inline_keyboard())
