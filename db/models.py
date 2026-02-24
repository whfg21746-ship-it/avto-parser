import json
import logging
from typing import Any

from db.database import get_db

logger = logging.getLogger(__name__)


# --- Categories ---

async def get_all_categories() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM categories ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_active_categories() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM categories WHERE is_active = 1 ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_category(category_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def add_category(name: str, avito_category_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO categories (name, avito_category_id) VALUES (?, ?)",
            (name, avito_category_id),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def delete_category(category_id: int) -> None:
    db = await get_db()
    try:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()
    finally:
        await db.close()


async def update_category_avito_id(category_id: int, avito_category_id: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE categories SET avito_category_id = ? WHERE id = ?",
            (avito_category_id, category_id),
        )
        await db.commit()
    finally:
        await db.close()


# --- Search Queries ---

async def get_all_search_queries() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT sq.*, c.name as category_name "
            "FROM search_queries sq "
            "LEFT JOIN categories c ON sq.category_id = c.id "
            "ORDER BY sq.keyword"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_active_search_queries() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT sq.*, c.name as category_name "
            "FROM search_queries sq "
            "LEFT JOIN categories c ON sq.category_id = c.id "
            "WHERE sq.is_active = 1 "
            "ORDER BY sq.keyword"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_search_query(query_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT sq.*, c.name as category_name "
            "FROM search_queries sq "
            "LEFT JOIN categories c ON sq.category_id = c.id "
            "WHERE sq.id = ?",
            (query_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def add_search_query(
    category_id: int,
    keyword: str,
    avito_category_id: int | None = None,
    price_max: int | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO search_queries (category_id, keyword, avito_category_id, price_max) "
            "VALUES (?, ?, ?, ?)",
            (category_id, keyword, avito_category_id, price_max),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_search_query_field(query_id: int, field: str, value: Any) -> None:
    allowed = {"keyword", "avito_category_id", "price_max", "is_active", "category_id"}
    if field not in allowed:
        raise ValueError(f"Field {field} is not allowed for update")
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE search_queries SET {field} = ? WHERE id = ?",  # noqa: S608
            (value, query_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete_search_query(query_id: int) -> None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM items WHERE search_query_id = ?", (query_id,)
        )
        item_ids = [row[0] for row in await cursor.fetchall()]
        for item_id in item_ids:
            await db.execute("DELETE FROM seen_ads WHERE item_id = ?", (item_id,))
        await db.execute("DELETE FROM items WHERE search_query_id = ?", (query_id,))
        await db.execute("DELETE FROM search_queries WHERE id = ?", (query_id,))
        await db.commit()
    finally:
        await db.close()


async def get_items_count_by_search_query(query_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM items WHERE search_query_id = ?",
            (query_id,),
        )
        row = await cursor.fetchone()
        return row[0]
    finally:
        await db.close()


# --- Items ---

async def get_all_items() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, c.name as category_name, sq.keyword as search_keyword "
            "FROM items i "
            "LEFT JOIN categories c ON i.category_id = c.id "
            "LEFT JOIN search_queries sq ON i.search_query_id = sq.id "
            "ORDER BY i.name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_active_items() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, c.name as category_name, c.avito_category_id, "
            "sq.keyword as search_keyword "
            "FROM items i "
            "JOIN categories c ON i.category_id = c.id "
            "LEFT JOIN search_queries sq ON i.search_query_id = sq.id "
            "WHERE i.is_active = 1 AND c.is_active = 1 "
            "ORDER BY i.name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_items_by_search_query(query_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, c.name as category_name "
            "FROM items i "
            "LEFT JOIN categories c ON i.category_id = c.id "
            "WHERE i.search_query_id = ? AND i.is_active = 1 "
            "ORDER BY i.name",
            (query_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_item(item_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, c.name as category_name, sq.keyword as search_keyword "
            "FROM items i "
            "LEFT JOIN categories c ON i.category_id = c.id "
            "LEFT JOIN search_queries sq ON i.search_query_id = sq.id "
            "WHERE i.id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def add_item(
    search_query_id: int,
    category_id: int,
    name: str,
    model_pattern: str,
    threshold_price: int,
    market_price: int,
    storage_gb: int | None = None,
    max_seller_items: int = 10,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO items (search_query_id, category_id, name, model_pattern, "
            "storage_gb, threshold_price, market_price, max_seller_items) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (search_query_id, category_id, name, model_pattern, storage_gb,
             threshold_price, market_price, max_seller_items),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_item_field(item_id: int, field: str, value: Any) -> None:
    allowed = {"threshold_price", "market_price", "is_active", "name",
               "model_pattern", "storage_gb", "max_seller_items", "search_query_id"}
    if field not in allowed:
        raise ValueError(f"Field {field} is not allowed for update")
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE items SET {field} = ? WHERE id = ?",  # noqa: S608
            (value, item_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete_item(item_id: int) -> None:
    db = await get_db()
    try:
        await db.execute("DELETE FROM seen_ads WHERE item_id = ?", (item_id,))
        await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        await db.commit()
    finally:
        await db.close()


# --- Seen Ads ---

async def is_ad_seen(ad_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM seen_ads WHERE ad_id = ?", (ad_id,)
        )
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def save_seen_ad(
    ad_id: str,
    item_id: int,
    price: int,
    title: str,
    url: str,
    seller_type: str,
    ai_verdict: dict | None = None,
    profit_estimate: int | None = None,
    was_alerted: bool = False,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO seen_ads "
            "(ad_id, item_id, price, title, url, seller_type, "
            "ai_verdict, profit_estimate, was_alerted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ad_id, item_id, price, title, url, seller_type,
                json.dumps(ai_verdict, ensure_ascii=False) if ai_verdict else None,
                profit_estimate,
                1 if was_alerted else 0,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def get_item_stats(item_id: int) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM seen_ads WHERE item_id = ?",
            (item_id,),
        )
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) as alerted FROM seen_ads "
            "WHERE item_id = ? AND was_alerted = 1",
            (item_id,),
        )
        alerted = (await cursor.fetchone())[0]

        return {"total": total, "alerted": alerted}
    finally:
        await db.close()


# --- Settings ---

async def get_setting(key: str) -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()


async def set_setting(key: str, value: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()


async def get_items_by_category(
    category_id: int, offset: int = 0, limit: int = 10,
) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, c.name as category_name "
            "FROM items i LEFT JOIN categories c ON i.category_id = c.id "
            "WHERE i.category_id = ? ORDER BY i.name LIMIT ? OFFSET ?",
            (category_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_items_count_by_category(category_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM items WHERE category_id = ?",
            (category_id,),
        )
        row = await cursor.fetchone()
        return row[0]
    finally:
        await db.close()
