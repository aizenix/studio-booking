from aiogram.filters.callback_data import CallbackData

NOOP = "noop"
CANCEL = "cancel"


class ServiceCb(CallbackData, prefix="svc"):
    id: int


class MasterCb(CallbackData, prefix="mst"):
    id: int


class DayCb(CallbackData, prefix="day"):
    value: str  # ISO date, CallbackData has no date type


class SlotCb(CallbackData, prefix="slot"):
    ts: int


class ConfirmCb(CallbackData, prefix="confirm"):
    ok: bool


class ReviewCb(CallbackData, prefix="review"):
    action: str
    booking_id: int


class MyBookingCb(CallbackData, prefix="my"):
    action: str
    booking_id: int
