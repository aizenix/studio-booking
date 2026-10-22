from django.conf import settings
from django.utils import timezone

from booking.models import Booking

Status = Booking.Status


def format_money(amount):
    return f"{amount:,}".replace(",", " ") + f" {settings.CURRENCY}"


def format_time(value):
    return timezone.localtime(value).strftime("%H:%M")


def format_day(day):
    return day.strftime("%a %d %b")


def format_when(value):
    return timezone.localtime(value).strftime("%a %d %b, %H:%M")


def confirmation_text(*, service, master, starts_at, client_name, phone):
    return "\n".join(
        [
            "Please check your booking:",
            "",
            f"Service: {service.name}",
            f"Master: {master.name}",
            f"When: {format_when(starts_at)}",
            f"Name: {client_name}",
            f"Phone: {phone}",
            f"Deposit: {format_money(service.deposit)}",
        ]
    )


def deposit_request_text(booking):
    lines = [
        f"Booking #{booking.pk} is held for you until {format_time(booking.deposit_deadline)}.",
        "",
        f"To confirm it, pay the deposit of {format_money(booking.deposit_amount)}",
    ]
    if settings.DEPOSIT_PAYMENT_DETAILS:
        lines.append(f"to: {settings.DEPOSIT_PAYMENT_DETAILS}")
    lines += [
        "",
        "Then send a photo of the receipt to this chat. "
        "If we do not get it in time, the booking is released automatically.",
    ]
    return "\n".join(lines)


def booking_card(booking):
    return "\n".join(
        [
            f"Booking #{booking.pk}",
            f"{booking.service.name} with {booking.master.name}",
            f"When: {format_when(booking.starts_at)}",
            f"Status: {booking.get_status_display()}",
        ]
    )


def review_caption(booking):
    return "\n".join(
        [
            f"Receipt for booking #{booking.pk} ({booking.get_source_display()})",
            f"{booking.client_name}, {booking.phone}",
            f"{booking.service.name} with {booking.master.name}",
            f"When: {format_when(booking.starts_at)}",
            f"Deposit: {format_money(booking.deposit_amount)}",
        ]
    )


def status_message(booking):
    when = format_when(booking.starts_at)
    if booking.status == Status.CONFIRMED:
        return (
            f"Your booking is confirmed: {when}, {booking.service.name} "
            f"with {booking.master.name}. See you at the studio!"
        )
    if booking.status == Status.EXPIRED:
        return (
            f"Booking #{booking.pk} for {when} was released because the deposit "
            "was not received in time. You can book again at any moment."
        )
    if booking.status == Status.CANCELLED:
        return (
            f"We could not confirm the deposit for booking #{booking.pk} ({when}), "
            "so the booking was cancelled. If this is a mistake, please contact the studio."
        )
    return booking_card(booking)
