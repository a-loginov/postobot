import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.context import unit_of_work
from bot.keyboards.main import get_main_keyboard
from bot.keyboards.request import get_cancel_keyboard
from bot.states.request import FeedbackForm
from database.repositories.users import UserRepository
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = Router()

CANCEL_TEXT = "❌ Отмена"

FEEDBACK_PROMPT = (
    "💬 Обратная связь\n\n"
    "Напишите ваше сообщение — оно будет "
    "передано администратору.\n\n"
    "Для отмены нажмите «❌ Отмена»."
)

FEEDBACK_SENT = "✅ Спасибо! Ваше сообщение передано администратору."

FEEDBACK_CANCELED = "❌ Отправка сообщения отменена."


@router.message(Command("feedback"))
@router.message(lambda message: message.text == "💬 Обратная связь")
async def cmd_feedback(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(FeedbackForm.waiting_for_text)
    await message.answer(FEEDBACK_PROMPT, reply_markup=get_cancel_keyboard())


@router.message(FeedbackForm.waiting_for_text)
async def on_feedback_text(message: types.Message, bot: Bot, state: FSMContext) -> None:
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer(
            FEEDBACK_CANCELED, reply_markup=get_main_keyboard(message.from_user.id)
        )
        return

    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введите текст сообщения.")
        return

    text = message.text.strip()
    sender = message.from_user

    try:
        with unit_of_work() as (service, session):
            user_repo = UserRepository(session)
            user_repo.get_or_create(
                telegram_id=sender.id,
                username=sender.username,
                full_name=sender.full_name,
            )
            admin_ids = service.list_admin_ids()

        n = NotificationService(bot)
        await n.notify_admins_feedback(admin_ids, sender.id, text)

        await state.clear()
        await message.answer(
            FEEDBACK_SENT, reply_markup=get_main_keyboard(sender.id)
        )
    except Exception:
        logger.exception("Failed to send feedback from telegram_id=%s", sender.id)
        await state.clear()
        await message.answer(
            "⚠️ Не удалось отправить сообщение. Попробуйте позже.",
            reply_markup=get_main_keyboard(sender.id),
        )
