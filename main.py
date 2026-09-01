import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
from database.database import init_db

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="my", description="Мои заявки"),
    BotCommand(command="admin", description="Администрирование"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def main() -> None:
    setup_logging()

    logger.info("Подключение к базе данных: %s", config.DATABASE_URL)
    init_db()
    logger.info("База данных готова")

    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    from bot.handlers import admin, fallback, request, start, user

    dp.include_router(start.router)
    dp.include_router(user.router)
    dp.include_router(request.router)
    dp.include_router(admin.router)
    dp.include_router(fallback.router)

    await bot.set_my_commands(BOT_COMMANDS)

    logger.info("ПостоБот запущен")
    try:
        await dp.start_polling(bot)
    except Exception:
        logger.exception("Ошибка при работе бота")
    finally:
        logger.info("ПостоБот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
