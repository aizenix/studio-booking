import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from django.conf import settings

from booking.services import InvalidTransition, aapprove_booking, areject_booking

from ..callbacks import ReviewCb
from ..formatting import status_message

logger = logging.getLogger(__name__)

router = Router(name="review")
router.callback_query.filter(F.message.chat.id == settings.TELEGRAM_ADMIN_CHAT_ID)


@router.callback_query(ReviewCb.filter(F.action.in_({"approve", "reject"})))
async def review_receipt(callback: CallbackQuery, callback_data: ReviewCb, bot: Bot):
    approve = callback_data.action == "approve"
    action = aapprove_booking if approve else areject_booking
    try:
        booking = await action(callback_data.booking_id)
    except InvalidTransition as exc:
        status = exc.booking.get_status_display().lower()
        await callback.answer(f"Already {status}.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    verdict = "Approved" if approve else "Rejected"
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n{verdict} by {callback.from_user.full_name}",
        reply_markup=None,
    )
    await callback.answer(verdict)

    if booking.telegram_id:
        try:
            await bot.send_message(booking.telegram_id, status_message(booking))
        except TelegramAPIError:
            logger.warning("Could not notify client about booking #%s", booking.pk, exc_info=True)
