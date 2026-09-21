"""🆕 Mini App uchun backend API. Botning o'zi bilan BIR jarayonda ishlaydi
(alohida konteyner/server emas) -- xotira tejash uchun. Faqat localhost'da
tinglaydi (127.0.0.1:8080), tashqi dunyoga Caddy orqali /api/* sifatida
ochiladi (webapp_domain/api/...).

Autentifikatsiya: har so'rov "Authorization: tma <initData>" sarlavhasi bilan
keladi, initData core.webapp_auth.validate_init_data orqali HMAC bilan
tekshiriladi -- shu orqali foydalanuvchi Telegram ID'si xavfsiz aniqlanadi
(parolsiz, tokensiz -- Telegram Mini App'ning rasmiy usuli).
"""

import asyncio
import json
import logging
import time

from aiogram.types import BufferedInputFile
from aiohttp import web

from bot.config import settings
from core.ai_check import answer_input_ok
from core.certificate_service import send_certificate
from core.answer_key import normalize_open_answer
from core.export import build_results_excel
from core.rasch import format_breakdown, score_archive_attempt
from core.webapp_auth import validate_init_data
from db.engine import async_session
from db.queries import (
    clear_all_stale_drafts,
    clear_stale_draft,
    create_attempt,
    finish_attempt,
    get_answers_map,
    get_attempt,
    get_question_labels,
    get_questions_for_test,
    get_test,
    get_user_by_telegram_id,
    has_purchase,
    list_all_tests,
    list_attempts_with_users_for_export,
    list_user_attempts,
    list_user_purchased_tests,
    touch_attempt,
    upsert_answer,
)

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()
_cert_last_request: dict[int, float] = {}


