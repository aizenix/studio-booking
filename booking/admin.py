from django.contrib import admin, messages
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html

from .models import Booking, Master, Service, TimeOff, WorkingHours
from .services import InvalidTransition, approve_booking, reject_booking
from .tasks import send_status_notification

admin.site.site_header = "Studio booking"


class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 0


class TimeOffInline(admin.TabularInline):
    model = TimeOff
    extra = 0


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active", "services"]
    search_fields = ["name"]
    filter_horizontal = ["services"]
    inlines = [WorkingHoursInline, TimeOffInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "duration_minutes", "price", "deposit", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ["master", "starts_at", "ends_at", "reason"]
    list_filter = ["master"]
    date_hierarchy = "starts_at"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "starts_at",
        "client_name",
        "phone",
        "master",
        "service",
        "status",
        "source",
        "has_receipt",
    ]
    list_filter = ["status", "source", "master", "service"]
    list_select_related = ["master", "service"]
    search_fields = ["client_name", "phone", "=telegram_id"]
    date_hierarchy = "starts_at"
    exclude = ["receipt"]
    readonly_fields = [
        "code",
        "source",
        "telegram_id",
        "deposit_deadline",
        "receipt_preview",
        "created_at",
        "updated_at",
    ]
    actions = ["approve", "reject"]

    @admin.display(boolean=True, description="Receipt")
    def has_receipt(self, booking):
        return bool(booking.receipt)

    @admin.display(description="Receipt")
    def receipt_preview(self, booking):
        if not booking.receipt:
            return "-"
        url = reverse("booking-receipt", args=[booking.pk])
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" style="max-height: 320px"></a>', url, url
        )

    @admin.action(description="Approve deposit and confirm")
    def approve(self, request, queryset):
        self._change_status(request, queryset, approve_booking, "confirmed")

    @admin.action(description="Reject deposit and cancel")
    def reject(self, request, queryset):
        self._change_status(request, queryset, reject_booking, "cancelled")

    def _change_status(self, request, queryset, change, verb):
        changed = skipped = 0
        for booking_id in queryset.values_list("pk", flat=True):
            try:
                booking = change(booking_id)
            except InvalidTransition:
                skipped += 1
                continue
            changed += 1
            if booking.telegram_id:
                transaction.on_commit(lambda pk=booking.pk: send_status_notification.delay(pk))

        if changed:
            self.message_user(request, f"{changed} booking(s) {verb}.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request, f"{skipped} booking(s) skipped because of their status.", messages.WARNING
            )
