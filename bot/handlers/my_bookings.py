from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from django.utils import timezone

from booking.models import ACTIVE_STATUSES, Booking
from booking.services import InvalidTransition, acancel_booking

from .. import keyboards
from ..admin_chat import notify_admins
from ..callbacks import MyBookingCb
from ..formatting import booking_card, deposit_request_text, format_when
from ..states import BookingForm

router = Router(name="my_bookings")


async def get_own_booking(callback: CallbackQuery, booking_id: int):
    return (
        await Booking.objects.select_related("master", "service")
        .filter(pk=booking_id, telegram_id=callback.from_user.id)
        .afirst()
    )


@router.message(Command("my"))
@router.message(F.text == keyboards.MY_BOOKINGS_BUTTON)
async def my_bookings(message: Message, state: FSMContext):
    await state.clear()
    upcoming = (
        Booking.objects.filter(
            telegram_id=message.from_user.id,
            status__in=ACTIVE_STATUSES,
            starts_at__gte=timezone.now(),
        )
        .select_related("master", "service")
        .order_by("starts_at")
    )
    bookings = [booking async for booking in upcoming]
    if not bookings:
        await message.answer("You have no upcoming bookings.", reply_markup=keyboards.main_menu())
        return
    for booking in bookings:
        await message.answer(
            booking_card(booking), reply_markup=keyboards.booking_actions_keyboard(booking)
        )


@router.callback_query(MyBookingCb.filter(F.action == "cancel"))
async def ask_to_confirm_cancel(callback: CallbackQuery, callback_data: MyBookingCb):
    await callback.message.edit_reply_markup(
        reply_markup=keyboards.cancel_confirm_keyboard(callback_data.booking_id)
    )
    await callback.answer()


@router.callback_query(MyBookingCb.filter(F.action == "keep"))
async def keep_booking(callback: CallbackQuery, callback_data: MyBookingCb):
    booking = await get_own_booking(callback, callback_data.booking_id)
    markup = keyboards.booking_actions_keyboard(booking) if booking and booking.is_active else None
    await callback.message.edit_reply_markup(reply_markup=markup)
    await callback.answer()


@router.callback_query(MyBookingCb.filter(F.action == "cancel_yes"))
async def cancel_booking(callback: CallbackQuery, callback_data: MyBookingCb, bot: Bot):
    booking = await get_own_booking(callback, callback_data.booking_id)
    if booking is None:
        await callback.answer("Booking not found.", show_alert=True)
        return
    try:
        booking = await acancel_booking(booking.pk)
    except InvalidTransition:
        await callback.answer("This booking can no longer be cancelled.", show_alert=True)
        return

    await callback.message.edit_text(booking_card(booking))
    await callback.answer("Booking cancelled")
    await notify_admins(
        bot,
        f"Client cancelled booking #{booking.pk}: {booking.client_name}, "
        f"{format_when(booking.starts_at)} with {booking.master.name}.",
    )


@router.callback_query(MyBookingCb.filter(F.action == "receipt"))
async def send_receipt_later(
    callback: CallbackQuery, callback_data: MyBookingCb, state: FSMContext
):
    booking = await get_own_booking(callback, callback_data.booking_id)
    if booking is None or booking.status != Booking.Status.PENDING_DEPOSIT:
        await callback.answer("This booking does not need a receipt.", show_alert=True)
        return
    await state.set_state(BookingForm.receipt)
    await state.update_data(booking_id=booking.pk)
    await callback.message.answer(deposit_request_text(booking))
    await callback.answer()
