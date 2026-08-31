import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import settings
from bot.handlers.admin import appeals as admin_appeals
from bot.handlers.admin import broadcast as admin_broadcast
from bot.handlers.admin import panel as admin_panel
from bot.handlers.admin import payments as admin_payments
from bot.handlers.admin import question_edit as admin_question_edit
from bot.handlers.admin import stats as admin_stats
from bot.handlers.admin import test_create as admin_test_create
from bot.handlers.admin import test_manage as admin_test_manage
from bot.handlers.user import appeal, cabinet, exam, registration
from bot.handlers.user import tests_list
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.nav_reset import NavigationResetMiddleware
from core.scheduler import create_scheduler, recover_all_jobs

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(NavigationResetMiddleware())

    dp.include_router(admin_test_create.router)
    dp.include_router(admin_payments.router)
    dp.include_router(admin_test_manage.router)
    dp.include_router(admin_question_edit.router)
    dp.include_router(admin_appeals.router)
    dp.include_router(admin_stats.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_panel.router)
    dp.include_router(registration.router)
    dp.include_router(tests_list.router)
    dp.include_router(exam.router)
    dp.include_router(appeal.router)
    dp.include_router(cabinet.router)

    scheduler = create_scheduler()
    await recover_all_jobs(scheduler, bot)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, scheduler=scheduler)


if __name__ == "__main__":
    asyncio.run(main())
