import logging
import os
from pathlib import Path

import aiosqlite

import config

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

INITIAL_CATEGORIES = [
    {"name": "Смартфоны Apple", "avito_category_id": 14},
    {"name": "Ноутбуки Apple", "avito_category_id": 17},
    {"name": "Наушники Apple", "avito_category_id": 31},
    {"name": "Планшеты Apple", "avito_category_id": 137},
]

INITIAL_SETTINGS = {
    "monitoring_enabled": "true",
    "scan_interval_seconds": str(config.SCAN_INTERVAL),
    "proxy_list": "[]",
    "telegram_chat_id": config.TELEGRAM_CHAT_ID,
}


async def get_db() -> aiosqlite.Connection:
    db_path = config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        await db.executescript(schema_sql)

        # Seed categories if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM categories")
        row = await cursor.fetchone()
        if row[0] == 0:
            for cat in INITIAL_CATEGORIES:
                await db.execute(
                    "INSERT INTO categories (name, avito_category_id) VALUES (?, ?)",
                    (cat["name"], cat["avito_category_id"]),
                )
            logger.info("Seeded %d initial categories", len(INITIAL_CATEGORIES))

        # Seed settings if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        row = await cursor.fetchone()
        if row[0] == 0:
            for key, value in INITIAL_SETTINGS.items():
                await db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            logger.info("Seeded initial settings")

        await db.commit()
        logger.info("Database initialized successfully")
    finally:
        await db.close()
