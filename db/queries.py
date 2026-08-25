from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AdminLog, Answer, Attempt, Payment, Purchase, Question, Test, User, public_id_seq


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_pk(session: AsyncSession, user_pk: int) -> User | None:
    return await session.get(User, user_pk)


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    phone: str,
    region: str | None,
) -> User:
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        region=region,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_test(
    session: AsyncSession,
    title: str,
    price: int,
    duration_min: int,
    mode: str,
    start_at: datetime | None,
    deadline_at: datetime | None,
    status: str,
) -> Test:
    test = Test(
        title=title,
        price=price,
        duration_min=duration_min,
        mode=mode,
        start_at=start_at,
        deadline_at=deadline_at,
        status=status,
    )
    session.add(test)
    await session.commit()
    await session.refresh(test)
    return test


async def add_question(
    session: AsyncSession,
    test_id: int,
    order_num: int,
    qtype: str,
    correct_answer: str,
    text: str | None = None,
    image_file_id: str | None = None,
) -> Question:
    question = Question(
        test_id=test_id,
        order_num=order_num,
        text=text,
        image_file_id=image_file_id,
        qtype=qtype,
        correct_answer=correct_answer,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return question


async def count_questions(session: AsyncSession, test_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Question).where(Question.test_id == test_id)
    )
    return result.scalar_one()


async def get_test(session: AsyncSession, test_id: int) -> Test | None:
    result = await session.execute(select(Test).where(Test.test_id == test_id))
    return result.scalar_one_or_none()


async def list_tests_by_mode(session: AsyncSession, mode: str) -> list[Test]:
    result = await session.execute(
        select(Test).where(Test.mode == mode).order_by(Test.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_tests(session: AsyncSession) -> list[Test]:
    result = await session.execute(select(Test).order_by(Test.created_at.desc()))
    return list(result.scalars().all())


# ---------------- To'lov / chipta ----------------


async def has_purchase(session: AsyncSession, user_pk: int, test_id: int) -> bool:
    result = await session.execute(
        select(Purchase.purchase_id).where(
            Purchase.user_pk == user_pk, Purchase.test_id == test_id
        )
    )
    return result.scalar_one_or_none() is not None


async def get_pending_payment(session: AsyncSession, user_pk: int, test_id: int) -> Payment | None:
    result = await session.execute(
        select(Payment).where(
            Payment.user_pk == user_pk,
            Payment.test_id == test_id,
            Payment.status == "kutilmoqda",
        )
    )
    return result.scalar_one_or_none()


async def get_payment_by_receipt_hash(session: AsyncSession, receipt_hash: str) -> Payment | None:
    result = await session.execute(
        select(Payment)
        .where(Payment.receipt_hash == receipt_hash)
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().first()


async def create_payment(
    session: AsyncSession,
    user_pk: int,
    test_id: int,
    receipt_file_id: str,
    receipt_hash: str | None,
    amount: int,
) -> Payment:
    payment = Payment(
        user_pk=user_pk,
        test_id=test_id,
        receipt_file_id=receipt_file_id,
        receipt_hash=receipt_hash,
        amount=amount,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment(session: AsyncSession, payment_id: int) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.payment_id == payment_id))
    return result.scalar_one_or_none()


async def list_pending_payments(session: AsyncSession) -> list[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.status == "kutilmoqda").order_by(Payment.created_at)
    )
    return list(result.scalars().all())


async def approve_payment(session: AsyncSession, payment_id: int, admin_id: int) -> Payment | None:
    """Atomik tasdiqlash: faqat hali 'kutilmoqda' bo'lsa amalga oshadi (ikki admin
    bir vaqtda bosishiga qarshi). public_id kerak bo'lsa SEQUENCE orqali beriladi."""
    result = await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id, Payment.status == "kutilmoqda")
        .values(status="tasdiqlangan", admin_id=admin_id, decided_at=func.now())
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        return None

    user = await session.get(User, payment.user_pk)
    if user.public_id is None:
        seq_result = await session.execute(select(public_id_seq.next_value()))
        user.public_id = seq_result.scalar_one()

    session.add(Purchase(user_pk=payment.user_pk, test_id=payment.test_id, payment_id=payment.payment_id))
    session.add(
        AdminLog(admin_id=admin_id, action="payment_approve", target=f"payment_id={payment_id}")
    )
    await session.commit()
    await session.refresh(payment)
    return payment


