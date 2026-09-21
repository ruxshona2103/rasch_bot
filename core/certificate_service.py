"""🆕 Sertifikat ma'lumotlarini bazadan yig'ish va foydalanuvchiga yuborish."""

import logging
from datetime import datetime

from aiogram.types import BufferedInputFile

from bot.config import settings
from core.ai_check import ai_key
from core.certificate import CertificateData, render_certificate_async, split_section_scores
from core.rasch import is_answer_correct
from core.topics import TOPIC_LABELS, TOPIC_ORDER
from db.engine import async_session
from db.queries import (
    count_scored_attempts,
    get_ai_verdict_cache,
    get_answers_map,
    get_attempt_by_id,
    get_questions_for_test,
    get_test,
    get_user_by_pk,
)

logger = logging.getLogger(__name__)


async def gather_certificate_data(session, attempt_id: int) -> CertificateData | None:
    attempt = await get_attempt_by_id(session, attempt_id)
    if attempt is None or attempt.ball_75 is None:
        return None
    user = await get_user_by_pk(session, attempt.user_pk)
    test = await get_test(session, attempt.test_id)
    questions = [q for q in await get_questions_for_test(session, attempt.test_id) if not q.is_excluded]

    sections: list[tuple[str, float]] = []
    if any(q.topic for q in questions):
        answers = await get_answers_map(session, attempt_id)
        cache = await get_ai_verdict_cache(session, [q.question_id for q in questions if q.qtype == "ochiq"])
        by_id = {q.question_id: q for q in questions}
        verdicts = {
            key: verdict for key, (correct, verdict) in cache.items() if by_id[key[0]].correct_answer == correct
        }
        correct_by_topic: dict[str, int] = {}
        for topic in TOPIC_ORDER:
            in_topic = [q for q in questions if q.topic == topic]
            if in_topic:
                correct_by_topic[TOPIC_LABELS[topic]] = sum(
                    1 for q in in_topic if is_answer_correct(q, answers.get(q.question_id), verdicts)
                )
        sections = split_section_scores(attempt.ball_75, correct_by_topic)

    participants = None
    if attempt.rank_position and attempt.kind == "jonli":
        participants = await count_scored_attempts(session, attempt.test_id, "jonli")

    moment = attempt.finished_at or datetime.now(settings.tzinfo)
    return CertificateData(
        full_name=user.full_name,
        username=user.username,
        test_title=test.title,
        ball=attempt.ball_75,
        grade=attempt.grade,
        date=moment.astimezone(settings.tzinfo),
        seed=attempt.attempt_id,
        rank=attempt.rank_position if participants else None,
        participants=participants,
        sections=sections,
    )


def certificate_filename(data: CertificateData) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in data.full_name)[:40].strip("_") or "natija"
    return f"Sertifikat_{safe}.pdf"


async def send_certificate(bot, telegram_id: int, attempt_id: int) -> bool:
    """Sertifikatni yaratib foydalanuvchiga hujjat sifatida yuboradi. Xatoda
    (masalan bot bloklangan) False qaytaradi va e'tibor bermaydi."""
    try:
        async with async_session() as session:
            data = await gather_certificate_data(session, attempt_id)
        if data is None:
            return False
        pdf = await render_certificate_async(data)
        await bot.send_document(
            telegram_id,
            BufferedInputFile(pdf, filename=certificate_filename(data)),
            caption=(
                f"🎓 Natija sertifikatingiz\n📊 Ball: {data.ball:.2f} | 🎖 Daraja: {data.grade or 'NC'}\n"
                "Abdurashid Yusufov bilan hammasi oson!"
            ),
        )
        return True
    except Exception:
        logger.warning("Sertifikat yuborilmadi: attempt_id=%s", attempt_id, exc_info=True)
        return False