async def _authenticate(request: web.Request):
    """Qaytaradi: (session, user) yoki None (401 chiqarilishi kerak bo'lsa)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("tma "):
        return None
    init_data = auth[len("tma ") :]
    parsed = validate_init_data(init_data, settings.BOT_TOKEN)
    if parsed is None or "user" not in parsed:
        return None

    telegram_id = parsed["user"].get("id")
    if not telegram_id:
        return None

    session = async_session()
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        await session.close()
        return None
    return session, user


async def _authenticate_admin(request: web.Request):
    auth = await _authenticate(request)
    if auth is None:
        return None
    session, user = auth
    if user.telegram_id not in settings.admin_ids:
        await session.close()
        return None
    return session, user


def _json_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


@routes.get("/api/health")
async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@routes.get("/api/tests/{test_id}")
async def get_test_schema(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        test_id = int(request.match_info["test_id"])
        test = await get_test(session, test_id)
        if test is None or test.status == "bekor_qilingan":
            return _json_error("Test topilmadi.", 404)
        if not await has_purchase(session, user.user_pk, test_id):
            return _json_error("Bu test uchun kirish huquqi yo'q.", 403)
        if test.mode == "jonli" and test.status != "jonli_davom":
            return _json_error("Test hali boshlanmagan yoki allaqachon yakunlangan.", 409)

        questions = await get_questions_for_test(session, test_id)
        if not questions:
            return _json_error("Bu testda hali savollar yo'q.", 404)

        attempt = await get_attempt(session, user.user_pk, test_id)
        answers_map: dict[int, str] = {}
        attempt_payload = None
        if attempt is not None:
            if attempt.status != "davom_etmoqda":
                return web.json_response(
                    {
                        "ok": True,
                        "test": {"id": test.test_id, "title": test.title, "mode": test.mode},
                        "user": {"full_name": user.full_name},
                        "finished": True,
                    }
                )
            await clear_stale_draft(session, attempt.attempt_id)
            await touch_attempt(session, attempt.attempt_id)
            raw_answers = await get_answers_map(session, attempt.attempt_id)
            answers_map = {
                q.order_num: raw_answers[q.question_id]
                for q in questions
                if q.question_id in raw_answers
            }
            attempt_payload = {
                "attempt_id": attempt.attempt_id,
                "deadline_at": attempt.deadline_at.isoformat() if attempt.deadline_at else None,
            }

        return web.json_response(
            {
                "ok": True,
                "test": {
                    "id": test.test_id,
                    "title": test.title,
                    "mode": test.mode,
                    "duration_min": test.duration_min,
                    "has_pdf": bool(test.pdf_file_id),
                },
                "questions": [
                    {
                        "order_num": q.order_num,
                        "qtype": q.qtype,
                        "option_count": q.option_count,
                        "label": q.label,
                    }
                    for q in questions
                    if not q.is_excluded
                ],
                "user": {"full_name": user.full_name},
                "attempt": attempt_payload,
                "answers": answers_map,
            }
        )
    finally:
        await session.close()


@routes.post("/api/attempt/start")
async def start_attempt(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        body = await request.json()
        test_id = int(body["test_id"])
        test = await get_test(session, test_id)
        if test is None or not await has_purchase(session, user.user_pk, test_id):
            return _json_error("Kirish huquqi yo'q.", 403)
        if test.mode == "jonli" and test.status != "jonli_davom":
            return _json_error("Test hali boshlanmagan yoki yakunlangan.", 409)

        from datetime import datetime, timedelta

        attempt = await get_attempt(session, user.user_pk, test_id)
        if attempt is None:
            deadline_at = datetime.now(settings.tzinfo) + timedelta(minutes=test.duration_min)
            attempt = await create_attempt(session, user.user_pk, test_id, kind=test.mode, deadline_at=deadline_at)
        elif attempt.status != "davom_etmoqda":
            return _json_error("Siz bu testni allaqachon yakunlagansiz.", 409)

        await touch_attempt(session, attempt.attempt_id)
        return web.json_response({"ok": True, "attempt_id": attempt.attempt_id})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


@routes.post("/api/heartbeat")
async def heartbeat(request: web.Request) -> web.Response:
    """Mini App ochiq ekanini bildiradi. Agar oldingi signaldan 5 daqiqadan ko'p
    o'tgan bo'lsa (ilova yopilgan/aloqa uzilgan), qoralama javoblar tozalanadi."""
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        body = await request.json()
        attempt_id = int(body["attempt_id"])

        from db.models import Attempt

        attempt = await session.get(Attempt, attempt_id)
        if attempt is None or attempt.user_pk != user.user_pk:
            return _json_error("Urinish topilmadi.", 404)
        if attempt.status != "davom_etmoqda":
            return web.json_response({"ok": True, "finished": True})

        cleared = await clear_stale_draft(session, attempt_id)
        await touch_attempt(session, attempt_id)
        return web.json_response({"ok": True, "cleared": cleared})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


@routes.post("/api/answer")
async def save_answer(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        body = await request.json()
        attempt_id = int(body["attempt_id"])
        order_num = int(body["order_num"])
        raw_answer = str(body["answer"]).strip()

        from db.models import Attempt

        attempt = await session.get(Attempt, attempt_id)
        if attempt is None or attempt.user_pk != user.user_pk:
            return _json_error("Urinish topilmadi.", 404)
        if attempt.status != "davom_etmoqda":
            return _json_error("Bu urinish allaqachon yakunlangan.", 409)

        await clear_stale_draft(session, attempt_id)
        questions = await get_questions_for_test(session, attempt.test_id)
        question = next((q for q in questions if q.order_num == order_num), None)
        if question is None:
            return _json_error("Savol topilmadi.", 404)

        if question.qtype == "yopiq":
            letter = raw_answer.upper()
            valid_letters = [chr(ord("A") + i) for i in range(question.option_count)]
            if letter not in valid_letters:
                return _json_error(f"Javob {'/'.join(valid_letters)} dan biri bo'lishi kerak.")
            await upsert_answer(session, attempt_id, question.question_id, letter)
        else:
            if not answer_input_ok(raw_answer):
                return _json_error("Javobni matematik ifoda sifatida yozing (12, 1/2, √2 kabi).")
            answer = normalize_open_answer(raw_answer)
            await upsert_answer(session, attempt_id, question.question_id, answer)

        await touch_attempt(session, attempt_id)
        return web.json_response({"ok": True})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


@routes.post("/api/finish")
async def finish(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        body = await request.json()
        attempt_id = int(body["attempt_id"])

        from db.models import Attempt

        attempt = await session.get(Attempt, attempt_id)
        if attempt is None or attempt.user_pk != user.user_pk:
            return _json_error("Urinish topilmadi.", 404)
        if attempt.status != "davom_etmoqda":
            return _json_error("Bu urinish allaqachon yakunlangan.", 409)

        await finish_attempt(session, attempt_id)
        test = await get_test(session, attempt.test_id)

        if test.mode == "arxiv":
            ball, grade, correct_orders, wrong_orders = await score_archive_attempt(session, attempt_id)
            bot = request.app["bot"]
            if bot is not None:
                task = asyncio.create_task(send_certificate(bot, user.telegram_id, attempt_id))
                request.app["tasks"].add(task)
                task.add_done_callback(request.app["tasks"].discard)
            return web.json_response(
                {
                    "ok": True,
                    "mode": "arxiv",
                    "attempt_id": attempt_id,
                    "ball_75": ball,
                    "grade": grade,
                    "breakdown": format_breakdown(
                        correct_orders, wrong_orders, await get_question_labels(session, attempt.test_id)
                    ),
                }
            )

        return web.json_response({"ok": True, "mode": "jonli"})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


# ---------------- O'quvchi: bosh sahifa / natijalar / profil ----------------


@routes.get("/api/my-tests")
async def my_tests(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        attempts = {a.test_id: a for a in await list_user_attempts(session, user.user_pk)}
        payload = []
        for t in await list_user_purchased_tests(session, user.user_pk):
            if t.status == "bekor_qilingan":
                continue
            attempt = attempts.get(t.test_id)
            finished = attempt is not None and attempt.status != "davom_etmoqda"
            can_enter = not finished and (t.mode == "arxiv" or t.status == "jonli_davom")
            payload.append(
                {
                    "id": t.test_id,
                    "title": t.title,
                    "mode": t.mode,
                    "status": t.status,
                    "finished": finished,
                    "can_enter": can_enter,
                    "ball_75": attempt.ball_75 if attempt else None,
                    "grade": attempt.grade if attempt else None,
                }
            )
        return web.json_response({"ok": True, "tests": payload})
    finally:
        await session.close()


@routes.get("/api/me")
async def me(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        results = []
        for a in await list_user_attempts(session, user.user_pk):
            if a.ball_75 is None:
                continue
            test = await get_test(session, a.test_id)
            results.append(
                {
                    "attempt_id": a.attempt_id,
                    "test_id": a.test_id,
                    "title": test.title if test else "-",
                    "ball_75": a.ball_75,
                    "grade": a.grade,
                    "rank": a.rank_position,
                    "date": a.started_at.strftime("%d.%m.%Y") if a.started_at else "",
                }
            )
        return web.json_response(
            {
                "ok": True,
                "user": {
                    "full_name": user.full_name,
                    "username": user.username,
                    "public_id": user.public_id,
                },
                "results": results,
            }
        )
    finally:
        await session.close()


@routes.get("/api/results")
async def results_list(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, _user = auth
    try:
        payload = []
        for t in await list_all_tests(session):
            if t.status in ("bekor_qilingan", "tayyorlanmoqda", "rejalashtirilgan", "jonli_davom"):
                continue
            rows = await list_attempts_with_users_for_export(session, t.test_id)
            scored = [r for r in rows if r[0].ball_75 is not None]
            if not scored:
                continue
            payload.append({"id": t.test_id, "title": t.title, "mode": t.mode, "participants": len(scored)})
        return web.json_response({"ok": True, "tests": payload})
    finally:
        await session.close()


@routes.get("/api/results/{test_id}")
async def results_detail(request: web.Request) -> web.Response:
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        test_id = int(request.match_info["test_id"])
        test = await get_test(session, test_id)
        if test is None or test.status in ("bekor_qilingan", "tayyorlanmoqda", "rejalashtirilgan", "jonli_davom"):
            return _json_error("Natijalar hali mavjud emas.", 404)

        rows = await list_attempts_with_users_for_export(session, test_id)
        results = [
            {
                "rank": a.rank_position,
                "full_name": u.full_name,
                "grade": a.grade,
                "ball_75": a.ball_75,
                "is_me": u.user_pk == user.user_pk,
            }
            for a, u in rows
            if a.ball_75 is not None
        ]
        grade_counts: dict[str, int] = {}
        for r in results:
            key = r["grade"] or "chegaradan past"
            grade_counts[key] = grade_counts.get(key, 0) + 1
        return web.json_response(
            {
                "ok": True,
                "test": {"id": test.test_id, "title": test.title},
                "participants": len(results),
                "grade_counts": grade_counts,
                "results": results,
            }
        )
    finally:
        await session.close()


@routes.post("/api/certificate")
async def certificate(request: web.Request) -> web.Response:
    """Natija sertifikatini (PDF) foydalanuvchining shaxsiy chatiga yuboradi."""
    auth = await _authenticate(request)
    if auth is None:
        return _json_error("Ro'yxatdan o'tmagansiz yoki sessiya eskirgan.", 401)
    session, user = auth
    try:
        body = await request.json()
        attempt_id = int(body["attempt_id"])

        from db.models import Attempt

        attempt = await session.get(Attempt, attempt_id)
        if attempt is None or attempt.user_pk != user.user_pk:
            return _json_error("Urinish topilmadi.", 404)
        if attempt.ball_75 is None:
            return _json_error("Natija hali e'lon qilinmagan.", 409)

        now = time.monotonic()
        if now - _cert_last_request.get(user.user_pk, -999) < 20:
            return _json_error("Iltimos, bir necha soniya kutib qayta urinib ko'ring.", 429)
        _cert_last_request[user.user_pk] = now

        bot = request.app["bot"]
        if bot is None or not await send_certificate(bot, user.telegram_id, attempt_id):
            return _json_error("Sertifikatni yuborib bo'lmadi. Botga /start yozib qayta urinib ko'ring.", 502)
        return web.json_response({"ok": True})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


# ---------------- Admin ----------------


@routes.get("/api/admin/tests")
async def admin_list_tests(request: web.Request) -> web.Response:
    auth = await _authenticate_admin(request)
    if auth is None:
        return _json_error("Ruxsat yo'q.", 403)
    session, _user = auth
    try:
        tests = await list_all_tests(session)
        payload = []
        for t in tests:
            rows = await list_attempts_with_users_for_export(session, t.test_id)
            payload.append(
                {
                    "id": t.test_id,
                    "title": t.title,
                    "mode": t.mode,
                    "status": t.status,
                    "participants": len(rows),
                }
            )
        return web.json_response({"ok": True, "tests": payload})
    finally:
        await session.close()


@routes.get("/api/admin/tests/{test_id}")
async def admin_test_results(request: web.Request) -> web.Response:
    auth = await _authenticate_admin(request)
    if auth is None:
        return _json_error("Ruxsat yo'q.", 403)
    session, _user = auth
    try:
        test_id = int(request.match_info["test_id"])
        test = await get_test(session, test_id)
        if test is None:
            return _json_error("Test topilmadi.", 404)

        rows = await list_attempts_with_users_for_export(session, test_id)
        results = [
            {
                "rank": attempt.rank_position,
                "public_id": user.public_id,
                "full_name": user.full_name,
                "username": user.username,
                "telegram_id": user.telegram_id,
                "kind": attempt.kind,
                "status": attempt.status,
                "ball_75": attempt.ball_75,
                "grade": attempt.grade,
            }
            for attempt, user in rows
        ]

        grade_counts: dict[str, int] = {}
        for r in results:
            key = r["grade"] or "chegaradan past"
            grade_counts[key] = grade_counts.get(key, 0) + 1

        return web.json_response(
            {
                "ok": True,
                "test": {"id": test.test_id, "title": test.title, "status": test.status, "mode": test.mode},
                "participants": len(results),
                "grade_counts": grade_counts,
                "results": results,
            }
        )
    finally:
        await session.close()


@routes.post("/api/admin/tests/{test_id}/export")
async def admin_export_excel(request: web.Request) -> web.Response:
    auth = await _authenticate_admin(request)
    if auth is None:
        return _json_error("Ruxsat yo'q.", 403)
    session, user = auth
    try:
        test_id = int(request.match_info["test_id"])
        test = await get_test(session, test_id)
        if test is None:
            return _json_error("Test topilmadi.", 404)

        rows = await list_attempts_with_users_for_export(session, test_id)
        if not rows:
            return _json_error("Bu testda hali ishtirokchi yo'q.", 404)

        excel_bytes = build_results_excel(test.title, rows)
        safe_title = "".join(c if c.isalnum() else "_" for c in test.title)[:40]
        bot = request.app["bot"]
        await bot.send_document(
            user.telegram_id,
            BufferedInputFile(excel_bytes, filename=f"{safe_title}_natijalar.xlsx"),
            caption=f"📊 \"{test.title}\" — {len(rows)} ta ishtirokchi natijasi.",
        )
        return web.json_response({"ok": True})
    finally:
        await session.close()


def create_webapp_app(bot=None) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["tasks"] = set()
    app.add_routes(routes)
    return app


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                count = await clear_all_stale_drafts(session)
            if count:
                logger.info("Eskirgan qoralamalar tozalandi: %d ta urinish", count)
        except Exception:
            logger.warning("Qoralama tozalash xatosi", exc_info=True)


async def start_webapp_server(bot, host: str = "127.0.0.1", port: int = 8080) -> web.AppRunner:
    app = create_webapp_app(bot)
    app["cleanup_task"] = asyncio.create_task(_cleanup_loop())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Mini App API ishga tushdi: http://%s:%s", host, port)
    return runner
