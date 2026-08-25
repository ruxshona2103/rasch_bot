"""Asosiy menyu/panel tugmalaridan biri bosilsa, faol FSM holatini avtomatik
tozalaydi. Aks holda foydalanuvchi bir bosqichli so'rov (masalan "raqam kiriting")
o'rtasida boshqa tugma bossa, bot uni "noto'g'ri kiritildi" deb qabul qilib,
foydalanuvchi hech qayerga chiqolmay qolar edi.
"""

from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

NAV_TEXTS = {
    "/start",
    "/admin",
    "/cancel",
    "➕ Yangi test",
    "📋 Testlar",
    "💳 To'lovlar",
    "✉️ Apellyatsiyalar",
    "📊 Statistika",
    "📢 E'lon yuborish",
    "⬅️ Foydalanuvchi rejimiga qaytish",
    "🔴 Jonli testlar",
    "📚 Arxiv testlar",
    "👤 Kabinetim",
    "📊 Natijalarim",
    "🎥 Video yechimlar",
    "ℹ️ Yordam / Aloqa",
}


class NavigationResetMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict) -> Any:
        text = getattr(event, "text", None)
        state = data.get("state")
        if text in NAV_TEXTS and state is not None:
            current = await state.get_state()
            if current is not None:
                await state.clear()
        return await handler(event, data)
