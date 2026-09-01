import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from bot.keyboards.main import get_main_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def unknown_message(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        "Не понимаю команду. Используйте меню ниже.",
        reply_markup=get_main_keyboard(message.from_user.id),
    )