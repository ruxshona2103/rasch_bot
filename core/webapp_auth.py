"""🆕 Mini App uchun Telegram WebApp `initData`ni xavfsiz tekshirish.
Rasmiy algoritm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

_MAX_AUTH_AGE_SECONDS = 24 * 60 * 60  # 24 soat -- eski (o'g'irlangan) initData qayta ishlatilmasin


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """initData to'g'ri va yangi bo'lsa, undagi maydonlarni dict qilib qaytaradi
    (jumladan "user" -> allaqachon json.loads qilingan dict). Noto'g'ri/eski
    bo'lsa None qaytaradi."""
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = parsed.get("auth_date")
    if not auth_date or not auth_date.isdigit():
        return None
    if time.time() - int(auth_date) > _MAX_AUTH_AGE_SECONDS:
        return None

    if "user" in parsed:
        try:
            parsed["user"] = json.loads(parsed["user"])
        except (json.JSONDecodeError, TypeError):
            return None

    return parsed
