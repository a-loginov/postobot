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

# Database file lives in ./local_db relative to the project root.
# Path is computed from BASE_DIR so it works on any machine.
LOCAL_DB_DIR = BASE_DIR / "local_db"
DATABASE_URL = f"sqlite:///{LOCAL_DB_DIR / 'postobot.db'}"


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS
