from aiogram.fsm.state import State, StatesGroup


class BookingForm(StatesGroup):
    service = State()
    master = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()
    receipt = State()
