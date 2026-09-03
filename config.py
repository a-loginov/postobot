import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set. Copy .env.example to .env and fill it.")
    return value


BOT_TOKEN: str = _get_required("BOT_TOKEN")

ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
]

ADMIN_PASSWORD: str = _get_required("ADMIN_PASSWORD")
SECRET_KEY: str = _get_required("SECRET_KEY")
ADMIN_HOST: str = os.getenv("ADMIN_HOST", "localhost")
ADMIN_PORT: int = int(os.getenv("ADMIN_PORT", "2026"))

LOCAL_DB_DIR = BASE_DIR / "local_db"
DATABASE_URL = f"sqlite:///{LOCAL_DB_DIR / 'postobot.db'}"


def is_admin(telegram_id: int) -> bool:
    if telegram_id in ADMIN_IDS:
        return True
    try:
        from database.database import SessionLocal
        from database.models import User, UserRole

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            return user is not None and user.role == UserRole.ADMIN
        finally:
            db.close()
    except Exception:
        return False
