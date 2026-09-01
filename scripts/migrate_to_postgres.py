#!/usr/bin/env python3
"""
ПостоБот — перенос данных из SQLite (local_db/postobot.db) в PostgreSQL.

Использование:
    1. На русском школьном сервере поднят PostgreSQL
       (см. scripts/setup_ru_server.sh — создаёт БД `postobot` и пользователя).
    2. Задайте строку подключения к PostgreSQL через переменную окружения
       POSTGRES_URL (или впишите в .env), например:

       export POSTGRES_URL="postgresql+psycopg://postobot:ПАРОЛЬ@127.0.0.1:5432/postobot"

    3. Запустите:

       python scripts/migrate_to_postgres.py

Скрипт:
    - читает данные из SQLite-источника;
    - создаёт таблицы в PostgreSQL;
    - переносит пользователей и заявки;
    - выравнивает последовательности id (счётчики номеров заявок);
    - ничего не удаляет в PostgreSQL при непустой базе без подтверждения.

Заготовка для production-этапа. Сейчас в .env:
    DATABASE_URL  — локальная SQLite (источник).
    POSTGRES_URL  — целевая PostgreSQL (переопределяет postgresql+psycopg).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

# Позволяет запускать скрипт как из корня проекта, так и из scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from database.models import Base, Request, User  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate_to_postgres")

TABLES = ["users", "requests"]


def get_tunnel_proxy() -> str | None:
    """Прокси туннеля NL-шлюза (SOCKS 127.0.0.1:10808), если задан.

    позволяя подключение к Postgres на РФ-сервере через VLESS+REALITY-туннель.
    """
    return os.getenv("XRAY_TUNNEL_PROXY")


def build_pg_engine(pg_url: str):
    proxy = get_tunnel_proxy()
    if proxy:
        logger.info("Подключение к PostgreSQL через туннель: %s", proxy)
    return create_engine(
        pg_url,
        connect_args={"http_proxy": proxy, "https_proxy": proxy} if proxy else {},
        pool_pre_ping=True,
    )


def has_data(engine) -> bool:
    """Есть ли уже записи в целевых таблицах."""
    insp = inspect(engine)
    count = 0
    with engine.connect() as conn:
        for table in TABLES:
            if insp.has_table(table):
                count += conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    return count > 0


def migrate() -> None:
    # --- Источник: SQLite (локальная БД разработки) ---
    src_engine = create_engine(config.DATABASE_URL)

    # --- Цель: PostgreSQL ---
    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL_PG")
    if not pg_url:
        logger.error(
            "Не задан POSTGRES_URL. Пример:\n"
            'export POSTGRES_URL="postgresql+psycopg://postobot:ПАРОЛЬ@127.0.0.1:5432/postobot"'
        )
        sys.exit(1)

    pg_engine = build_pg_engine(pg_url)

    # Проверяем доступность Postgres
    try:
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось подключиться к PostgreSQL: %s", exc)
        logger.error(
            "Проверьте POSTGRES_URL и доступность сервера (в т.ч. через туннель)."
        )
        sys.exit(1)

    if has_data(pg_engine):
        logger.warning("В целевых таблицах PostgreSQL уже есть данные!")
        answer = input("Продолжить (добавить) [y/N]? ").strip().lower()
        if answer != "y":
            logger.info("Остановлено пользователем.")
            sys.exit(0)

    # --- Создаём схемы таблиц в PostgreSQL ---
    Base.metadata.create_all(bind=pg_engine)
    logger.info("Таблицы созданы/подтверждены: users, requests")

    # --- Переносим данные ---
    pg_tables = {t: Base.metadata.tables[t] for t in TABLES}

    with src_engine.connect() as src_conn, pg_engine.begin() as pg_conn:
        for table in TABLES:
            source_rows = src_conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            logger.info("%s: найдено %d записей", table, len(source_rows))
            if not source_rows:
                continue

            columns = [c.key for c in pg_tables[table].columns if c.key in row.keys()]
            for row in source_rows:
                values = {k: row[k] for k in columns}
                pg_conn.execute(pg_tables[table].insert().values(**values))

            logger.info("%s: перенесено в PostgreSQL", table)

    logger.info("Данные перенесены.")

    # --- Выравниваем последовательности PostgreSQL ---
    insp = inspect(pg_engine)
    with pg_engine.connect() as conn:
        for table in TABLES:
            if not insp.has_table(table):
                continue
            max_id = conn.execute(
                text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
            ).scalar()
            # Стандартное имя последовательности SQLAlchemy: <table>_id_seq
            seq_name = f"{table}_id_seq"
            try:
                conn.execute(
                    text(f"SELECT setval('{seq_name}', :v, true)")
                    .bindparams(v=max_id or 1)
                )
                logger.info("Последовательность %s установлена на %s", seq_name, max_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Не удалось выровнять последовательность %s: %s", seq_name, exc)

    logger.info("Перенос завершён.")


if __name__ == "__main__":
    migrate()