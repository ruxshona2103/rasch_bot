"""V-bo'lim: Rasch Engine.

Jonli (MIN_PARTICIPANTS_FOR_RASCH+ ishtirokchi): JMLE — b_difficulty
savollarga, theta o'quvchilarga.
Jonli (undan kam ishtirokchi): klassik % ball (Rasch ishonchsiz bo'lgani uchun).
Arxiv (kalibrlangan bo'lsa): MLE — mavjud b_difficulty asosida <1s da theta.
Arxiv (kalibrlanmagan bo'lsa): klassik % ball.

Eslatma: BBA rasmiy logit->ball koeffitsiyentini e'lon qilmagan, shuning uchun
bu yerdagi chiziqli transformatsiya (SCALE_CENTER/SCALE_SPREAD) taxminiy —
natija rasmiyga yaqin, lekin aynan emas ("norasmiy mock", VIII-qism).

Kalibrlash edge case'lari:
- 0% yoki 100% yechilgan savollar JMLE matritsasidan chiqariladi (aks holda
  cheksiz logit kerak bo'lib, matematik jihatdan yechib bo'lmaydi)
- Hammasiga to'g'ri/noto'g'ri javob bergan o'quvchilarga theta THETA_CAP bilan
  chegaralanadi (eng qiyin/eng oson savol +-THETA_CAP)
- Ball 1 xonagacha yaxlitlangandan keyingina darajaga aylantiriladi
- Reytingda teng ball: avval ball (kamayish), keyin finished_at (o'sish —
  tezroq tugatgan yuqorida)
"""

import numpy as np

from core.answer_key import is_open_answer_correct

MAX_BALL = 75.0
SCALE_CENTER = 37.5
SCALE_SPREAD = 7.5
THETA_CAP = 4.0
MIN_PARTICIPANTS_FOR_RASCH = 10  # 🆕 sinov uchun 50dan pasaytirildi — real ishga tushishda 50ga qaytariladi

GRADE_TABLE = [
    (70.0, "A+"),
    (65.0, "A"),
    (60.0, "B+"),
    (55.0, "B"),
    (50.0, "C+"),
    (46.0, "C"),
]


def ball_to_grade(ball_75: float) -> str | None:
    rounded = round(ball_75, 1)
    for threshold, label in GRADE_TABLE:
        if rounded >= threshold:
            return label
    return None


def theta_to_ball75(theta: float) -> float:
    ball = SCALE_CENTER + SCALE_SPREAD * theta
    return round(max(0.0, min(MAX_BALL, ball)), 1)


