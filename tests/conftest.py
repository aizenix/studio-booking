import datetime as dt

import pytest
from django.utils import timezone

from booking.models import Booking, Master, Service, WorkingHours


@pytest.fixture(autouse=True)
def _local_cache(settings):
    # Throttling hits the cache on every request, tests should not need Redis.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.fixture
def service(db):
    return Service.objects.create(
        name="Small tattoo", duration_minutes=60, price=600_000, deposit=150_000
    )


@pytest.fixture
def master(db, service):
    master = Master.objects.create(name="Aziza")
    master.services.add(service)
    for weekday in range(6):
        WorkingHours.objects.create(
            master=master, weekday=weekday, start_time=dt.time(10), end_time=dt.time(20)
        )
    return master


@pytest.fixture
def day():
    """Next Monday: always in the future and inside the booking horizon."""
    today = timezone.localdate()
    return today + dt.timedelta(days=7 - today.weekday())


@pytest.fixture
def at(day):
    def build(hour, minute=0):
        return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))

    return build


@pytest.fixture
def make_booking(master, service):
    def factory(starts_at, *, status=Booking.Status.CONFIRMED, **extra):
        extra.setdefault("master", master)
        extra.setdefault("service", service)
        return Booking.objects.create(
            starts_at=starts_at,
            ends_at=starts_at + extra["service"].duration,
            client_name="Dilnoza",
            phone="+998901234567",
            source=Booking.Source.WEB,
            deposit_amount=extra["service"].deposit,
            status=status,
            **extra,
        )

    return factory
