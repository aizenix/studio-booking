import datetime as dt

from django.utils import timezone

from booking.models import Booking
from bot.callbacks import NOOP, DayCb, SlotCb
from bot.formatting import deposit_request_text, format_money
from bot.keyboards import calendar_keyboard, slots_keyboard


def clickable(markup):
    return [
        button
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data.startswith(DayCb.__prefix__)
    ]


def test_calendar_is_aligned_to_weekdays():
    wednesday = dt.date(2026, 10, 28)

    rows = calendar_keyboard(wednesday, 14, available=set()).inline_keyboard

    assert rows[0][0].text == "Oct - Nov 2026"
    assert [b.text for b in rows[1]] == ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    first_week = rows[2]
    assert [b.text for b in first_week[:3]] == [" ", " ", "-"]
    # 2 blank cells + 14 days = 16 cells, padded to three full weeks
    assert all(len(row) == 7 for row in rows[2:5])
    assert rows[-1][0].text == "Cancel"


def test_calendar_only_available_days_are_clickable():
    start = dt.date(2026, 11, 2)
    available = {start, start + dt.timedelta(days=3)}

    markup = calendar_keyboard(start, 14, available)
    buttons = clickable(markup)

    assert [b.text for b in buttons] == ["2", "5"]
    assert DayCb.unpack(buttons[1].callback_data).value == "2026-11-05"
    blanks = [b for row in markup.inline_keyboard[2:-1] for b in row if b not in buttons]
    assert all(b.callback_data == NOOP for b in blanks)


def test_slots_keyboard_shows_local_time_in_rows_of_four():
    tz = timezone.get_current_timezone()
    slots = [
        dt.datetime(2026, 11, 2, 10, 0, tzinfo=tz) + dt.timedelta(minutes=30 * i) for i in range(6)
    ]

    rows = slots_keyboard(slots).inline_keyboard

    assert [b.text for b in rows[0]] == ["10:00", "10:30", "11:00", "11:30"]
    assert [b.text for b in rows[1]] == ["12:00", "12:30"]
    assert SlotCb.unpack(rows[0][0].callback_data).ts == int(slots[0].timestamp())
    assert rows[-1][0].text == "Cancel"


def test_deposit_request_text(settings):
    settings.DEPOSIT_PAYMENT_DETAILS = "Uzcard 8600 0000 0000 0000"
    deadline = dt.datetime(2026, 11, 2, 9, 5, tzinfo=dt.UTC)
    booking = Booking(pk=42, deposit_amount=150_000, deposit_deadline=deadline)

    text = deposit_request_text(booking)

    assert format_money(1_250_000) == "1 250 000 UZS"
    assert "Booking #42 is held for you until 14:05." in text
    assert "150 000 UZS" in text
    assert "Uzcard 8600 0000 0000 0000" in text
