from datetime import timedelta

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .callbacks import CANCEL, NOOP, ConfirmCb, DayCb, MasterCb, ReviewCb, ServiceCb, SlotCb
from .formatting import format_money, format_time

BOOK_BUTTON = "Book a session"
MY_BOOKINGS_BUTTON = "My bookings"
WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _noop(text=" "):
    return InlineKeyboardButton(text=text, callback_data=NOOP)


def _cancel():
    return InlineKeyboardButton(text="Cancel", callback_data=CANCEL)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BOOK_BUTTON), KeyboardButton(text=MY_BOOKINGS_BUTTON)]],
        resize_keyboard=True,
    )


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Share my phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def services_keyboard(services):
    builder = InlineKeyboardBuilder()
    for service in services:
        builder.button(
            text=f"{service.name}, {format_money(service.price)}",
            callback_data=ServiceCb(id=service.pk),
        )
    builder.adjust(1)
    builder.row(_cancel())
    return builder.as_markup()


def masters_keyboard(masters):
    builder = InlineKeyboardBuilder()
    for master in masters:
        builder.button(text=master.name, callback_data=MasterCb(id=master.pk))
    builder.adjust(2)
    builder.row(_cancel())
    return builder.as_markup()


def calendar_keyboard(start, days, available):
    """A grid aligned to weekdays. Days without free slots are shown but not clickable."""
    end = start + timedelta(days=days - 1)
    if (start.year, start.month) == (end.year, end.month):
        title = start.strftime("%B %Y")
    else:
        title = f"{start:%b} - {end:%b %Y}"

    rows = [[_noop(title)], [_noop(name) for name in WEEKDAYS]]
    week = [_noop() for _ in range(start.weekday())]
    for offset in range(days):
        day = start + timedelta(days=offset)
        if day in available:
            week.append(
                InlineKeyboardButton(
                    text=str(day.day), callback_data=DayCb(value=day.isoformat()).pack()
                )
            )
        else:
            week.append(_noop("-"))
        if len(week) == 7:
            rows.append(week)
            week = []
    if week:
        week += [_noop() for _ in range(7 - len(week))]
        rows.append(week)
    rows.append([_cancel()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def slots_keyboard(slots, per_row=4):
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=format_time(slot), callback_data=SlotCb(ts=int(slot.timestamp())))
    builder.adjust(per_row)
    builder.row(_cancel())
    return builder.as_markup()


def confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Confirm", callback_data=ConfirmCb(ok=True))
    builder.button(text="Cancel", callback_data=ConfirmCb(ok=False))
    return builder.as_markup()


def review_keyboard(booking_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="Approve", callback_data=ReviewCb(action="approve", booking_id=booking_id))
    builder.button(text="Reject", callback_data=ReviewCb(action="reject", booking_id=booking_id))
    return builder.as_markup()
