import logging

from aiogram import Bot, Router, types
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.context import unit_of_work
from bot.keyboards.main import get_main_keyboard
from database.repositories.users import UserRepository
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = Router()


def _user_requests_keyboard(request_ids: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"№{rid}", callback_data=f"user_open:{rid}")]
        for rid in request_ids
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_my_requests(message: types.Message, bot: Bot) -> None:
    with unit_of_work() as (service, session):
        user_repo = UserRepository(session)
        user = user_repo.get_by_telegram_id(message.from_user.id)
        if user is None:
            user = user_repo.create(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
        requests = service.get_user_requests(user)
        request_ids = [r.id for r in requests]

    if not requests:
        await message.answer(
            "📋 У вас пока нет заявок.",
            reply_markup=get_main_keyboard(message.from_user.id),
        )
        return

    lines = ["📋 Ваши заявки:"]
    n = NotificationService(bot)
    for r in requests:
        lines.append(n.format_request_short(user, r))
    text = "\n\n".join(lines)
    await message.answer(text, reply_markup=_user_requests_keyboard(request_ids))


@router.callback_query(lambda c: c.data.startswith("user_open:"))
async def on_user_open(callback: CallbackQuery, bot: Bot) -> None:
    request_id = int(callback.data.split(":")[1])
    with unit_of_work() as (service, session):
        try:
            request = service.get_request(request_id)
        except Exception:
            await callback.answer()
            await callback.message.answer(
                "⚠️ Заявка не найдена.", reply_markup=get_main_keyboard(callback.from_user.id)
            )
            return
    n = NotificationService(bot)
    text = n.format_request_for_user(request)
    if request.photo_file_id:
        await callback.message.answer_photo(
            photo=request.photo_file_id,
            caption=text,
        )
    else:
        await callback.message.answer(text)
    await callback.answer()
