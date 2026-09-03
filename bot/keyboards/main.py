from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import is_admin


def get_main_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Создать заявку")],
        [KeyboardButton(text="📋 Мои заявки")],
        [KeyboardButton(text="ℹ️ Помощь")],
        [KeyboardButton(text="💬 Обратная связь")],
    ]
    if is_admin(telegram_id):
        buttons.append([KeyboardButton(text="🛠 Администрирование")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
