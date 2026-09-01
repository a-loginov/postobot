import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from bot.context import unit_of_work
from bot.filters.admin import IsAdminFilter
from bot.keyboards.admin import get_admin_main_keyboard
from bot.keyboards.main import get_main_keyboard
from database.models import UserRole
from database.repositories.users import UserRepository

logger = logging.getLogger(__name__)

router = Router()

HELP_TEXT = (
    "ПостоБот предназначен для отправки заявок\n"
    "на замену или ремонт оборудования.\n\n"
    "Для создания заявки необходимо указать:\n\n"
    "👤 Имя и фамилию\n"
    "🏫 Класс\n"
    "🔧 Причину\n"
    "📷 Фотографию"
)

MAIN_WELCOME = (
    "👋 Добро пожаловать в ПостоБот!\n\n"
    "Здесь можно сообщить о необходимости\n"
    "замены или ремонта оборудования."
)


@router.message(CommandStart())
async def cmd_start(message: types.Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    tg_user = message.from_user
    from config import is_admin

    role = UserRole.ADMIN if is_admin(tg_user.id) else UserRole.USER
    with unit_of_work() as (service, session):
        user_repo = UserRepository(session)
        user_repo.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            role=role,
        )
    await message.answer(
        MAIN_WELCOME, reply_markup=get_main_keyboard(tg_user.id)
    )


@router.message(Command("help"))
@router.message(lambda message: message.text == "ℹ️ Помощь")
async def cmd_help(message: types.Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        HELP_TEXT, reply_markup=get_main_keyboard(message.from_user.id)
    )


@router.message(IsAdminFilter(), Command("admin"))
@router.message(
    IsAdminFilter(), lambda message: message.text == "🛠 Администрирование"
)
async def cmd_admin(message: types.Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    text = "🛠 Администрирование\nВыберите действие:"
    await message.answer(text, reply_markup=get_admin_main_keyboard())


@router.message(Command("my"))
@router.message(lambda message: message.text == "📋 Мои заявки")
async def cmd_my(message: types.Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    from bot.handlers.user import send_my_requests

    await send_my_requests(message, bot)
