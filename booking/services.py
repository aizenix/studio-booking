from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ACTIVE_STATUSES, Booking
from .slots import get_available_slots

Status = Booking.Status


class BookingError(Exception):
    pass


class SlotUnavailable(BookingError):
    pass


class DepositWindowClosed(BookingError):
    pass


class InvalidTransition(BookingError):
    def __init__(self, booking, target):
        self.booking = booking
        super().__init__(f"booking #{booking.pk} is {booking.status}, cannot move to {target}")


def create_booking(
    *, master, service, starts_at, client_name, phone, source, telegram_id=None
) -> Booking:
    if starts_at not in get_available_slots(master, service, timezone.localdate(starts_at)):
        raise SlotUnavailable

    deadline = timezone.now() + timedelta(minutes=settings.DEPOSIT_TIMEOUT_MINUTES)
    try:
        with transaction.atomic():
            return Booking.objects.create(
                master=master,
                service=service,
                starts_at=starts_at,
                ends_at=starts_at + service.duration,
                client_name=client_name,
                phone=phone,
                telegram_id=telegram_id,
                source=source,
                deposit_amount=service.deposit,
                deposit_deadline=deadline,
            )
    except IntegrityError as exc:
        # Two clients passed the availability check at the same time,
        # the exclusion constraint lets only one of them in.
        if "booking_no_overlap" not in str(exc):
            raise
        raise SlotUnavailable from exc


def _get_locked(booking_id):
    return (
        Booking.objects.select_related("master", "service")
        .select_for_update(of=("self",))
        .get(pk=booking_id)
    )


def _transition(booking_id, allowed, target):
    with transaction.atomic():
        booking = _get_locked(booking_id)
        if booking.status not in allowed:
            raise InvalidTransition(booking, target)
        booking.status = target
        booking.save(update_fields=["status", "updated_at"])
    return booking


def attach_receipt(booking_id, file) -> Booking:
    with transaction.atomic():
        booking = _get_locked(booking_id)
        if booking.status != Status.PENDING_DEPOSIT:
            raise InvalidTransition(booking, Status.AWAITING_CONFIRMATION)
        if booking.deposit_deadline and booking.deposit_deadline <= timezone.now():
            raise DepositWindowClosed
        booking.receipt.save(file.name, file, save=False)
        booking.status = Status.AWAITING_CONFIRMATION
        booking.save(update_fields=["receipt", "status", "updated_at"])
    return booking


def approve_booking(booking_id) -> Booking:
    return _transition(
        booking_id, {Status.PENDING_DEPOSIT, Status.AWAITING_CONFIRMATION}, Status.CONFIRMED
    )


def reject_booking(booking_id) -> Booking:
    return _transition(
        booking_id, {Status.PENDING_DEPOSIT, Status.AWAITING_CONFIRMATION}, Status.CANCELLED
    )


def cancel_booking(booking_id) -> Booking:
    return _transition(booking_id, set(ACTIVE_STATUSES), Status.CANCELLED)


def expire_unpaid_bookings(now=None) -> list[int]:
    now = now or timezone.now()
    with transaction.atomic():
        # skip_locked: a receipt upload holding the row wins over expiry.
        ids = list(
            Booking.objects.select_for_update(skip_locked=True)
            .filter(status=Status.PENDING_DEPOSIT, deposit_deadline__lte=now)
            .values_list("pk", flat=True)
        )
        if ids:
            Booking.objects.filter(pk__in=ids).update(status=Status.EXPIRED, updated_at=now)
    return ids


# The async ORM does not support transactions yet, so the bot goes through these wrappers.
acreate_booking = sync_to_async(create_booking)
aattach_receipt = sync_to_async(attach_receipt)
aapprove_booking = sync_to_async(approve_booking)
areject_booking = sync_to_async(reject_booking)
acancel_booking = sync_to_async(cancel_booking)
