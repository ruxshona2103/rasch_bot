"""III.8-bo'lim: Kabinet, Natijalar, Video yechimlar, Yordam/Aloqa."""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import (
    count_attempts_by_kind,
    get_test,
    get_user_by_telegram_id,
    list_tests_with_video,
    list_user_attempts,
)

router = Router(name="cabinet")


def _fmt_ball(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


@router.message(F.text == "👤 Kabinetim")
async def show_cabinet(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)

    jonli_count = await count_attempts_by_kind(session, user.user_pk, "jonli")
    arxiv_count = await count_attempts_by_kind(session, user.user_pk, "arxiv")

    attempts = [a for a in await list_user_attempts(session, user.user_pk) if a.ball_75 is not None]

    lines = [
        f"👤 {user.full_name} | 🎫 ID: {user.public_id if user.public_id else 'hali yo‘q'}",
        f"📊 {jonli_count} jonli, {arxiv_count} arxiv",
    ]

    if attempts:
        dynamics = " → ".join(_fmt_ball(a.ball_75) for a in attempts)
        best = max(attempts, key=lambda a: a.ball_75)
        lines.append(f"📈 Dinamika: {dynamics}")
        lines.append(f"🎖 Eng yaxshi: {best.grade} ({_fmt_ball(best.ball_75)})")
    else:
        lines.append("📈 Hali yakunlangan urinishlaringiz yo'q.")

    await message.answer("\n".join(lines))


@router.message(F.text == "📊 Natijalarim")
async def show_results(message: Message, session: AsyncSession) -> None:
    user = await get_user_by_telegram_id(session, message.from_user.id)
    attempts = [
        a
        for a in await list_user_attempts(session, user.user_pk)
        if a.status == "yakunlangan" and a.ball_75 is not None
    ]

    if not attempts:
        await message.answer("Hali yakunlangan natijalaringiz yo'q.")
        return

    for attempt in attempts:
        test = await get_test(session, attempt.test_id)
        practice_tag = " 🏋️ Mashq" if attempt.kind == "arxiv" else ""
        rank = f" | 🥇 {attempt.rank_position}-o'rin" if attempt.rank_position else ""
        await message.answer(
            f"{test.title}{practice_tag}\n"
            f"📊 Ball: {_fmt_ball(attempt.ball_75)} / 75 | 🎖 {attempt.grade}{rank}"
        )


@router.message(F.text == "🎥 Video yechimlar")
async def show_videos(message: Message, session: AsyncSession) -> None:
    tests = await list_tests_with_video(session)
    if not tests:
        await message.answer("Hozircha video yechimlar yo'q.")
        return

    lines = [f"🎥 {test.title}\n{test.video_url}" for test in tests]
    await message.answer("\n\n".join(lines))


@router.message(F.text == "ℹ️ Yordam / Aloqa")
async def show_help(message: Message) -> None:
    await message.answer(
        "ℹ️ Yordam / Aloqa\n\n"
        "Bu — norasmiy mock-test botidir, Milliy sertifikat rasmiy tashkilotiga "
        "(BBA) aloqasi yo'q.\n\n"
        "Savol yoki muammo bo'lsa, admin bilan bevosita bog'laning."
    )