def classic_ball(correct: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((correct / total) * MAX_BALL, 1)


def is_answer_correct(question, given_answer: str | None) -> bool:
    if not given_answer:
        return False
    if question.qtype == "yopiq":
        return given_answer.strip().upper() == question.correct_answer.strip().upper()
    return is_open_answer_correct(given_answer, question.correct_answer)


def run_jmle(
    matrix: np.ndarray, max_iter: int = 100, tol: float = 1e-3
) -> tuple[np.ndarray, np.ndarray]:
    """matrix: N x M (0/1). Qaytaradi: thetas (N,), bs (M,) — bs'da
    kalibrlanmagan (0%/100%) savollar uchun NaN turadi."""
    n, m = matrix.shape
    item_totals = matrix.sum(axis=0)
    item_mask = (item_totals > 0) & (item_totals < n)

    thetas = np.zeros(n)
    bs = np.full(m, np.nan)

    if item_mask.sum() == 0:
        return thetas, bs

    sub = matrix[:, item_mask]
    max_score = int(item_mask.sum())
    raw_scores = sub.sum(axis=1)

    person_mask = (raw_scores > 0) & (raw_scores < max_score)
    active_idx = np.where(person_mask)[0]

    low_cap, high_cap = -THETA_CAP, THETA_CAP

    if active_idx.size > 0:
        active_matrix = sub[active_idx]
        r = active_matrix.sum(axis=1)
        s = active_matrix.sum(axis=0)

        theta_a = np.zeros(len(active_idx))
        b_a = np.zeros(max_score)

        for _ in range(max_iter):
            p = 1.0 / (1.0 + np.exp(-(theta_a[:, None] - b_a[None, :])))
            s_hat = p.sum(axis=0)
            info_i = np.clip((p * (1 - p)).sum(axis=0), 1e-6, None)
            b_a = b_a - (s - s_hat) / info_i
            b_a -= b_a.mean()

            p = 1.0 / (1.0 + np.exp(-(theta_a[:, None] - b_a[None, :])))
            r_hat = p.sum(axis=1)
            info_p = np.clip((p * (1 - p)).sum(axis=1), 1e-6, None)
            theta_a_new = theta_a + (r - r_hat) / info_p

            delta = float(np.max(np.abs(theta_a_new - theta_a)))
            theta_a = theta_a_new
            if delta < tol:
                break

        thetas[active_idx] = theta_a
        bs[np.where(item_mask)[0]] = b_a
        low_cap = b_a.min() - THETA_CAP
        high_cap = b_a.max() + THETA_CAP

    thetas[raw_scores == 0] = low_cap
    thetas[raw_scores == max_score] = high_cap

    return thetas, bs


def run_mle_single(responses: np.ndarray, bs: np.ndarray, max_iter: int = 50, tol: float = 1e-4) -> float:
    """responses/bs: 1-D. bs'dagi NaN (kalibrlanmagan) savollar tashlab yuboriladi."""
    valid = ~np.isnan(bs)
    b = bs[valid]
    x = responses[valid]
    if b.size == 0:
        return 0.0

    r = float(x.sum())
    max_score = b.size
    if r == 0:
        return float(b.min() - THETA_CAP)
    if r == max_score:
        return float(b.max() + THETA_CAP)

    theta = 0.0
    for _ in range(max_iter):
        p = 1.0 / (1.0 + np.exp(-(theta - b)))
        r_hat = p.sum()
        info = max(float((p * (1 - p)).sum()), 1e-6)
        theta_new = theta + (r - r_hat) / info
        if abs(theta_new - theta) < tol:
            theta = theta_new
            break
        theta = theta_new
    return float(theta)


# ---------------- Orchestration (DB bilan ishlaydigan qism) ----------------


async def finalize_jonli_test(session, test_id: int) -> list[tuple[int, float, str | None, int]]:
    """Jonli test yakunlanganda (admin 'Yakunlash' bosgach yoki avtopilot orqali)
    barcha ishtirokchilar uchun BIR VAQTDA chaqiriladi. test.status allaqachon
    'hisoblanmoqda' bo'lishi kerak (test_manage.py / scheduler.close_test).

    Qaytaradi: [(user_pk, ball_75, grade, rank_position), ...] — xabar yuborish uchun.
    Ma'lumot yo'q bo'lsa ham (0 savol yoki 0 urinish) test baribir
    'yakunlangan'ga o'tkaziladi — aks holda 'hisoblanmoqda'da abadiy qolib ketardi.
    """
    from db.queries import (
        get_answers_map,
        get_questions_for_test,
        list_scoreable_attempts,
        mark_test_status,
        set_attempt_result,
        set_question_b_difficulty,
    )

    questions = [q for q in await get_questions_for_test(session, test_id) if not q.is_excluded]
    attempts = await list_scoreable_attempts(session, test_id)

    payload: list[tuple[int, float, str | None, int]] = []
    use_rasch = False

    if questions and attempts:
        matrix = np.zeros((len(attempts), len(questions)), dtype=int)
        for i, attempt in enumerate(attempts):
            answers = await get_answers_map(session, attempt.attempt_id)
            for j, q in enumerate(questions):
                matrix[i, j] = 1 if is_answer_correct(q, answers.get(q.question_id)) else 0

        use_rasch = len(attempts) >= MIN_PARTICIPANTS_FOR_RASCH
        results: list[tuple] = []  # (attempt, ball, grade, theta)

        if use_rasch:
            thetas, bs = run_jmle(matrix)
            for j, q in enumerate(questions):
                b_val = bs[j]
                await set_question_b_difficulty(
                    session, q.question_id, None if np.isnan(b_val) else float(b_val)
                )
            for i, attempt in enumerate(attempts):
                ball = theta_to_ball75(float(thetas[i]))
                grade = ball_to_grade(ball)
                results.append((attempt, ball, grade, float(thetas[i])))
        else:
            for i, attempt in enumerate(attempts):
                correct = int(matrix[i].sum())
                ball = classic_ball(correct, len(questions))
                grade = ball_to_grade(ball)
                results.append((attempt, ball, grade, None))

        # Reyting: ball kamayish, keyin finished_at o'sish (tezroq tugatgan yuqorida)
        ranked = sorted(
            results,
            key=lambda item: (-item[1], item[0].finished_at or item[0].started_at),
        )
        for rank, (attempt, ball, grade, theta) in enumerate(ranked, start=1):
            await set_attempt_result(session, attempt.attempt_id, theta, ball, grade, rank_position=rank)
            payload.append((attempt.user_pk, ball, grade, rank))

    await mark_test_status(session, test_id, ("hisoblanmoqda",), "yakunlangan", calibrated=use_rasch)
    return payload


async def score_archive_attempt(session, attempt_id: int) -> tuple[float, str | None]:
    """Arxiv urinishi yakunlanganda DARHOL chaqiriladi (III.7-bo'lim).
    Test kalibrlangan bo'lsa MLE (<1s), bo'lmasa klassik % ball."""
    from db.queries import get_attempt_by_id, get_questions_for_test, get_test, get_answers_map, set_attempt_result

    attempt = await get_attempt_by_id(session, attempt_id)
    test = await get_test(session, attempt.test_id)
    questions = [q for q in await get_questions_for_test(session, attempt.test_id) if not q.is_excluded]
    answers = await get_answers_map(session, attempt_id)

    if not questions:
        await set_attempt_result(session, attempt_id, None, 0.0, None)
        return 0.0, None

    responses = np.array(
        [1 if is_answer_correct(q, answers.get(q.question_id)) else 0 for q in questions]
    )

    if test.calibrated:
        bs = np.array(
            [q.b_difficulty if q.b_difficulty is not None else np.nan for q in questions]
        )
        theta = run_mle_single(responses, bs)
        ball = theta_to_ball75(theta)
    else:
        theta = None
        ball = classic_ball(int(responses.sum()), len(questions))

    grade = ball_to_grade(ball)
    await set_attempt_result(session, attempt_id, theta, ball, grade)
    return ball, grade
