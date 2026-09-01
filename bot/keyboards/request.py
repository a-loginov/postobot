from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

CANCEL_TEXT = "❌ Отмена"


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]], resize_keyboard=True
    )


def get_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="req_accept"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="req_edit"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="req_cancel")],
        ]
    )


def get_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 ФИО", callback_data="edit_name"),
                InlineKeyboardButton(text="🏫 Класс", callback_data="edit_class"),
            ],
            [
                InlineKeyboardButton(text="🔧 Причина", callback_data="edit_reason"),
                InlineKeyboardButton(text="📷 Фото", callback_data="edit_photo"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_back")],
        ]
    )
