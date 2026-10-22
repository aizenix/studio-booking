import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from bot import notify
from bot.formatting import reminder_text, status_message

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


def _claim(booking, **flags):
    # Conditional update so that two overlapping runs never remind twice.
    unclaimed = {field: False for field in flags}
    return Booking.objects.filter(pk=booking.pk, **unclaimed).update(**flags) == 1


@shared_task
def send_reminders():
    now = timezone.now()
    upcoming = Booking.objects.filter(
        status=Booking.Status.CONFIRMED, telegram_id__isnull=False, starts_at__gt=now
    ).select_related("master", "service")
    messages = []

    for booking in upcoming.filter(reminded_2h=False, starts_at__lte=now + timedelta(hours=2)):
        if _claim(booking, reminded_2h=True):
            messages.append((booking.telegram_id, reminder_text(booking)))

    # Bookings made less than a day ahead skip the 24h reminder.
    day_ahead = upcoming.filter(
        reminded_24h=False,
        starts_at__gt=now + timedelta(hours=2),
        starts_at__lte=now + timedelta(hours=24),
        created_at__lte=F("starts_at") - timedelta(hours=24),
    )
    for booking in day_ahead:
        if _claim(booking, reminded_24h=True):
            messages.append((booking.telegram_id, reminder_text(booking)))

    notify.send_messages(messages)
    return len(messages)
