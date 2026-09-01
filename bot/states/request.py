from aiogram.fsm.state import State, StatesGroup


class RequestForm(StatesGroup):
    full_name = State()
    class_name = State()
    reason = State()
    photo = State()


class RequestEdit(StatesGroup):
    waiting_for_field = State()
