"""IV.6-bo'lim: statistika.

Moliya va umumiy foydalanuvchi statistikasi hoziroq ishlaydi. Savol/test
statistikasi (b qiyinlik, misfit) Rasch Engine va Exam Mode qurilgach qo'shiladi
— ular hisoblash uchun yakunlangan urinishlar (attempts/answers) kerak.
"""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin import IsAdmin
from db.queries import count_blocked_users, count_users, count_users_with_payment, payment_stats

router = Router(name="admin_stats")
router.message.filter(IsAdmin())


def _fmt_sum(value: int) -> str:
    return f"{value:,} so'm".replace(",", " ")


@router.message(F.text == "📊 Statistika")
async def show_stats(message: Message, session: AsyncSession) -> None:
    total_users = await count_users(session)
    blocked_users = await count_blocked_users(session)
    paying_users = await count_users_with_payment(session)
    conversion = (paying_users / total_users * 100) if total_users else 0

    stats = await payment_stats(session)

    text = (
        "📊 STATISTIKA\n\n"
        "👥 Umumiy:\n"
        f"  • Userlar: {total_users}\n"
        f"  • Bloklaganlar: {blocked_users}\n"
        f"  • Konversiya (ro'yxat → to'lov): {conversion:.1f}%\n\n"
        "💰 Moliya:\n"
        f"  • Tasdiqlangan: {stats['approved_count']} ta | Tushum: {_fmt_sum(stats['approved_sum'])}\n"
        f"  • Rad etilgan: {stats['rejected_count']} ta\n"
        f"  • Kutilmoqda: {stats['pending_count']} ta\n\n"
        "📈 Test/savol statistikasi (b qiyinlik, misfit) Rasch Engine "
        "qurilgach shu yerda chiqadi."
    )
    await message.answer(text)