async def reject_payment(
    session: AsyncSession, payment_id: int, admin_id: int, reason: str
) -> Payment | None:
    result = await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id, Payment.status == "kutilmoqda")
        .values(status="rad_etilgan", admin_id=admin_id, decided_at=func.now(), reject_reason=reason)
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        return None

    session.add(
        AdminLog(admin_id=admin_id, action="payment_reject", target=f"payment_id={payment_id}")
    )
    await session.commit()
    await session.refresh(payment)
    return payment


# ---------------- Test boshqaruv (admin) ----------------


async def set_test_video_url(session: AsyncSession, test_id: int, video_url: str) -> None:
    await session.execute(update(Test).where(Test.test_id == test_id).values(video_url=video_url))
    await session.commit()


async def mark_test_status(
    session: AsyncSession,
    test_id: int,
    from_statuses: tuple[str, ...],
    to_status: str,
    **extra_values,
) -> bool:
    """Faqat test hozir from_statuses'dan birida bo'lsa statusni o'zgartiradi
    (avtopilot bosqichlarini ikki marta bajarmaslik uchun himoya)."""
    result = await session.execute(
        update(Test)
        .where(Test.test_id == test_id, Test.status.in_(from_statuses))
        .values(status=to_status, **extra_values)
        .returning(Test.test_id)
    )
    changed = result.scalar_one_or_none() is not None
    await session.commit()
    return changed


async def start_test_manually(session: AsyncSession, test_id: int) -> bool:
    """🆕 Admin 'jonli' testni istalgan payt qo'lda boshlaydi ('▶️ Hoziroq boshlash').
    Vaqt oldindan belgilangan bo'lsa ham ('rejalashtirilgan'), shu tugma bilan
    admin uni kutmasdan darhol boshlashi mumkin — start_at 'hozir'ga yangilanadi."""
    return await mark_test_status(
        session, test_id, ("tayyorlanmoqda", "rejalashtirilgan"), "jonli_davom", start_at=func.now()
    )


async def set_test_schedule(session: AsyncSession, test_id: int, start_at, deadline_at) -> bool:
    """🆕 Admin '🕐 Vaqt belgilash' orqali boshlanish/tugash vaqtini kiritganda —
    test.status='rejalashtirilgan'ga o'tadi, keyin avtopilot (scheduler) shu
    vaqtda avtomatik ochadi/yopadi (schedule_test orqali)."""
    return await mark_test_status(
        session, test_id, ("tayyorlanmoqda",), "rejalashtirilgan", start_at=start_at, deadline_at=deadline_at
    )


async def finish_test_manually(session: AsyncSession, test_id: int) -> bool:
    """🆕 Admin 'jonli' testni istalgan payt qo'lda yakunlaydi ('🏁 Yakunlash').
    Rasch Engine hali yo'qligi uchun to'g'ridan-to'g'ri 'yakunlangan'ga o'tadi."""
    changed = await mark_test_status(
        session, test_id, ("jonli_davom",), "hisoblanmoqda", deadline_at=func.now()
    )
    if not changed:
        return False
    await mark_test_status(session, test_id, ("hisoblanmoqda",), "yakunlangan", calibrated=True)
    return True


async def cancel_test(session: AsyncSession, test_id: int, admin_id: int) -> None:
    await session.execute(
        update(Test).where(Test.test_id == test_id).values(status="bekor_qilingan")
    )
    session.add(AdminLog(admin_id=admin_id, action="test_cancel", target=f"test_id={test_id}"))
    await session.commit()


async def list_purchasers(session: AsyncSession, test_id: int) -> list[User]:
    result = await session.execute(
        select(User).join(Purchase, Purchase.user_pk == User.user_pk).where(Purchase.test_id == test_id)
    )
    return list(result.scalars().all())


# ---------------- Kabinet / Natijalar / Video (user) ----------------


async def list_user_attempts(session: AsyncSession, user_pk: int) -> list[Attempt]:
    result = await session.execute(
        select(Attempt).where(Attempt.user_pk == user_pk).order_by(Attempt.started_at)
    )
    return list(result.scalars().all())


async def count_attempts_by_kind(session: AsyncSession, user_pk: int, kind: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Attempt)
        .where(Attempt.user_pk == user_pk, Attempt.kind == kind, Attempt.status == "yakunlangan")
    )
    return result.scalar_one()


