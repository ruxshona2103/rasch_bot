"""III.3-bo'lim: test tanlash -> chek yuborish -> admin tasdiqlashini kutish."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards.payment import approve_reject_keyboard, enter_test_keyboard, pay_button_keyboard
from bot.states.payment import PaymentFlow
from db.queries import (
    create_payment,
    get_payment_by_receipt_hash,
    get_pending_payment,
    get_test,
    get_user_by_telegram_id,
    has_purchase,
    list_tests_by_mode,
)

router = Router(name="tests_list")


def _fmt_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


def _contact_line() -> str:
    parts = []
    if settings.ADMIN_CONTACT_USERNAME:
        parts.append(settings.ADMIN_CONTACT_USERNAME)
    if settings.ADMIN_PHONE:
        parts.append(settings.ADMIN_PHONE)
    if not parts:
        return ""
    return f"\n\n❓ Savollar yoki qo'shimcha ma'lumot uchun: {' | '.join(parts)}"


def _format_test_card(test) -> str:
    emoji = "🔴" if test.mode == "jonli" else "📚"
    if test.mode == "jonli":
        if test.start_at:
            local_start = test.start_at.astimezone(settings.tzinfo)
            schedule = f"📅 {local_start:%d-%m %H:%M}"
            if test.deadline_at:
                local_deadline = test.deadline_at.astimezone(settings.tzinfo)
                schedule += f"–{local_deadline:%H:%M}"
        elif test.status == "jonli_davom":
            schedule = "🔴 Hozir jonli efirda"
        else:
            schedule = "⏳ Boshlanish vaqti tez orada e'lon qilinadi"
    else:
        schedule = "📚 Istalgan vaqtda"
    return f"{emoji} {test.title}\n{schedule} | 💰 {_fmt_price(test.price)}"


@router.message(F.text == "🔴 Jonli testlar")
async def list_live_tests(message: Message, session: AsyncSession) -> None:
    await _list_tests(message, session, mode="jonli")


@router.message(F.text == "📚 Arxiv testlar")
async def list_archive_tests(message: Message, session: AsyncSession) -> None:
    await _list_tests(message, session, mode="arxiv")


async def _list_tests(message: Message, session: AsyncSession, mode: str) -> None:
    tests = [t for t in await list_tests_by_mode(session, mode) if t.status != "bekor_qilingan"]
    if not tests:
        label = "jonli" if mode == "jonli" else "arxiv"
        await message.answer(f"Hozircha {label} testlar yo'q.")
        return

    user = await get_user_by_telegram_id(session, message.from_user.id)

    for test in tests:
        card = _format_test_card(test)
        if await has_purchase(session, user.user_pk, test.test_id):
            if test.mode == "arxiv" or test.status == "jonli_davom":
                await message.answer(
                    f"{card}\n✅ Kirish huquqingiz bor",
                    reply_markup=enter_test_keyboard(test.test_id),
                )
            elif test.status in ("hisoblanmoqda", "yakunlangan"):
                await message.answer(f"{card}\n✅ Yakunlangan — natijalar tez orada.")
            else:
                await message.answer(
                    f"{card}\n✅ Kirish huquqingiz bor\n⏳ Hali boshlanmagan — boshlansa xabar beramiz."
                )
        else:
            await message.answer(card, reply_markup=pay_button_keyboard(test.test_id))


@router.callback_query(F.data.startswith("pay:start:"))
async def start_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    test_id = int(callback.data.split(":")[2])
    test = await get_test(session, test_id)
    if test is None or test.status == "bekor_qilingan":
        await callback.answer("Bu test endi mavjud emas.", show_alert=True)
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if await has_purchase(session, user.user_pk, test_id):
        await callback.answer("Sizda bu testga kirish huquqi allaqachon bor.", show_alert=True)
        return

    if await get_pending_payment(session, user.user_pk, test_id):
        await callback.answer("⏳ Oldingi chekingiz hali tekshirilmoqda, iltimos kuting.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "💳 To'lov tartibi:\n"
        f"1️⃣ {settings.CARD_NUMBER} ({settings.CARD_OWNER}) kartasiga {_fmt_price(test.price)} o'tkazing\n"
        "2️⃣ Chek (skrinshot) rasmini SHU YERGA yuboring\n"
        "⏳ Admin 30 daqiqa ichida tekshiradi"
    )
    await state.update_data(test_id=test_id)
    await state.set_state(PaymentFlow.waiting_receipt)
    await callback.answer()


@router.message(PaymentFlow.waiting_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    test_id = data["test_id"]
    test = await get_test(session, test_id)
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if await get_pending_payment(session, user.user_pk, test_id):
        await message.answer("⏳ Oldingi chekingiz hali tekshirilmoqda, iltimos kuting.")
        return

    receipt_file_id = message.photo[-1].file_id
    receipt_hash = message.photo[-1].file_unique_id
    duplicate = await get_payment_by_receipt_hash(session, receipt_hash)

    payment = await create_payment(
        session,
        user_pk=user.user_pk,
        test_id=test_id,
        receipt_file_id=receipt_file_id,
        receipt_hash=receipt_hash,
        amount=test.price,
    )

    await state.clear()
    await message.answer(
        "✅ Chekingiz qabul qilindi. Admin 30 daqiqa ichida tekshiradi." + _contact_line()
    )
    await _notify_admins(message, payment, user, test, duplicate)


@router.message(PaymentFlow.waiting_receipt)
async def process_receipt_invalid(message: Message) -> None:
    await message.answer("❗️ Iltimos, chek rasmini (skrinshot) yuboring:")



# 🆕 "▶️ Kirish" bosilganda ("examenter:") Exam Mode'ga o'tadi — bot/handlers/user/exam.py


async def _notify_admins(message: Message, payment, user, test, duplicate) -> None:
    is_first_payment = user.public_id is None
    caption = (
        f"🔔 YANGI TO'LOV #{payment.payment_id}\n"
        f"👤 {user.full_name} | 📱 {user.phone}\n"
        + ("🆕 Birinchi to'lov (ID yo'q)\n" if is_first_payment else f"🎫 ID: {user.public_id}\n")
        + f"🧪 Test: {test.title} | Kutilgan summa: {_fmt_price(test.price)}"
    )
    if duplicate is not None:
        caption += f"\n⚠️ BU CHEK AVVAL YUBORILGAN (payment #{duplicate.payment_id})!"

    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_photo(
                admin_id,
                photo=payment.receipt_file_id,
                caption=caption,
                reply_markup=approve_reject_keyboard(payment.payment_id),
            )
        except Exception:
            continue
