import uuid
from datetime import timedelta
from pathlib import Path

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField()
    price = models.PositiveIntegerField()
    deposit = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def duration(self):
        return timedelta(minutes=self.duration_minutes)


class Master(models.Model):
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    services = models.ManyToManyField(Service, related_name="masters", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name_plural = "working hours"
        ordering = ["master", "weekday"]
        constraints = [
            models.UniqueConstraint(fields=["master", "weekday"], name="one_schedule_per_weekday"),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="working_hours_end_after_start"
            ),
        ]

    def __str__(self):
        hours = f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        return f"{self.master} {self.get_weekday_display()} {hours}"


class TimeOff(models.Model):
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name="time_off")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "time off"
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="time_off_end_after_start"
            ),
        ]

    def __str__(self):
        return f"{self.master}: {self.starts_at:%Y-%m-%d %H:%M} - {self.ends_at:%Y-%m-%d %H:%M}"


def receipt_upload_to(instance, filename):
    ext = Path(filename).suffix.lower() or ".jpg"
    return f"receipts/{instance.code}{ext}"


class BookingStatus(models.TextChoices):
    PENDING_DEPOSIT = "pending_deposit", "Pending deposit"
    AWAITING_CONFIRMATION = "awaiting_confirmation", "Awaiting confirmation"
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


# Statuses that hold the slot, both for slot calculation and for the exclusion constraint.
ACTIVE_STATUSES = [
    BookingStatus.PENDING_DEPOSIT,
    BookingStatus.AWAITING_CONFIRMATION,
    BookingStatus.CONFIRMED,
]


class Booking(models.Model):
    Status = BookingStatus

    class Source(models.TextChoices):
        WEB = "web", "Website"
        BOT = "bot", "Telegram bot"

    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    master = models.ForeignKey(Master, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    client_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=10, choices=Source.choices)
    status = models.CharField(
        max_length=30,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING_DEPOSIT,
        db_index=True,
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    deposit_amount = models.PositiveIntegerField()
    deposit_deadline = models.DateTimeField(null=True, blank=True)
    receipt = models.ImageField(upload_to=receipt_upload_to, blank=True)
    reminded_24h = models.BooleanField(default=False)
    reminded_2h = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["status", "deposit_deadline"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="booking_end_after_start"
            ),
            ExclusionConstraint(
                name="booking_no_overlap",
                expressions=[
                    (TsTzRange("starts_at", "ends_at", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("master", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.client_name} {self.starts_at:%Y-%m-%d %H:%M}"

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES
