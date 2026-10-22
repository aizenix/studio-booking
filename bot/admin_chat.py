import logging

from django.conf import settings

from .formatting import review_caption
from .keyboards import review_keyboard

logger = logging.getLogger(__name__)


async def send_for_review(bot, booking, photo):
    """Post the receipt to the studio chat with Approve/Reject buttons.

    `photo` is a Telegram file_id or an aiogram InputFile.
    """
    if not settings.TELEGRAM_ADMIN_CHAT_ID:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID is not set, booking #%s not sent", booking.pk)
        return
    await bot.send_photo(
        settings.TELEGRAM_ADMIN_CHAT_ID,
        photo,
        caption=review_caption(booking),
        reply_markup=review_keyboard(booking.pk),
    )


async def notify_admins(bot, text):
    if not settings.TELEGRAM_ADMIN_CHAT_ID:
        return
    await bot.send_message(settings.TELEGRAM_ADMIN_CHAT_ID, text)
