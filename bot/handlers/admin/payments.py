"""IV.4-bo'lim: to'lovlarni ko'rish, tasdiqlash, rad etish."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from bot.keyboards.payment import approve_reject_keyboard, reject_reason_keyboard
from bot.states.payment import PaymentReview
from db.queries import (
    approve_payment,
    get_test,
    get_user_by_pk,
    list_pending_payments,
    reject_payment,
)

router = Router(name="admin_payments")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

_REASON_TEXTS = {
    "summa_kam": "Summa kam",
    "soxta": "Chek soxta",
}


def _fmt_price(price: int) -> str:
    return f"{price:,} so'm".replace(",", " ")


@router.message(F.text == "💳 To'lovlar")
async def list_payments(message: Message, session: AsyncSession) -> None:
    payments = await list_pending_payments(session)
    if not payments:
        await message.answer("Hozircha yangi to'lovlar yo'q.")
        return

    for payment in payments:
        user = await get_user_by_pk(session, payment.user_pk)
        test = await get_test(session, payment.test_id)
        caption = (
            f"🔔 TO'LOV #{payment.payment_id}\n"
            f"👤 {user.full_name} | 📱 {user.phone}\n"
            + ("🆕 Birinchi to'lov (ID yo'q)\n" if user.public_id is None else f"🎫 ID: {user.public_id}\n")
            + f"🧪 Test: {test.title} | Kutilgan summa: {_fmt_price(test.price)}"
        )
        await message.answer_photo(
            photo=payment.receipt_file_id,
            caption=caption,
            reply_markup=approve_reject_keyboard(payment.payment_id),
        )


@router.callback_query(F.data.startswith("pay:approve:"))
async def approve(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_id = int(callback.data.split(":")[2])
    payment = await approve_payment(session, payment_id, callback.from_user.id)
    if payment is None:
        await callback.answer("⚠️ Bu chek allaqachon hal qilingan.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    user = await get_user_by_pk(session, payment.user_pk)
    test = await get_test(session, payment.test_id)

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + f"\n\n✅ TASDIQLANDI | 🎫 ID: {user.public_id}",
        reply_markup=None,
    )

    try:
        await callback.bot.send_message(
            user.telegram_id,
            "✅ To'lovingiz tasdiqlandi!\n"
            f"🎫 Sizning unikal ID: {user.public_id}\n"
            "   (doimiy raqam — barcha testlarda shu; reytingda ism o'rniga chiqadi)\n"
            f"{'🔴' if test.mode == 'jonli' else '📚'} {test.title} ga kirish ochildi.",
        )
    except Exception:
        pass

    await callback.answer("Tasdiqlandi ✅")


@router.callback_query(F.data.startswith("pay:reject:"))
async def reject_start(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(reply_markup=reject_reason_keyboard(payment_id))
    await callback.answer()


@router.callback_query(F.data.startswith("payreason:"))
async def reject_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, payment_id_str, reason_code = callback.data.split(":")
    payment_id = int(payment_id_str)

    if reason_code == "boshqa":
        await state.update_data(reject_payment_id=payment_id)
        await callback.message.answer("Rad etish sababini yozing:")
        await state.set_state(PaymentReview.waiting_reject_reason)
        await callback.answer()
        return

    await _finish_reject(callback, session, payment_id, _REASON_TEXTS[reason_code])


@router.message(PaymentReview.waiting_reject_reason, F.text)
async def reject_reason_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    payment_id = data["reject_payment_id"]
    await state.clear()

    reason = message.text.strip()
    payment = await reject_payment(session, payment_id, message.from_user.id, reason)
    if payment is None:
        await message.answer("⚠️ Bu chek allaqachon hal qilingan.")
        return

    user = await get_user_by_pk(session, payment.user_pk)
    await message.answer(f"❌ To'lov #{payment_id} rad etildi.")
    try:
        await message.bot.send_message(
            user.telegram_id,
            f"❌ To'lovingiz rad etildi.\nSabab: {reason}\nQayta urinib ko'rishingiz mumkin.",
        )
    except Exception:
        pass


async def _finish_reject(callback: CallbackQuery, session: AsyncSession, payment_id: int, reason: str) -> None:
    payment = await reject_payment(session, payment_id, callback.from_user.id, reason)
    if payment is None:
        await callback.answer("⚠️ Bu chek allaqachon hal qilingan.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    user = await get_user_by_pk(session, payment.user_pk)
    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + f"\n\n❌ RAD ETILDI ({reason})", reply_markup=None
    )
    try:
        await callback.bot.send_message(
            user.telegram_id,
            f"❌ To'lovingiz rad etildi.\nSabab: {reason}\nQayta urinib ko'rishingiz mumkin.",
        )
    except Exception:
        pass
    await callback.answer("Rad etildi ❌")
