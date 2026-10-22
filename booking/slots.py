from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import ACTIVE_STATUSES, Booking, TimeOff, WorkingHours


def compute_slots(open_at, close_at, duration, step, busy, not_before=None):
    """Start times in [open_at, close_at) where `duration` fits without touching `busy`."""
    slots = []
    start = open_at
    while start + duration <= close_at:
        end = start + duration
        is_free = all(end <= busy_start or start >= busy_end for busy_start, busy_end in busy)
        if is_free and (not_before is None or start >= not_before):
            slots.append(start)
        start += step
    return slots


def get_available_slots(master, service, day, *, now=None, step_minutes=None):
    """Free start times for `service` with `master` on a local `day`.

    The website API and the bot both go through this function, so the rules
    (working hours, time off, notice period, horizon) live in one place.
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    if not today <= day < today + timedelta(days=settings.BOOKING_HORIZON_DAYS):
        return []

    hours = WorkingHours.objects.filter(master=master, weekday=day.weekday()).first()
    if hours is None:
        return []

    tz = timezone.get_current_timezone()
    open_at = datetime.combine(day, hours.start_time, tzinfo=tz)
    close_at = datetime.combine(day, hours.end_time, tzinfo=tz)

    bookings = Booking.objects.filter(
        master=master,
        status__in=ACTIVE_STATUSES,
        starts_at__lt=close_at,
        ends_at__gt=open_at,
    ).values_list("starts_at", "ends_at")
    time_off = TimeOff.objects.filter(
        master=master, starts_at__lt=close_at, ends_at__gt=open_at
    ).values_list("starts_at", "ends_at")

    step = timedelta(minutes=step_minutes or settings.SLOT_STEP_MINUTES)
    not_before = now + timedelta(minutes=settings.BOOKING_MIN_NOTICE_MINUTES)
    return compute_slots(
        open_at, close_at, service.duration, step, [*bookings, *time_off], not_before
    )


def get_available_days(master, service, start, days, *, now=None):
    candidates = (start + timedelta(days=offset) for offset in range(days))
    return [day for day in candidates if get_available_slots(master, service, day, now=now)]
