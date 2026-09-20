"""Admin panel kirish nuqtasi (IV.1-bo'lim).

Hozircha faqat panel ochiladi va tugmalar "tez orada" javob beradi —
har biri (test yaratish, to'lovlar, apellyatsiyalar, statistika, broadcast)
navbat bilan to'liq handlerga almashtiriladi.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.filters.admin import IsAdmin
from bot.keyboards.admin import admin_panel_keyboard
from bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="admin_panel")
router.message.filter(IsAdmin())


@router.callback_query(F.data == "flow:cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    if callback.from_user.id in settings.admin_ids:
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=admin_panel_keyboard())
    else:
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard())
    await callback.answer()

@router.message(Command("admin"))
async def open_admin_panel(message: Message) -> None:
    await message.answer(
        "👨‍💼 ADMIN PANEL",
        reply_markup=admin_panel_keyboard(),
    )


@router.message(F.text == "⬅️ Foydalanuvchi rejimiga qaytish")
async def back_to_user_mode(message: Message) -> None:
    await message.answer(
        "Foydalanuvchi rejimiga qaytdingiz.",
        reply_markup=main_menu_keyboard(),
    )
