import datetime as dt

import pytest
from django.utils import timezone

from booking import tasks
from booking.models import Booking
from booking.slots import get_available_slots

pytestmark = pytest.mark.django_db

Status = Booking.Status


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(tasks.notify, "send_messages", messages.extend)
    return messages


def test_expire_task_releases_overdue_unpaid_bookings(master, service, day, at, make_booking, sent):
    now = timezone.now()
    overdue = make_booking(
        at(12),
        status=Status.PENDING_DEPOSIT,
        telegram_id=555,
        deposit_deadline=now - dt.timedelta(minutes=1),
    )
    fresh = make_booking(
        at(14), status=Status.PENDING_DEPOSIT, deposit_deadline=now + dt.timedelta(minutes=20)
    )
    with_receipt = make_booking(
        at(16),
        status=Status.AWAITING_CONFIRMATION,
        deposit_deadline=now - dt.timedelta(minutes=5),
    )

    assert tasks.expire_unpaid_bookings() == 1

    overdue.refresh_from_db()
    fresh.refresh_from_db()
    with_receipt.refresh_from_db()
    assert overdue.status == Status.EXPIRED
    assert fresh.status == Status.PENDING_DEPOSIT
    assert with_receipt.status == Status.AWAITING_CONFIRMATION
    assert at(12) in get_available_slots(master, service, day)
    assert [chat_id for chat_id, _ in sent] == [555]
    assert "was not received in time" in sent[0][1]
