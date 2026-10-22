import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bot.dispatcher import run_polling


class Command(BaseCommand):
    help = "Run the Telegram bot (long polling)."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set")
        asyncio.run(run_polling())
