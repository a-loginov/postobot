from aiogram import types
from aiogram.filters import BaseFilter

from config import is_admin


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return is_admin(message.from_user.id)


class IsAdminCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: types.CallbackQuery) -> bool:
        return is_admin(callback_query.from_user.id)
