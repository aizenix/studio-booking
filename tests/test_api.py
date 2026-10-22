import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import Booking, Master

pytestmark = pytest.mark.django_db

Status = Booking.Status


@pytest.fixture
def api():
    return APIClient()


def booking_payload(master, service, starts_at, **overrides):
    return {
        "master": master.pk,
        "service": service.pk,
        "starts_at": starts_at.isoformat(),
        "client_name": "Malika",
        "phone": "+998 90 111 22 33",
        **overrides,
    }


def test_services_and_masters_are_listed(api, master, service):
    Master.objects.create(name="Timur")

    services = api.get("/api/services/").json()
    masters = api.get("/api/masters/", {"service": service.pk}).json()

    assert [s["name"] for s in services] == ["Small tattoo"]
    assert [m["name"] for m in masters] == ["Aziza"]


def test_availability_lists_free_slots(api, master, service, day, at, make_booking):
    make_booking(at(13))

    response = api.get(
        "/api/availability/", {"master": master.pk, "service": service.pk, "date": day}
    )

    assert response.status_code == 200
    slots = response.json()["slots"]
    assert slots[0] == at(10).isoformat()
    assert at(13).isoformat() not in slots


def test_create_booking_from_website(api, master, service, at):
    response = api.post("/api/bookings/", booking_payload(master, service, at(15)), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == Status.PENDING_DEPOSIT
    assert body["deposit_amount"] == service.deposit
    booking = Booking.objects.get(code=body["code"])
    assert booking.source == Booking.Source.WEB
    assert booking.phone == "+998901112233"
    assert booking.telegram_id is None


def test_create_booking_on_taken_slot_returns_409(api, master, service, at, make_booking):
    make_booking(at(15))

    response = api.post(
        "/api/bookings/", booking_payload(master, service, at(15, 30)), format="json"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "This time is no longer available."
    assert Booking.objects.count() == 1


def test_create_booking_validates_master_and_service(api, master, service, at):
    other = Master.objects.create(name="Timur")

    response = api.post("/api/bookings/", booking_payload(other, service, at(15)), format="json")

    assert response.status_code == 400


def test_receipt_upload(api, make_booking, at, receipt_image):
    booking = make_booking(
        at(15),
        status=Status.PENDING_DEPOSIT,
        deposit_deadline=timezone.now() + dt.timedelta(minutes=20),
    )

    response = api.post(f"/api/bookings/{booking.code}/receipt/", {"receipt": receipt_image})

    assert response.status_code == 200
    assert response.json()["status"] == Status.AWAITING_CONFIRMATION


def test_receipt_upload_for_expired_booking_returns_409(api, make_booking, at, receipt_image):
    booking = make_booking(at(15), status=Status.EXPIRED)

    response = api.post(f"/api/bookings/{booking.code}/receipt/", {"receipt": receipt_image})

    assert response.status_code == 409


def test_healthz(api):
    response = api.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
