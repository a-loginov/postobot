from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Request, RequestStatus, User

logger = logging.getLogger(__name__)

STATUS_EMOJI = {
    RequestStatus.NEW: "🟡",
    RequestStatus.IN_PROGRESS: "🔵",
    RequestStatus.COMPLETED: "☑️",
    RequestStatus.REJECTED: "🔴",
}


def format_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


class NotificationService:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def notify_admins_new_request(
        self, request: Request, admin_ids: list[int]
    ) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔍 Открыть заявку",
                        callback_data=f"admin_open:{request.id}",
                    )
                ]
            ]
        )
        text = self.format_request_for_admin(request)
        for admin_id in admin_ids:
            try:
                if request.photo_file_id:
                    await self._bot.send_photo(
                        chat_id=admin_id,
                        photo=request.photo_file_id,
                        caption=text,
                        reply_markup=keyboard,
                    )
                else:
                    await self._bot.send_message(
                        chat_id=admin_id,
                        text=text,
                        reply_markup=keyboard,
                    )
            except Exception:
                logger.exception("Failed to notify admin telegram_id=%s", admin_id)

    @staticmethod
    def format_request_for_admin(request: Request) -> str:
        status_emoji = STATUS_EMOJI.get(request.status, "🟡")
        return (
            f"🚨 Новая заявка №{request.id}\n\n"
            f"👤 {request.full_name}\n"
            f"🏫 {request.class_name}\n\n"
            f"🔧 Причина:\n{request.reason}\n\n"
            f"📷 Фото прикреплено\n"
            f"Статус: {status_emoji} {request.status.value}"
        )

    async def notify_status_changed(self, user_telegram_id: int, request: Request) -> None:
        status_messages = {
            RequestStatus.NEW: "🟡 Заявка №{n} создана.",
            RequestStatus.IN_PROGRESS: "🔧 Заявка №{n} взята в работу.",
            RequestStatus.COMPLETED: "☑️ Заявка №{n} выполнена.",
            RequestStatus.REJECTED: "❌ Заявка №{n} отклонена.",
        }
        template = status_messages.get(request.status, "Статус заявки №{n} обновлён.")
        text = template.format(n=request.id)
        try:
            await self._bot.send_message(chat_id=user_telegram_id, text=text)
        except Exception:
            logger.exception("Failed to notify user telegram_id=%s", user_telegram_id)

    def format_request_for_user(self, request: Request) -> str:
        status_emoji = STATUS_EMOJI.get(request.status, "🟡")
        return (
            f"📋 Заявка №{request.id}\n\n"
            f"👤 {request.full_name}\n"
            f"🏫 {request.class_name}\n\n"
            f"🔧 Причина:\n{request.reason}\n\n"
            f"📅 {format_date(request.created_at)}\n\n"
            f"Статус:\n{status_emoji} {request.status.value}"
        )

    async def notify_admins_feedback(
        self, admin_ids: list[int], telegram_id: int, text: str
    ) -> None:
        for admin_id in admin_ids:
            try:
                await self._bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Обратная связь от @{telegram_id}\n\n{text}",
                )
            except Exception:
                logger.exception(
                    "Failed to send feedback to admin telegram_id=%s", admin_id
                )

    @staticmethod
    def format_request_short(user_info: User, request: Request) -> str:
        status_emoji = STATUS_EMOJI.get(request.status, "🟡")
        reason_first_line = request.reason.splitlines()[0] if request.reason else ""
        return (
            f"№{request.id}\n"
            f"🔧 {reason_first_line}\n"
            f"📅 {format_date(request.created_at)}\n"
            f"{status_emoji} {request.status.value}"
        )
