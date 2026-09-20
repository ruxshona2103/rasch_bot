"""🆕 Mini App uchun backend API. Botning o'zi bilan BIR jarayonda ishlaydi
(alohida konteyner/server emas) -- xotira tejash uchun. Faqat localhost'da
tinglaydi (127.0.0.1:8080), tashqi dunyoga Caddy orqali /api/* sifatida
ochiladi (webapp_domain/api/...).

Autentifikatsiya: har so'rov "Authorization: tma <initData>" sarlavhasi bilan
keladi, initData core.webapp_auth.validate_init_data orqali HMAC bilan
tekshiriladi -- shu orqali foydalanuvchi Telegram ID'si xavfsiz aniqlanadi
(parolsiz, tokensiz -- Telegram Mini App'ning rasmiy usuli).
"""

import json
import logging

from aiohttp import web

from bot.config import settings
from core.answer_key import is_valid_numeric_answer, normalize_open_answer
from core.rasch import format_breakdown, score_archive_attempt
from core.webapp_auth import validate_init_data
from db.engine import async_session
from db.queries import (
    create_attempt,
    finish_attempt,
    get_answers_map,
    get_attempt,
    get_questions_for_test,
    get_test,
    get_user_by_telegram_id,
    has_purchase,
    upsert_answer,
)

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()


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
                        "finished": True,
                    }
                )
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
                    }
                    for q in questions
                    if not q.is_excluded
                ],
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

        return web.json_response({"ok": True, "attempt_id": attempt.attempt_id})
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
            if not is_valid_numeric_answer(raw_answer):
                return _json_error("Javobni matematik ifoda sifatida yozing (12, 1/2, √2 kabi).")
            answer = normalize_open_answer(raw_answer)
            await upsert_answer(session, attempt_id, question.question_id, answer)

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
            return web.json_response(
                {
                    "ok": True,
                    "mode": "arxiv",
                    "ball_75": ball,
                    "grade": grade,
                    "breakdown": format_breakdown(correct_orders, wrong_orders),
                }
            )

        return web.json_response({"ok": True, "mode": "jonli"})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _json_error("Noto'g'ri so'rov.")
    finally:
        await session.close()


def create_webapp_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app


async def start_webapp_server(host: str = "127.0.0.1", port: int = 8080) -> web.AppRunner:
    app = create_webapp_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Mini App API ishga tushdi: http://%s:%s", host, port)
    return runner
