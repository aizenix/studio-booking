import logging

from celery import shared_task

from bot import notify
from bot.formatting import status_message

from . import services
from .models import Booking

logger = logging.getLogger(__name__)


@shared_task
def expire_unpaid_bookings():
    expired = services.expire_unpaid_bookings()
    if not expired:
        return 0
    logger.info("Expired unpaid bookings: %s", expired)
    bookings = Booking.objects.filter(pk__in=expired, telegram_id__isnull=False).select_related(
        "master", "service"
    )
    notify.send_messages([(b.telegram_id, status_message(b)) for b in bookings])
    return len(expired)


@shared_task
def send_status_notification(booking_id):
    booking = Booking.objects.select_related("master", "service").get(pk=booking_id)
    if booking.telegram_id:
        notify.send_messages([(booking.telegram_id, status_message(booking))])


@shared_task
def send_receipt_for_review(booking_id):
    booking = Booking.objects.select_related("master", "service").get(pk=booking_id)
    notify.send_receipt_for_review(booking)
