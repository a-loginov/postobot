import logging

from aiogram import Bot, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.context import unit_of_work
from bot.keyboards.main import get_main_keyboard
from bot.keyboards.request import (
    CANCEL_TEXT,
    get_action_keyboard,
    get_cancel_keyboard,
    get_edit_keyboard,
)
from bot.states.request import RequestForm
from services.notification_service import NotificationService
from services.request_service import RequestService, RequestValidationError

logger = logging.getLogger(__name__)

router = Router()


@router.message(lambda message: message.text == "📝 Создать заявку")
async def menu_create_request(message: Message, state: FSMContext) -> None:
    await cmd_create_request(message, state)

FULL_NAME = "full_name"
CLASS_NAME = "class_name"
REASON = "reason"
PHOTO = "photo"

PROMPTS = {
    FULL_NAME: "👤 Введите имя и фамилию:",
    CLASS_NAME: "🏫 Введите класс:",
    REASON: "🔧 Опишите причину замены или ремонта:",
    PHOTO: "📷 Прикрепите фотографию проблемы.\n\nФото обязательно.",
}


def _state_for(field: str):
    mapping = {
        FULL_NAME: RequestForm.full_name,
        CLASS_NAME: RequestForm.class_name,
        REASON: RequestForm.reason,
        PHOTO: RequestForm.photo,
    }
    return mapping[field]


async def cmd_create_request(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RequestForm.full_name)
    await state.update_data(editing=False)
    await message.answer(PROMPTS[FULL_NAME], reply_markup=get_cancel_keyboard())


async def stop_creation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "❌ Создание заявки отменено.",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


async def _draft(state: FSMContext) -> dict:
    data = await state.get_data()
    return data


def _validators() -> dict:
    return {
        FULL_NAME: RequestService.validate_full_name,
        CLASS_NAME: RequestService.validate_class_name,
        REASON: RequestService.validate_reason,
    }


async def _handle_text_field(message: Message, state: FSMContext, field: str) -> None:
    if message.text == CANCEL_TEXT:
        await stop_creation(message, state)
        return
    validator = _validators()[field]
    try:
        value = validator(message.text or "")
    except RequestValidationError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    data[field] = value
    await state.update_data(**{field: value})
    if data.get("editing"):
        await state.update_data(editing=False)
        await show_preview(message, state)
        return
    await _advance(message, state, field, data)


async def _advance(message: Message, state: FSMContext, field: str, data: dict) -> None:
    order = [FULL_NAME, CLASS_NAME, REASON, PHOTO]
    next_fields = order[order.index(field) + 1:]
    if not next_fields:
        await show_preview(message, state)
        return
    next_field = next_fields[0]
    await state.set_state(_state_for(next_field))
    await message.answer(PROMPTS[next_field], reply_markup=get_cancel_keyboard())


@router.message(RequestForm.full_name)
async def on_full_name(message: Message, state: FSMContext) -> None:
    await _handle_text_field(message, state, FULL_NAME)


@router.message(RequestForm.class_name)
async def on_class_name(message: Message, state: FSMContext) -> None:
    await _handle_text_field(message, state, CLASS_NAME)


@router.message(RequestForm.reason)
async def on_reason(message: Message, state: FSMContext) -> None:
    await _handle_text_field(message, state, REASON)


@router.message(RequestForm.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    if message.text == CANCEL_TEXT:
        await stop_creation(message, state)
        return
    if not message.photo:
        await message.answer(
            "📷 Пожалуйста, прикрепите фотографию проблемы.\nФото обязательно."
        )
        return
    photo = message.photo[-1]
    await state.update_data(photo=photo.file_id)
    data = await state.get_data()
    await show_preview(message, state)


async def show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    full_name = data.get(FULL_NAME, "")
    class_name = data.get(CLASS_NAME, "")
    reason = data.get(REASON, "")
    text = (
        "📋 Проверьте заявку\n\n"
        f"👤 {full_name}\n"
        f"🏫 {class_name}\n\n"
        f"🔧 Причина:\n{reason}\n\n"
        f"📷 Фото прикреплено"
    )
    await state.set_state(None)
    await message.answer(text, reply_markup=get_action_keyboard())


@router.callback_query(lambda c: c.data == "req_accept")
async def on_accept(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    try:
        with unit_of_work() as (service, session):
            from database.repositories.users import UserRepository

            user_repo = UserRepository(session)
            user = user_repo.get_or_create(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name,
            )
            request = service.create_request(
                user=user,
                full_name=data.get(FULL_NAME, ""),
                class_name=data.get(CLASS_NAME, ""),
                reason=data.get(REASON, ""),
                photo_file_id=data.get(PHOTO, ""),
            )
            admin_ids = service.list_admin_ids()
            session.commit()
            if admin_ids:
                n = NotificationService(bot)
                await n.notify_admins_new_request(request, admin_ids)
        await callback.message.answer(
            f"✅ Заявка №{request.id} создана!\n"
            f"Заявка отправлена ответственному.\n\n"
            f"Статус:\n🟡 Новая",
            reply_markup=get_main_keyboard(callback.from_user.id),
        )
    except Exception:
        logger.exception("Failed to create request")
        await callback.message.answer(
            "⚠️ Не удалось сохранить заявку. Попробуйте ещё раз позже.",
            reply_markup=get_main_keyboard(callback.from_user.id),
        )
    finally:
        await state.clear()


@router.callback_query(lambda c: c.data == "req_edit")
async def on_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    text = "✏️ Что хотите изменить?"
    await callback.message.answer(text, reply_markup=get_edit_keyboard())


@router.callback_query(lambda c: c.data == "req_cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "❌ Создание заявки отменено.",
        reply_markup=get_main_keyboard(callback.from_user.id),
    )


@router.callback_query(lambda c: c.data == "edit_back")
async def on_edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(editing=False)
    await show_preview(callback.message, state)


@router.callback_query(lambda c: c.data.startswith("edit_name"))
async def on_edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    await _start_edit_field(callback, state, FULL_NAME)


@router.callback_query(lambda c: c.data.startswith("edit_class"))
async def on_edit_class(callback: CallbackQuery, state: FSMContext) -> None:
    await _start_edit_field(callback, state, CLASS_NAME)


@router.callback_query(lambda c: c.data.startswith("edit_reason"))
async def on_edit_reason(callback: CallbackQuery, state: FSMContext) -> None:
    await _start_edit_field(callback, state, REASON)


@router.callback_query(lambda c: c.data.startswith("edit_photo"))
async def on_edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(editing=True)
    await state.set_state(RequestForm.photo)
    await callback.message.answer(PROMPTS[PHOTO], reply_markup=get_cancel_keyboard())


async def _start_edit_field(callback: CallbackQuery, state: FSMContext, field: str) -> None:
    await callback.answer()
    await state.update_data(editing=True)
    await state.set_state(_state_for(field))
    await callback.message.answer(PROMPTS[field], reply_markup=get_cancel_keyboard())
