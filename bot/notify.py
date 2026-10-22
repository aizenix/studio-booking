"""Sending Telegram messages from sync code (Celery tasks, Django admin)."""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile
from django.conf import settings

from .admin_chat import send_for_review

logger = logging.getLogger(__name__)


def _run(send):
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set, Telegram message skipped")
        return

    async def main():
        async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
            await send(bot)

    asyncio.run(main())


def send_messages(messages):
    """Send (chat_id, text) pairs in one bot session. One failed chat does not stop the rest."""

    async def send(bot):
        for chat_id, text in messages:
            try:
                await bot.send_message(chat_id, text)
            except Exception:
                logger.warning("Could not send message to %s", chat_id, exc_info=True)

    if messages:
        _run(send)


def send_receipt_for_review(booking):
    with booking.receipt.open("rb") as receipt:
        photo = BufferedInputFile(receipt.read(), filename=Path(booking.receipt.name).name)
    _run(lambda bot: send_for_review(bot, booking, photo))
