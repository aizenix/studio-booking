import pytest
from django.db import IntegrityError, transaction

from booking.models import Booking, Master

pytestmark = pytest.mark.django_db


def test_overlapping_active_bookings_are_rejected(make_booking, at):
    make_booking(at(12))

    with pytest.raises(IntegrityError), transaction.atomic():
        make_booking(at(12, 30), status=Booking.Status.PENDING_DEPOSIT)


def test_back_to_back_bookings_are_allowed(make_booking, at):
    make_booking(at(12))
    make_booking(at(13))

    assert Booking.objects.count() == 2


def test_cancelled_and_expired_bookings_do_not_hold_the_slot(make_booking, at):
    make_booking(at(12), status=Booking.Status.CANCELLED)
    make_booking(at(12), status=Booking.Status.EXPIRED)
    make_booking(at(12))

    assert Booking.objects.filter(status=Booking.Status.CONFIRMED).count() == 1


def test_different_masters_can_book_the_same_time(make_booking, at, service):
    other = Master.objects.create(name="Timur")
    make_booking(at(12))
    make_booking(at(12), master=other)

    assert Booking.objects.count() == 2


def test_cannot_reactivate_booking_into_taken_slot(make_booking, at):
    cancelled = make_booking(at(12), status=Booking.Status.CANCELLED)
    make_booking(at(12))

    cancelled.status = Booking.Status.CONFIRMED
    with pytest.raises(IntegrityError), transaction.atomic():
        cancelled.save()
