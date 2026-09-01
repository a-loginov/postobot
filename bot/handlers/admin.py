import logging

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from bot.context import unit_of_work
from bot.filters.admin import IsAdminCallbackFilter
from bot.keyboards.admin import get_admin_request_keyboard
from bot.keyboards.main import get_main_keyboard
from database.models import RequestStatus
from database.repositories.requests import RequestNotFoundError, RequestRepositoryError
from database.repositories.users import UserRepository
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = Router()

STATUS_TRANSITIONS = {
    "NEW": ["IN_PROGRESS", "REJECTED"],
    "IN_PROGRESS": ["COMPLETED", "REJECTED"],
}


@router.callback_query(IsAdminCallbackFilter(), lambda c: c.data == "admin_new")
async def admin_new_requests(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    with unit_of_work() as (service, session):
        requests = service.get_new_requests()

    if not requests:
        await callback.message.answer(
            "🆕 Новых заявок нет.",
            reply_markup=get_main_keyboard(callback.from_user.id),
        )
        return

    n = NotificationService(bot)
    for request in requests:
        text = n.format_request_for_admin(request)
        user_tg_id = request.user.telegram_id if request.user else None
        kb = get_admin_request_keyboard(
            request.id, request.status.value, user_telegram_id=user_tg_id
        )
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(
    IsAdminCallbackFilter(), lambda c: c.data.startswith("admin_open:")
)
async def admin_open_request(callback: CallbackQuery, bot: Bot) -> None:
    request_id = int(callback.data.split(":")[1])
    with unit_of_work() as (service, session):
        try:
            request = service.get_request(request_id)
        except RequestNotFoundError:
            await callback.answer("⚠️ Заявка не найдена.")
            return

    n = NotificationService(bot)
    text = n.format_request_for_admin(request)
    user_tg_id = request.user.telegram_id if request.user else None
    kb = get_admin_request_keyboard(
        request.id, request.status.value, user_telegram_id=user_tg_id
    )
    if request.photo_file_id:
        await callback.message.answer_photo(
            photo=request.photo_file_id, caption=text, reply_markup=kb
        )
    else:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(
    IsAdminCallbackFilter(), lambda c: c.data.startswith("admin_status:")
)
async def admin_change_status(callback: CallbackQuery, bot: Bot) -> None:
    _, request_id_str, new_status_str = callback.data.split(":")
    request_id = int(request_id_str)
    try:
        new_status = RequestStatus(new_status_str)
    except ValueError:
        await callback.answer("⚠️ Некорректный статус.")
        return

    with unit_of_work() as (service, session):
        try:
            request = service.get_request(request_id)
        except RequestNotFoundError:
            await callback.answer("⚠️ Заявка не найдена.")
            return

        if new_status.value not in STATUS_TRANSITIONS.get(request.status.value, []):
            await callback.answer(
                "⚠️ Нельзя изменить статус с текущего на выбранный."
            )
            return

        try:
            request = service.update_status(
                request_id, new_status
            )
        except (RequestNotFoundError, RequestRepositoryError):
            await callback.answer("⚠️ Не удалось изменить статус.")
            return

        user_telegram_id = request.user.telegram_id
        session.commit()

        if user_telegram_id:
            n = NotificationService(bot)
            await n.notify_status_changed(user_telegram_id, request)

    kb = get_admin_request_keyboard(
        request.id,
        request.status.value,
        user_telegram_id=request.user.telegram_id if request.user else None,
    )
    n = NotificationService(bot)
    text = n.format_request_for_admin(request)
    if request.photo_file_id and hasattr(callback.message, "answer_photo"):
        await callback.message.answer_photo(
            photo=request.photo_file_id, caption=text, reply_markup=kb
        )
    else:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(
    IsAdminCallbackFilter(), lambda c: c.data.startswith("admin_user:")
)
async def admin_user_info(callback: CallbackQuery) -> None:
    telegram_id = int(callback.data.split(":")[1])
    with unit_of_work() as (service, session):
        user_repo = UserRepository(session)
        user = user_repo.get_by_telegram_id(telegram_id)

    if user is None:
        await callback.answer("⚠️ Пользователь не найден.")
        return

    text = (
        "👤 Пользователь\n\n"
        f"ID: {user.telegram_id}\n"
        f"Имя: {user.full_name or '—'}\n"
        f"@username: {user.username or '—'}\n"
        f"Роль: {user.role.value}"
    )
    await callback.message.answer(text)
    await callback.answer()
