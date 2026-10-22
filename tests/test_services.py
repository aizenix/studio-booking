import datetime as dt

import pytest
from django.utils import timezone

from booking import services
from booking.models import Booking
from booking.validators import normalize_phone

pytestmark = pytest.mark.django_db

Status = Booking.Status


def book(master, service, starts_at, **extra):
    return services.create_booking(
        master=master,
        service=service,
        starts_at=starts_at,
        client_name="Kamola",
        phone="+998935554433",
        source=Booking.Source.BOT,
        telegram_id=1001,
        **extra,
    )


def test_create_booking_fills_end_time_and_deposit(master, service, at, settings):
    settings.DEPOSIT_TIMEOUT_MINUTES = 30
    before = timezone.now()

    booking = book(master, service, at(12))

    assert booking.status == Status.PENDING_DEPOSIT
    assert booking.ends_at == at(13)
    assert booking.deposit_amount == service.deposit
    deadline_delay = booking.deposit_deadline - before
    assert dt.timedelta(minutes=30) <= deadline_delay < dt.timedelta(minutes=30, seconds=5)


def test_create_booking_turns_constraint_violation_into_slot_unavailable(
    master, service, at, make_booking, monkeypatch
):
    make_booking(at(12))
    # Simulate a stale availability check: the slot looked free a moment ago.
    monkeypatch.setattr(services, "get_available_slots", lambda *args, **kwargs: [at(12)])

    with pytest.raises(services.SlotUnavailable):
        book(master, service, at(12))
    assert Booking.objects.count() == 1


def test_attach_receipt_waits_for_confirmation(make_booking, at, receipt_image):
    booking = make_booking(
        at(12),
        status=Status.PENDING_DEPOSIT,
        deposit_deadline=timezone.now() + dt.timedelta(minutes=10),
    )

    booking = services.attach_receipt(booking.pk, receipt_image)

    assert booking.status == Status.AWAITING_CONFIRMATION
    assert booking.receipt.name == f"receipts/{booking.code}.png"


def test_attach_receipt_after_deadline_is_refused(make_booking, at, receipt_image):
    booking = make_booking(
        at(12),
        status=Status.PENDING_DEPOSIT,
        deposit_deadline=timezone.now() - dt.timedelta(minutes=1),
    )

    with pytest.raises(services.DepositWindowClosed):
        services.attach_receipt(booking.pk, receipt_image)
    booking.refresh_from_db()
    assert booking.status == Status.PENDING_DEPOSIT
    assert not booking.receipt


def test_approve_confirms_booking(make_booking, at):
    booking = make_booking(at(12), status=Status.AWAITING_CONFIRMATION)

    assert services.approve_booking(booking.pk).status == Status.CONFIRMED


def test_reject_cancels_booking_and_frees_the_slot(master, service, make_booking, at):
    booking = make_booking(at(12), status=Status.AWAITING_CONFIRMATION)

    assert services.reject_booking(booking.pk).status == Status.CANCELLED
    assert book(master, service, at(12)).status == Status.PENDING_DEPOSIT


def test_expired_booking_cannot_be_approved(make_booking, at):
    booking = make_booking(at(12), status=Status.EXPIRED)

    with pytest.raises(services.InvalidTransition):
        services.approve_booking(booking.pk)


def test_normalize_phone():
    assert normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("90 123 45 67") == "+998901234567"
    assert normalize_phone("12345") is None
    assert normalize_phone("call me") is None
