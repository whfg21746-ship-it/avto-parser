import json
import logging
from typing import Any

from db.database import get_db

logger = logging.getLogger(__name__)


# --- Categories ---

async def get_all_categories() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM categories ORDER BY name"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_active_categories() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM categories WHERE is_active = 1 ORDER BY name"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_category(category_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def add_category(name: str, custom_prompt: str | None = None) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO categories (name, custom_prompt) VALUES (?, ?)",
        (name, custom_prompt),
    )
    await db.commit()
    return cursor.lastrowid


async def rename_category(category_id: int, name: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE categories SET name = ? WHERE id = ?",
        (name, category_id),
    )
    await db.commit()


async def update_category_field(category_id: int, field: str, value: Any) -> None:
    allowed = {"name", "is_active", "custom_prompt"}
    if field not in allowed:
        raise ValueError(f"Field {field} is not allowed for update")
    db = await get_db()
    await db.execute(
        f"UPDATE categories SET {field} = ? WHERE id = ?",  # noqa: S608
        (value, category_id),
    )
    await db.commit()


async def delete_category(category_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    await db.commit()


async def set_category_items_active(category_id: int, is_active: bool) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE items SET is_active = ? WHERE category_id = ?",
        (1 if is_active else 0, category_id),
    )
    await db.commit()


async def get_items_count_by_category(category_id: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM items WHERE category_id = ?",
        (category_id,),
    )
    row = await cursor.fetchone()
    return row[0]


async def get_active_items_count_by_category(category_id: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM items WHERE category_id = ? AND is_active = 1",
        (category_id,),
    )
    row = await cursor.fetchone()
    return row[0]


# --- Items ---

async def get_all_items() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT i.*, c.name as category_name "
        "FROM items i "
        "LEFT JOIN categories c ON i.category_id = c.id "
        "ORDER BY i.name"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_active_items() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT i.*, c.name as category_name, "
        "c.custom_prompt as category_custom_prompt "
        "FROM items i "
        "JOIN categories c ON i.category_id = c.id "
        "WHERE i.is_active = 1 AND c.is_active = 1 "
        "ORDER BY i.name"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_items_by_category(
    category_id: int, offset: int = 0, limit: int = 10,
) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT i.*, c.name as category_name "
        "FROM items i LEFT JOIN categories c ON i.category_id = c.id "
        "WHERE i.category_id = ? ORDER BY i.name LIMIT ? OFFSET ?",
        (category_id, limit, offset),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_item(item_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT i.*, c.name as category_name "
        "FROM items i "
        "LEFT JOIN categories c ON i.category_id = c.id "
        "WHERE i.id = ?",
        (item_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def add_item(
    category_id: int,
    name: str,
    avito_url: str,
    custom_prompt: str | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO items (category_id, name, avito_url, custom_prompt) "
        "VALUES (?, ?, ?, ?)",
        (category_id, name, avito_url, custom_prompt),
    )
    await db.commit()
    return cursor.lastrowid


async def update_item_field(item_id: int, field: str, value: Any) -> None:
    allowed = {"is_active", "name", "avito_url", "category_id", "custom_prompt"}
    if field not in allowed:
        raise ValueError(f"Field {field} is not allowed for update")
    db = await get_db()
    await db.execute(
        f"UPDATE items SET {field} = ? WHERE id = ?",  # noqa: S608
        (value, item_id),
    )
    await db.commit()


async def delete_item(item_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM seen_ads WHERE item_id = ?", (item_id,))
    await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    await db.commit()


# --- Seen Ads ---

async def has_seen_ads(item_id: int) -> bool:
    """Check if there are any seen ads for this item (first scan detection)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM seen_ads WHERE item_id = ? LIMIT 1", (item_id,)
    )
    row = await cursor.fetchone()
    return row is not None


async def is_ad_seen(ad_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM seen_ads WHERE ad_id = ?", (ad_id,)
    )
    row = await cursor.fetchone()
    return row is not None


async def save_seen_ad(
    ad_id: str,
    item_id: int,
    price: int,
    title: str,
    url: str,
    ai_verdict: dict | None = None,
    was_alerted: bool = False,
    skip_reason: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO seen_ads "
        "(ad_id, item_id, price, title, url, "
        "ai_verdict, was_alerted, skip_reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ad_id, item_id, price, title, url,
            json.dumps(ai_verdict, ensure_ascii=False) if ai_verdict else None,
            1 if was_alerted else 0,
            skip_reason,
        ),
    )
    await db.commit()


async def get_item_stats(item_id: int) -> dict:
    db = await get_db()
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


async def get_user_stats() -> dict:
    """Get overall stats for the current user."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM seen_ads")
    total_seen = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT COUNT(*) FROM seen_ads WHERE was_alerted = 1"
    )
    total_alerted = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM items WHERE is_active = 1")
    active_items = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE is_active = 1")
    active_categories = (await cursor.fetchone())[0]

    return {
        "total_seen": total_seen,
        "total_alerted": total_alerted,
        "active_items": active_items,
        "active_categories": active_categories,
    }


async def get_alerted_ads(limit: int = 1000) -> list[dict]:
    """Get seen_ads that were alerted (for export)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM seen_ads WHERE was_alerted = 1 "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_old_seen_ads(days: int = 30) -> int:
    """Delete seen_ads older than N days. Returns number deleted."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM seen_ads WHERE created_at < datetime('now', ?)",
        (f"-{days} days",),
    )
    await db.commit()
    return cursor.rowcount


# --- Settings ---

async def get_setting(key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()
