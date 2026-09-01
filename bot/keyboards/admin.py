from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆕 Новые заявки", callback_data="admin_new")],
        ]
    )


def get_admin_request_keyboard(
    request_id: int, status: str, user_telegram_id: int | None = None
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if status == "NEW":
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🔧 В работу", callback_data=f"admin_status:{request_id}:IN_PROGRESS"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"admin_status:{request_id}:REJECTED"
                ),
            ]
        )
    elif status == "IN_PROGRESS":
        buttons.append(
            [
                InlineKeyboardButton(
                    text="☑️ Выполнено", callback_data=f"admin_status:{request_id}:COMPLETED"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"admin_status:{request_id}:REJECTED"
                ),
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔍 Открыть", callback_data=f"admin_open:{request_id}")]
    )
    if user_telegram_id is not None:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👤 Пользователь",
                    callback_data=f"admin_user:{user_telegram_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)