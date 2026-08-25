from aiogram import Bot

from bot.config import settings

_SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}


async def is_subscribed(bot: Bot, telegram_id: int) -> bool:
    if settings.SKIP_CHANNEL_CHECK:
        # 🧪 VAQTINCHALIK bypass — bot_config.SKIP_CHANNEL_CHECK izohiga qarang
        return True
    try:
        member = await bot.get_chat_member(chat_id=settings.CHANNEL_ID, user_id=telegram_id)
    except Exception:
        # kanal topilmadi / bot admin emas / user hech qachon botga tegmagan va h.k.
        return False
    return member.status in _SUBSCRIBED_STATUSES
