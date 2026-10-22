import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from django.conf import settings

from .handlers import booking, my_bookings, review
from .middlewares import DbConnectionMiddleware

logger = logging.getLogger(__name__)


def build_dispatcher():
    dispatcher = Dispatcher(storage=RedisStorage.from_url(settings.REDIS_URL))
    dispatcher.update.outer_middleware(DbConnectionMiddleware())
    # booking.router goes last: it ends with a catch-all for outdated buttons.
    dispatcher.include_routers(review.router, my_bookings.router, booking.router)
    return dispatcher


async def run_polling():
    bot = Bot(settings.TELEGRAM_BOT_TOKEN)
    dispatcher = build_dispatcher()
    await bot.set_my_commands(
        [
            BotCommand(command="book", description="Book a session"),
            BotCommand(command="my", description="My bookings"),
            BotCommand(command="cancel", description="Stop the current booking"),
        ]
    )
    logger.info("Starting bot polling")
    await dispatcher.start_polling(bot)
