import logging
import os
from pathlib import Path

import aiosqlite

import config

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

INITIAL_SETTINGS = {
    "city": "",
    "city_slug": "rossiya",
    "scan_interval_seconds": str(config.SCAN_INTERVAL),
    "max_seller_items": str(config.MAX_SELLER_ITEMS),
    "monitoring_enabled": "true",
    "telegram_chat_id": config.TELEGRAM_CHAT_ID,
    "proxy_list": "[]",
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
        # Check if this is old schema (has search_queries table) — needs full reset
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_queries'"
        )
        has_old_schema = await cursor.fetchone() is not None

        if has_old_schema:
            logger.info("Detected old schema, dropping all tables for clean start...")
            await db.execute("DROP TABLE IF EXISTS seen_ads")
            await db.execute("DROP TABLE IF EXISTS items")
            await db.execute("DROP TABLE IF EXISTS search_queries")
            await db.execute("DROP TABLE IF EXISTS categories")
            await db.execute("DROP TABLE IF EXISTS settings")
            await db.commit()

        # Apply clean schema
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        await db.executescript(schema_sql)

        # Seed default settings if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        row = await cursor.fetchone()
        if row[0] == 0:
            for key, value in INITIAL_SETTINGS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            logger.info("Seeded default settings")

        await db.commit()
        logger.info("Database initialized (clean slate)")
    finally:
        await db.close()
