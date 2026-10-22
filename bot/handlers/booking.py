from datetime import UTC, date, datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from booking.models import Booking, Master, Service
from booking.services import (
    DepositWindowClosed,
    InvalidTransition,
    SlotUnavailable,
    aattach_receipt,
    acreate_booking,
)
from booking.slots import get_available_days, get_available_slots
from booking.validators import normalize_phone

from .. import keyboards
from ..admin_chat import send_for_review
from ..callbacks import CANCEL, NOOP, ConfirmCb, DayCb, MasterCb, ServiceCb, SlotCb
from ..formatting import confirmation_text, deposit_request_text, format_day, format_when
from ..states import BookingForm

router = Router(name="booking")

aget_available_slots = sync_to_async(get_available_slots)
aget_available_days = sync_to_async(get_available_days)


async def load_choice(state):
    data = await state.get_data()
    master = await Master.objects.aget(pk=data["master_id"])
    service = await Service.objects.aget(pk=data["service_id"])
    return master, service


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Hi! Here you can book a session at the studio and keep track of your bookings.",
        reply_markup=keyboards.main_menu(),
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.", reply_markup=keyboards.main_menu())


@router.callback_query(F.data == CANCEL)
async def cancel_button(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('Cancelled. Tap "Book a session" to start again.')
    await callback.answer()


@router.callback_query(F.data == NOOP)
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.message(Command("book"))
@router.message(F.text == keyboards.BOOK_BUTTON)
async def choose_service(message: Message, state: FSMContext):
    await state.clear()
    bookable = Service.objects.filter(is_active=True, masters__is_active=True).distinct()
    services = [service async for service in bookable]
    if not services:
        await message.answer("Online booking is not available right now, please call the studio.")
        return
    await state.set_state(BookingForm.service)
    await message.answer("Choose a service:", reply_markup=keyboards.services_keyboard(services))


@router.callback_query(BookingForm.service, ServiceCb.filter())
async def service_chosen(callback: CallbackQuery, callback_data: ServiceCb, state: FSMContext):
    qs = Master.objects.filter(is_active=True, services=callback_data.id)
    masters = [master async for master in qs]
    if not masters:
        await callback.answer("Nobody does this service at the moment.", show_alert=True)
        return
    await state.update_data(service_id=callback_data.id)
    await state.set_state(BookingForm.master)
    await callback.message.edit_text(
        "Choose a master:", reply_markup=keyboards.masters_keyboard(masters)
    )
    await callback.answer()


@router.callback_query(BookingForm.master, MasterCb.filter())
async def master_chosen(callback: CallbackQuery, callback_data: MasterCb, state: FSMContext):
    await state.update_data(master_id=callback_data.id)
    await show_calendar(callback.message, state, edit=True)
    await callback.answer()


async def show_calendar(message: Message, state: FSMContext, *, edit: bool):
    master, service = await load_choice(state)
    today = timezone.localdate()
    days = settings.BOOKING_HORIZON_DAYS
    available = await aget_available_days(master, service, today, days)

    if available:
        await state.set_state(BookingForm.day)
        text = f"{service.name} with {master.name}. Choose a day:"
        markup = keyboards.calendar_keyboard(today, days, set(available))
    else:
        await state.clear()
        text = f"{master.name} has no free time in the next {days} days. Try another master."
        markup = None

    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(BookingForm.day, DayCb.filter())
async def day_chosen(callback: CallbackQuery, callback_data: DayCb, state: FSMContext):
    day = date.fromisoformat(callback_data.value)
    master, service = await load_choice(state)
    slots = await aget_available_slots(master, service, day)
    if not slots:
        await callback.answer("This day is already full, please pick another.", show_alert=True)
        return
    await state.set_state(BookingForm.time)
    await callback.message.edit_text(
        f"{format_day(day)}. Choose a time:", reply_markup=keyboards.slots_keyboard(slots)
    )
    await callback.answer()


@router.callback_query(BookingForm.time, SlotCb.filter())
async def time_chosen(callback: CallbackQuery, callback_data: SlotCb, state: FSMContext):
    starts_at = datetime.fromtimestamp(callback_data.ts, tz=UTC)
    await state.update_data(starts_at=callback_data.ts)
    await state.set_state(BookingForm.name)
    await callback.message.edit_text(f"Time: {format_when(starts_at)}")
    await callback.message.answer("What is your name?")
    await callback.answer()


@router.message(BookingForm.name, F.text)
async def name_entered(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) > 100:
        await message.answer("That is a bit long, please send just your name.")
        return
    await state.update_data(client_name=name)
    await state.set_state(BookingForm.phone)
    await message.answer(
        "Send your phone number or tap the button below.",
        reply_markup=keyboards.contact_keyboard(),
    )


@router.message(BookingForm.phone, F.contact)
async def contact_shared(message: Message, state: FSMContext):
    await save_phone(message, state, message.contact.phone_number)


@router.message(BookingForm.phone, F.text)
async def phone_typed(message: Message, state: FSMContext):
    await save_phone(message, state, message.text)


async def save_phone(message: Message, state: FSMContext, raw_phone: str):
    phone = normalize_phone(raw_phone)
    if phone is None:
        await message.answer("This does not look like a phone number. Example: +998 90 123 45 67")
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingForm.confirm)

    data = await state.get_data()
    master, service = await load_choice(state)
    # Puts the main menu back in place of the contact button.
    await message.answer("Almost done.", reply_markup=keyboards.main_menu())
    await message.answer(
        confirmation_text(
            service=service,
            master=master,
            starts_at=datetime.fromtimestamp(data["starts_at"], tz=UTC),
            client_name=data["client_name"],
            phone=phone,
        ),
        reply_markup=keyboards.confirm_keyboard(),
    )


