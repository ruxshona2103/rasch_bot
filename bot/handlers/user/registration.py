from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.registration import (
    channel_check_keyboard,
    contact_keyboard,
    region_keyboard,
    remove_keyboard,
)
from bot.states.registration import Registration
from core.channel import is_subscribed
from db.queries import create_user, get_user_by_telegram_id

router = Router(name="registration")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user:
        await message.answer(
            f"Xush kelibsiz, {user.full_name}!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "Assalomu alaykum! Milliy sertifikat mock-test botiga xush kelibsiz.\n"
        "Ism-familiyangizni kiriting:",
        reply_markup=remove_keyboard(),
    )
    await state.set_state(Registration.waiting_full_name)


@router.message(Registration.waiting_full_name, F.text)
async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3 or len(full_name) > 120:
        await message.answer("Ism-familiyangizni to'liq kiriting (masalan: Aliyev Vali):")
        return

    await state.update_data(full_name=full_name)
    await message.answer(
        "Telefon raqamingizni yuboring:",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(Registration.waiting_phone)


@router.message(Registration.waiting_full_name)
async def process_full_name_invalid(message: Message) -> None:
    await message.answer("Iltimos, ism-familiyangizni matn ko'rinishida kiriting:")


@router.message(Registration.waiting_phone, F.contact)
async def process_phone(message: Message, state: FSMContext) -> None:
    contact = message.contact
    # Soxtalashga qarshi: faqat o'z raqamini ulashgan bo'lishi shart
    if contact.user_id != message.from_user.id:
        await message.answer(
            "⚠️ Iltimos, boshqa birovning emas, o'zingizning raqamingizni ulashing.",
            reply_markup=contact_keyboard(),
        )
        return

    await state.update_data(phone=contact.phone_number)
    await message.answer(
        "Viloyatingizni tanlang:",
        reply_markup=region_keyboard(),
    )
    await state.set_state(Registration.waiting_region)


@router.message(Registration.waiting_phone)
async def process_phone_invalid(message: Message) -> None:
    await message.answer(
        "❗️ Qo'lda yozilgan raqam qabul qilinmaydi.\n"
        "Iltimos, pastdagi tugma orqali raqamingizni ulashing:",
        reply_markup=contact_keyboard(),
    )


@router.callback_query(Registration.waiting_region, F.data.startswith("region:"))
async def process_region(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    region = callback.data.split(":", 1)[1]
    await state.update_data(region=region)
    await callback.message.edit_reply_markup(reply_markup=None)

    if await is_subscribed(bot, callback.from_user.id):
        await _finish_registration(callback.message, state, session, callback.from_user.id)
    else:
        await callback.message.answer(
            "📢 Davom etish uchun kanalimizga a'zo bo'ling:",
            reply_markup=channel_check_keyboard(),
        )
        await state.set_state(Registration.waiting_channel_check)

    await callback.answer()


@router.callback_query(Registration.waiting_channel_check, F.data == "check_subscription")
async def process_channel_check(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if await is_subscribed(bot, callback.from_user.id):
        await _finish_registration(callback.message, state, session, callback.from_user.id)
    else:
        await callback.answer("❌ Hali kanalga a'zo emassiz.", show_alert=True)


async def _finish_registration(
    message: Message, state: FSMContext, session: AsyncSession, telegram_id: int
) -> None:
    data = await state.get_data()
    await create_user(
        session,
        telegram_id=telegram_id,
        full_name=data["full_name"],
        phone=data["phone"],
        region=data.get("region"),
    )
    await state.clear()
    await message.answer(
        "✅ Ro'yxatdan o'tdingiz!\n"
        "ℹ️ Unikal ID birinchi to'lovingiz tasdiqlangach beriladi.",
        reply_markup=main_menu_keyboard(),
    )
