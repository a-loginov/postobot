import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import request as request_handler
from bot.keyboards.request import CANCEL_TEXT
from bot.states.request import RequestForm


class FakeUser:
    id = 12345
    username = "testuser"
    full_name = "Тестов Тест"
    first_name = "Тест"
    last_name = None


class FakeMessage:
    def __init__(self, text=None, photo=None):
        self.text = text
        self.photo = photo
        self.from_user = FakeUser()
        self.sent = []

    async def answer(self, text, **kwargs):
        self.sent.append(("text", text, kwargs))
        return None


class FakePhotoSize:
    file_id = "FAKE_PHOTO_ID"


async def _make_context() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=12345)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_photo_required_not_advancing():
    state = await _make_context()
    await state.set_state(RequestForm.photo)
    message = FakeMessage(text="Нет фото")
    await request_handler.on_photo(message, state)
    # state should still be in photo state (no photo provided)
    assert await state.get_state() == RequestForm.photo.state
    # user got a notice
    assert any("фотографию" in s[1] for s in message.sent)


@pytest.mark.asyncio
async def test_photo_advances_to_preview():
    state = await _make_context()
    await state.update_data(
        full_name="Иванов Иван",
        class_name="10А",
        reason="Не работает экран",
    )
    await state.set_state(RequestForm.photo)
    message = FakeMessage(text="", photo=[FakePhotoSize()])
    await request_handler.on_photo(message, state)
    data = await state.get_data()
    assert data["photo"] == "FAKE_PHOTO_ID"
    # preview sets state to None
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_cancel_fsm_clears_state():
    state = await _make_context()
    await state.set_state(RequestForm.reason)
    message = FakeMessage(text=CANCEL_TEXT)
    await request_handler.stop_creation(message, state)
    assert await state.get_state() is None
    assert any("заявки отменено" in s[1].lower() for s in message.sent)


@pytest.mark.asyncio
async def test_full_name_validation_error_shows_message():
    state = await _make_context()
    await state.set_state(RequestForm.full_name)
    message = FakeMessage(text="И")
    await request_handler.on_full_name(message, state)
    assert await state.get_state() == RequestForm.full_name.state
    assert any("минимум 2" in s[1] for s in message.sent)


@pytest.mark.asyncio
async def test_full_name_valid_advance_to_class():
    state = await _make_context()
    await state.set_state(RequestForm.full_name)
    message = FakeMessage(text="Иванов Иван")
    await request_handler.on_full_name(message, state)
    assert await state.get_state() == RequestForm.class_name.state
