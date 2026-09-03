import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
from database.database import SessionLocal, init_db
from database.models import User, UserRole

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="my", description="Мои заявки"),
    BotCommand(command="admin", description="Администрирование"),
    BotCommand(command="feedback", description="Обратная связь"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def seed_admins() -> None:
    db = SessionLocal()
    try:
        for tg_id in config.ADMIN_IDS:
            user = db.query(User).filter(User.telegram_id == tg_id).first()
            if user is None:
                user = User(telegram_id=tg_id, role=UserRole.ADMIN)
                db.add(user)
                logger.info("Seeded admin telegram_id=%s", tg_id)
            elif user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                logger.info("Promoted telegram_id=%s to ADMIN", tg_id)
        db.commit()
    finally:
        db.close()


async def main() -> None:
    setup_logging()

    logger.info("Подключение к базе данных: %s", config.DATABASE_URL)
    init_db()
    seed_admins()
    logger.info("База данных готова")

    from admin.main import start_admin_server

    start_admin_server()
    logger.info("Админ-панель запущена на http://%s:%s", config.ADMIN_HOST, config.ADMIN_PORT)

    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    from bot.handlers import admin, fallback, feedback, request, start, user

    dp.include_router(start.router)
    dp.include_router(user.router)
    dp.include_router(request.router)
    dp.include_router(feedback.router)
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
