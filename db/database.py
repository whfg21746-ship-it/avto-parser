import asyncio
import contextvars
import logging
import os
from pathlib import Path

import aiosqlite

import config

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Per-user context: set by middleware for handlers, set manually for scheduler
current_user_id: contextvars.ContextVar[int] = contextvars.ContextVar(
    "current_user_id"
)

# Track which users have had their DB initialized this session
_initialized_users: set[int] = set()

INITIAL_SETTINGS = {
    "city": "",
    "city_slug": "rossiya",
    "scan_interval_seconds": str(config.SCAN_INTERVAL),
    "max_seller_items": str(config.MAX_SELLER_ITEMS),
    "monitoring_enabled": "true",
    "proxy_list": "[]",
}

# Connection pool: reuse connections per user instead of open/close each time
_connection_pool: dict[int, aiosqlite.Connection] = {}
_pool_lock = asyncio.Lock()


def _db_path_for_user(user_id: int) -> str:
    """Return database file path for a specific user."""
    base_dir = os.path.dirname(config.DATABASE_PATH)
    return os.path.join(base_dir, f"user_{user_id}", "flipper.db")


async def get_db() -> aiosqlite.Connection:
    """Get a connection to the current user's database.

    Connections are cached per user and reused across calls.
    """
    user_id = current_user_id.get()

    # Fast path: connection already cached and alive
    if user_id in _connection_pool:
        conn = _connection_pool[user_id]
        try:
            # Quick health check
            await conn.execute("SELECT 1")
            return conn
        except Exception:
            # Connection is dead, remove from pool
            try:
                await conn.close()
            except Exception:
                pass
            del _connection_pool[user_id]

    # Slow path: create new connection
    async with _pool_lock:
        # Double-check after acquiring lock
        if user_id in _connection_pool:
            return _connection_pool[user_id]

        db_path = _db_path_for_user(user_id)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        _connection_pool[user_id] = db
        return db


async def close_all_connections() -> None:
    """Close all cached connections. Call on shutdown."""
    for user_id, conn in list(_connection_pool.items()):
        try:
            await conn.close()
        except Exception:
            pass
    _connection_pool.clear()


async def ensure_db_initialized() -> None:
    """Initialize the database for the current user if not done yet."""
    user_id = current_user_id.get()
    if user_id in _initialized_users:
        return

    db = await get_db()

    # Check if this is old schema (has search_queries table) — needs full reset
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_queries'"
    )
    has_old_schema = await cursor.fetchone() is not None

    if has_old_schema:
        logger.info("User %d: old schema detected, dropping tables...", user_id)
        for table in ("seen_ads", "items", "search_queries", "categories", "settings"):
            await db.execute(f"DROP TABLE IF EXISTS {table}")
        await db.commit()

    # Apply clean schema
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    await db.executescript(schema_sql)

    # Migrate: add custom_prompt columns if missing
    for table in ("categories", "items"):
        cursor = await db.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in await cursor.fetchall()}
        if "custom_prompt" not in columns:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN custom_prompt TEXT DEFAULT NULL"
            )
            logger.info("User %d: added custom_prompt to %s", user_id, table)

    # Migrate: remove market_price column if present (recreate table)
    cursor = await db.execute("PRAGMA table_info(items)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "market_price" in columns:
        logger.info("User %d: removing market_price column...", user_id)
        await db.execute(
            "CREATE TABLE items_new ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE, "
            "name TEXT NOT NULL, "
            "avito_url TEXT NOT NULL, "
            "model_pattern TEXT, "
            "threshold_price INTEGER NOT NULL, "
            "custom_prompt TEXT DEFAULT NULL, "
            "is_active BOOLEAN DEFAULT 1, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "INSERT INTO items_new "
            "(id, category_id, name, avito_url, model_pattern, "
            "threshold_price, custom_prompt, is_active, created_at) "
            "SELECT id, category_id, name, avito_url, model_pattern, "
            "threshold_price, custom_prompt, is_active, created_at "
            "FROM items"
        )
        await db.execute("DROP TABLE items")
        await db.execute("ALTER TABLE items_new RENAME TO items")
        logger.info("User %d: market_price column removed", user_id)

    await db.commit()

    # Seed default settings if table is empty
    cursor = await db.execute("SELECT COUNT(*) FROM settings")
    row = await cursor.fetchone()
    if row[0] == 0:
        for key, value in INITIAL_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        # Auto-set telegram_chat_id to this user's ID
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("telegram_chat_id", str(user_id)),
        )
        logger.info("User %d: seeded default settings", user_id)

    await db.commit()
    logger.info("User %d: database initialized", user_id)

    _initialized_users.add(user_id)


def get_all_user_ids() -> list[int]:
    """Discover all user IDs by scanning the data directory."""
    base_dir = os.path.dirname(config.DATABASE_PATH)
    abs_base = os.path.abspath(base_dir)
    if not os.path.exists(abs_base):
        logger.warning("Data directory does not exist: %s", abs_base)
        return []
    user_ids = []
    entries = os.listdir(abs_base)
    for name in entries:
        full = os.path.join(abs_base, name)
        if name.startswith("user_") and os.path.isdir(full):
            try:
                uid = int(name.split("_", 1)[1])
                user_ids.append(uid)
            except (ValueError, IndexError):
                pass
    if not user_ids:
        logger.warning(
            "No user directories found in %s (entries: %s)",
            abs_base, entries[:20],
        )
    return user_ids
