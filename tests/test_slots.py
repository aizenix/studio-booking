import datetime as dt

import pytest
from django.utils import timezone

from booking.models import Booking, Service, TimeOff
from booking.slots import get_available_days, get_available_slots

pytestmark = pytest.mark.django_db


def hhmm(slots):
    return [timezone.localtime(slot).strftime("%H:%M") for slot in slots]


def test_slots_cover_working_hours_with_step(master, service, day):
    labels = hhmm(get_available_slots(master, service, day))

    assert labels[0] == "10:00"
    assert labels[1] == "10:30"
    assert labels[-1] == "19:00"
    assert len(labels) == 19


def test_last_slot_ends_exactly_at_closing_time(master, day):
    long_session = Service.objects.create(
        name="Sleeve session", duration_minutes=150, price=2_000_000, deposit=400_000
    )

    labels = hhmm(get_available_slots(master, long_session, day))

    assert labels[-1] == "17:30"
    assert "18:00" not in labels


def test_active_booking_blocks_overlapping_slots(master, service, day, at, make_booking):
    make_booking(at(13), status=Booking.Status.PENDING_DEPOSIT)

    labels = hhmm(get_available_slots(master, service, day))

    assert {"12:30", "13:00", "13:30"}.isdisjoint(labels)
    assert "12:00" in labels
    assert "14:00" in labels


def test_cancelled_and_expired_bookings_do_not_block(master, service, day, at, make_booking):
    make_booking(at(13), status=Booking.Status.CANCELLED)
    make_booking(at(13), status=Booking.Status.EXPIRED)

    assert "13:00" in hhmm(get_available_slots(master, service, day))


def test_time_off_blocks_part_of_the_day(master, service, day, at):
    TimeOff.objects.create(master=master, starts_at=at(15), ends_at=at(17))

    labels = hhmm(get_available_slots(master, service, day))

    assert "14:00" in labels
    assert {"14:30", "15:00", "16:30"}.isdisjoint(labels)
    assert "17:00" in labels


def test_slots_respect_minimum_notice(master, service, day, at, settings):
    settings.BOOKING_MIN_NOTICE_MINUTES = 60

    labels = hhmm(get_available_slots(master, service, day, now=at(12, 10)))

    assert labels[0] == "13:30"


def test_no_slots_outside_booking_horizon(master, service, day):
    assert get_available_slots(master, service, day - dt.timedelta(days=14)) == []
    assert get_available_slots(master, service, day + dt.timedelta(days=14)) == []


def test_available_days_skip_days_off_and_full_days(master, service, day, at):
    wednesday = day + dt.timedelta(days=2)
    TimeOff.objects.create(
        master=master,
        starts_at=at(0) + dt.timedelta(days=2),
        ends_at=at(0) + dt.timedelta(days=3),
    )

    days = get_available_days(master, service, day, 7)

    # Sunday has no working hours, Wednesday is a full day off
    assert days == [day + dt.timedelta(days=n) for n in (0, 1, 3, 4, 5)]
    assert get_available_slots(master, service, wednesday) == []
