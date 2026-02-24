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

INITIAL_SEARCH_QUERIES = [
    {"keyword": "iphone", "category_id": 1, "avito_category_id": 84, "price_max": 150000},
    {"keyword": "macbook", "category_id": 2, "avito_category_id": None, "price_max": 250000},
    {"keyword": "airpods", "category_id": 3, "avito_category_id": None, "price_max": 50000},
    {"keyword": "ipad", "category_id": 4, "avito_category_id": None, "price_max": 150000},
    {"keyword": "apple watch", "category_id": 1, "avito_category_id": None, "price_max": 80000},
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


async def _migrate_old_schema(db: aiosqlite.Connection) -> bool:
    """Migrate from old schema (items with search_query/avito_params) to new schema."""
    cursor = await db.execute("PRAGMA table_info(items)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "search_query" not in columns:
        return False

    logger.info("Detected old schema, running migration...")

    # Check if search_queries table exists
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_queries'"
    )
    if not await cursor.fetchone():
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER REFERENCES categories(id),
                keyword TEXT NOT NULL,
                avito_category_id INTEGER,
                price_max INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Seed initial search queries
    cursor = await db.execute("SELECT COUNT(*) FROM search_queries")
    sq_count = (await cursor.fetchone())[0]
    if sq_count == 0:
        for sq in INITIAL_SEARCH_QUERIES:
            await db.execute(
                "INSERT INTO search_queries (keyword, category_id, avito_category_id, price_max) "
                "VALUES (?, ?, ?, ?)",
                (sq["keyword"], sq["category_id"], sq["avito_category_id"], sq["price_max"]),
            )

    # Build keyword -> search_query_id mapping
    cursor = await db.execute("SELECT id, keyword FROM search_queries")
    sq_map = {}
    for row in await cursor.fetchall():
        sq_map[row[1].lower()] = row[0]

    # Create new items table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_query_id INTEGER REFERENCES search_queries(id),
            category_id INTEGER REFERENCES categories(id),
            name TEXT NOT NULL,
            model_pattern TEXT NOT NULL,
            storage_gb INTEGER,
            threshold_price INTEGER NOT NULL,
            market_price INTEGER NOT NULL,
            max_seller_items INTEGER DEFAULT 10,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate items
    from parser.model_matcher import extract_storage_from_name, generate_model_pattern

    cursor = await db.execute("SELECT * FROM items")
    old_items = await cursor.fetchall()
    old_col_names = [desc[0] for desc in cursor.description]

    for row in old_items:
        item = dict(zip(old_col_names, row))
        name = item["name"]
        pattern = generate_model_pattern(name)
        storage = extract_storage_from_name(name)

        # Determine search_query_id from name
        name_lower = name.lower()
        sq_id = None
        for keyword, qid in sq_map.items():
            if keyword in name_lower:
                sq_id = qid
                break
        if sq_id is None:
            # Fallback: use first search query for the same category
            for keyword, qid in sq_map.items():
                sq_id = qid
                break

        await db.execute(
            "INSERT INTO items_new (search_query_id, category_id, name, model_pattern, "
            "storage_gb, threshold_price, market_price, max_seller_items, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sq_id, item.get("category_id"), name, pattern, storage,
                item["threshold_price"], item["market_price"],
                item.get("max_seller_items", 10), item.get("is_active", 1),
                item.get("created_at"),
            ),
        )

    # Update seen_ads to point to new item IDs (same IDs since we preserved order)
    # Drop old items and rename new
    await db.execute("DROP TABLE items")
    await db.execute("ALTER TABLE items_new RENAME TO items")

    await db.commit()
    logger.info("Migration complete: %d items migrated", len(old_items))
    return True


async def init_db() -> None:
    db = await get_db()
    try:
        # Check if we need to migrate
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
        )
        has_items_table = await cursor.fetchone() is not None

        if has_items_table:
            migrated = await _migrate_old_schema(db)
            if migrated:
                # Schema is already up to date after migration
                # Just ensure search_queries table has the new schema applied
                schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
                await db.executescript(schema_sql)
                await db.commit()
                return

        # Fresh install or already migrated — apply schema
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

        # Seed search queries if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM search_queries")
        row = await cursor.fetchone()
        if row[0] == 0:
            for sq in INITIAL_SEARCH_QUERIES:
                await db.execute(
                    "INSERT INTO search_queries (keyword, category_id, avito_category_id, price_max) "
                    "VALUES (?, ?, ?, ?)",
                    (sq["keyword"], sq["category_id"], sq["avito_category_id"], sq["price_max"]),
                )
            logger.info("Seeded %d initial search queries", len(INITIAL_SEARCH_QUERIES))

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