async def list_tests_with_video(session: AsyncSession) -> list[Test]:
    result = await session.execute(
        select(Test).where(Test.video_url.is_not(None)).order_by(Test.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------- Statistika (admin) ----------------


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def count_blocked_users(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.is_blocked.is_(True))
    )
    return result.scalar_one()


async def count_users_with_payment(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(func.distinct(Payment.user_pk))))
    return result.scalar_one()


async def payment_stats(session: AsyncSession) -> dict:
    result = await session.execute(
        select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == "tasdiqlangan")
        .group_by(Payment.status)
    )
    approved_count, approved_sum = 0, 0
    row = result.first()
    if row:
        _, approved_count, approved_sum = row

    pending_result = await session.execute(
        select(func.count()).select_from(Payment).where(Payment.status == "kutilmoqda")
    )
    rejected_result = await session.execute(
        select(func.count()).select_from(Payment).where(Payment.status == "rad_etilgan")
    )
    return {
        "approved_count": approved_count,
        "approved_sum": approved_sum,
        "pending_count": pending_result.scalar_one(),
        "rejected_count": rejected_result.scalar_one(),
    }


# ---------------- Broadcast (admin) ----------------


async def list_all_user_telegram_ids(session: AsyncSession) -> list[tuple[int, int]]:
    """(user_pk, telegram_id) juftliklarini qaytaradi, bloklanganlarsiz."""
    result = await session.execute(
        select(User.user_pk, User.telegram_id).where(User.is_blocked.is_(False))
    )
    return [tuple(row) for row in result.all()]


async def mark_user_blocked(session: AsyncSession, user_pk: int) -> None:
    await session.execute(update(User).where(User.user_pk == user_pk).values(is_blocked=True))
    await session.commit()


# ---------------- Exam Mode (III.5-bo'lim) ----------------


async def get_questions_for_test(session: AsyncSession, test_id: int) -> list[Question]:
    result = await session.execute(
        select(Question).where(Question.test_id == test_id).order_by(Question.order_num)
    )
    return list(result.scalars().all())


async def get_attempt(session: AsyncSession, user_pk: int, test_id: int) -> Attempt | None:
    result = await session.execute(
        select(Attempt).where(Attempt.user_pk == user_pk, Attempt.test_id == test_id)
    )
    return result.scalar_one_or_none()


async def get_attempt_by_id(session: AsyncSession, attempt_id: int) -> Attempt | None:
    return await session.get(Attempt, attempt_id)


async def create_attempt(
    session: AsyncSession, user_pk: int, test_id: int, kind: str, deadline_at: datetime
) -> Attempt:
    attempt = Attempt(
        user_pk=user_pk,
        test_id=test_id,
        kind=kind,
        started_at=func.now(),
        deadline_at=deadline_at,
        status="davom_etmoqda",
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def upsert_answer(session: AsyncSession, attempt_id: int, question_id: int, answer: str) -> None:
    """Har javob darhol DB'ga yoziladi (internet uzilsa ham yo'qolmasligi uchun)."""
    stmt = pg_insert(Answer).values(attempt_id=attempt_id, question_id=question_id, answer=answer)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Answer.attempt_id, Answer.question_id],
        set_={"answer": answer, "updated_at": func.now()},
    )
    await session.execute(stmt)
    await session.commit()


async def get_answers_map(session: AsyncSession, attempt_id: int) -> dict[int, str]:
    result = await session.execute(
        select(Answer.question_id, Answer.answer).where(Answer.attempt_id == attempt_id)
    )
    return {question_id: answer for question_id, answer in result.all() if answer}


async def finish_attempt(session: AsyncSession, attempt_id: int) -> None:
    await session.execute(
        update(Attempt)
        .where(Attempt.attempt_id == attempt_id)
        .values(status="yakunlangan", finished_at=func.now())
    )
    await session.commit()


async def auto_close_attempt(session: AsyncSession, attempt_id: int) -> None:
    """🆕 Admin jonli testni 'Yakunlash' bilan to'xtatganda, hali davom etayotgan
    urinishlarni majburan yopadi (foydalanuvchi keyingi harakatida)."""
    await session.execute(
        update(Attempt)
        .where(Attempt.attempt_id == attempt_id, Attempt.status == "davom_etmoqda")
        .values(status="vaqt_tugagan", finished_at=func.now())
    )
    await session.commit()