@router.callback_query(BookingForm.confirm, ConfirmCb.filter(F.ok.is_(False)))
async def booking_declined(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Booking cancelled.")
    await callback.answer()


@router.callback_query(BookingForm.confirm, ConfirmCb.filter(F.ok.is_(True)))
async def booking_confirmed(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master, service = await load_choice(state)
    try:
        booking = await acreate_booking(
            master=master,
            service=service,
            starts_at=datetime.fromtimestamp(data["starts_at"], tz=UTC),
            client_name=data["client_name"],
            phone=data["phone"],
            source=Booking.Source.BOT,
            telegram_id=callback.from_user.id,
        )
    except SlotUnavailable:
        await callback.message.edit_text("Sorry, this time was just taken by someone else.")
        await show_calendar(callback.message, state, edit=False)
        await callback.answer()
        return

    await state.set_state(BookingForm.receipt)
    await state.update_data(booking_id=booking.pk)
    await callback.message.edit_text(deposit_request_text(booking))
    await callback.answer()


@router.message(BookingForm.receipt, F.photo)
async def receipt_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photo = message.photo[-1]
    content = await bot.download(photo)
    try:
        booking = await aattach_receipt(
            data["booking_id"], ContentFile(content.read(), name=f"{photo.file_unique_id}.jpg")
        )
    except DepositWindowClosed:
        await state.clear()
        await message.answer(
            "Sorry, the time to pay the deposit is over and the slot was released. "
            "You are welcome to book again."
        )
        return
    except InvalidTransition:
        await state.clear()
        await message.answer("This booking does not need a receipt anymore.")
        return

    await state.clear()
    await message.answer(
        "Thank you, we got the receipt. You will get a message as soon as the studio checks it.",
        reply_markup=keyboards.main_menu(),
    )
    await send_for_review(bot, booking, photo.file_id)


@router.message(BookingForm.receipt)
async def receipt_expected(message: Message):
    await message.answer("Please send the receipt as a photo (not as a file).")


@router.callback_query()
async def outdated_button(callback: CallbackQuery):
    # Buttons from old messages stay clickable after the state has moved on.
    await callback.answer("This menu is out of date, please start again.", show_alert=True)
